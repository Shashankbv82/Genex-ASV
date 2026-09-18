"""
GENEX ASV - Main Backend API & WebSocket Server
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import settings
from backend.gps.reader import gps_reader
from backend.gps.filter import gps_filter
from backend.imu.reader import imu_reader
from backend.system_monitor import get_system_health
from backend.telemetry.state import ASVTelemetry, GPSData, SystemHealth, IMUData

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("genex.backend")

# Active WebSocket connections
active_websockets: list[WebSocket] = []
current_operating_mode = "manual"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start GPS reader thread, IMU reader thread, and background telemetry broadcaster
    logger.info("Starting GENEX ASV Backend Services...")
    gps_reader.start_reader()
    imu_reader.start_reader()
    broadcast_task = asyncio.create_task(telemetry_broadcaster())
    yield
    # Shutdown
    logger.info("Stopping GENEX ASV Backend Services...")
    broadcast_task.cancel()
    imu_reader.stop_reader()
    gps_reader.stop_reader()

app = FastAPI(title="GENEX ASV Backend API", version="1.0.0", lifespan=lifespan)

# Enable CORS for frontend development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ModeRequest(BaseModel):
    mode: str

@app.get("/api/health", response_model=SystemHealth)
async def api_health():
    return get_system_health()

@app.get("/api/gps", response_model=GPSData)
async def api_gps():
    return gps_reader.get_state()

@app.get("/api/imu", response_model=IMUData)
async def api_imu():
    return imu_reader.get_state()

@app.get("/api/telemetry", response_model=ASVTelemetry)
async def api_telemetry():
    gps = gps_reader.get_state()
    filtered = gps_filter.get_filtered_position()
    imu = imu_reader.get_state()
    sys_health = get_system_health()
    return ASVTelemetry(
        operating_mode=current_operating_mode,
        gps=gps,
        filtered=filtered,
        imu=imu,
        system=sys_health
    )


@app.post("/api/mode")
async def set_operating_mode(req: ModeRequest):
    global current_operating_mode
    if req.mode in ["manual", "semi_autonomous"]:
        current_operating_mode = req.mode
        logger.info("Switched operating mode to: %s", current_operating_mode)
        return {"status": "ok", "mode": current_operating_mode}
    return {"status": "error", "message": "Invalid mode. Must be manual or semi_autonomous"}

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    logger.info("WebSocket client connected. Active clients: %d", len(active_websockets))
    try:
        while True:
            # Keep connection alive; handle any client messages/pings
            msg = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
        logger.info("WebSocket client disconnected. Remaining clients: %d", len(active_websockets))

async def telemetry_broadcaster():
    """Broadcasts telemetry state to all connected WebSockets at configured Hz."""
    interval = 1.0 / settings.TELEMETRY_BROADCAST_RATE_HZ
    last_gps_utc = None
    last_gps_mono = 0.0
    while True:
        try:
            t_now = time.monotonic()
            gps = gps_reader.get_state()

            # Detect fresh GNSS measurement from GPSReader
            is_new_fix = False
            if gps.connected and gps.fix_valid:
                if gps.timestamp_utc and gps.timestamp_utc != last_gps_utc:
                    is_new_fix = True
                    last_gps_utc = gps.timestamp_utc
                    last_gps_mono = gps.last_update_monotonic
                elif gps.last_update_monotonic > 0 and gps.last_update_monotonic != last_gps_mono:
                    is_new_fix = True
                    last_gps_mono = gps.last_update_monotonic

            if is_new_fix:
                gps_filter.update(gps, t_now)

            # Advance filter prediction to current 5 Hz tick
            gps_filter.predict_to(t_now)
            filtered = gps_filter.get_filtered_position()

            if active_websockets:
                sys_health = get_system_health()
                imu = imu_reader.get_state()
                telem = ASVTelemetry(
                    operating_mode=current_operating_mode,
                    gps=gps,
                    filtered=filtered,
                    imu=imu,
                    system=sys_health
                )
                payload = telem.model_dump_json()

                
                # Send to all connected sockets
                disconnected = []
                for ws in active_websockets:
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        disconnected.append(ws)
                        
                for ws in disconnected:
                    if ws in active_websockets:
                        active_websockets.remove(ws)
                        
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in telemetry broadcaster: %s", e)
            await asyncio.sleep(1.0)

# Serve production frontend if built
dist_dir = os.path.join(os.path.dirname(__file__), "../frontend/dist")
if os.path.exists(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index_file = os.path.join(dist_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "ok", "message": "Frontend build in progress or dist/index.html not found."}
