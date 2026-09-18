"""
GENEX ASV - Threaded UART GPS Serial Reader
Continuously consumes /dev/ttyS0 at 115200 baud, 8N1 with graceful error handling and auto-reconnect.
"""

import os
import threading
import time
import logging
import serial
from typing import Optional
from backend.telemetry.state import GPSData
from backend.gps.parser import parse_nmea_sentence
from backend.config import settings

logger = logging.getLogger("genex.gps.reader")

class GPSReader(threading.Thread):
    def __init__(self, port: str = settings.GPS_SERIAL_PORT, baudrate: int = settings.GPS_BAUDRATE):
        super().__init__(daemon=True, name="GPSReaderThread")
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self._lock = threading.Lock()
        
        # Internal state
        self._data = GPSData(source=f"SIMCom A7672S UART ({port})")
        self._ser: Optional[serial.Serial] = None

    def _init_simcom_modem(self):
        """Auto-powers GNSS engine and routes NMEA to UART on SIMCom A7672S if AT port is present."""
        at_port = getattr(settings, "SIMCOM_AT_PORT", "/dev/ttyUSB2")
        if not os.path.exists(at_port):
            return
        try:
            logger.info("Initializing SIMCom GNSS via AT port %s...", at_port)
            with serial.Serial(at_port, 115200, timeout=1.5) as ser:
                ser.write(b"AT+CGNSSPWR=1\r\n")
                time.sleep(0.3)
                ser.write(b"AT+CGNSSPORTSWITCH=1,1\r\n")
                time.sleep(0.3)
            logger.info("SIMCom GNSS engine active on %s", at_port)
        except Exception as e:
            logger.warning("Could not auto-initialize SIMCom GNSS via %s: %s", at_port, e)

    def start_reader(self):
        self._init_simcom_modem()
        self.running = True
        self.start()
        logger.info("GPSReader started on %s @ %d baud", self.port, self.baudrate)

    def stop_reader(self):
        self.running = False
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:
                pass
        logger.info("GPSReader stopped.")

    def get_state(self) -> GPSData:
        with self._lock:
            # Update data age
            now = time.monotonic()
            if self._data.last_update_monotonic > 0:
                age = round(now - self._data.last_update_monotonic, 2)
                self._data.data_age_seconds = age
                if age > settings.GPS_STALE_THRESHOLD_SEC:
                    self._data.is_stale = True
            else:
                self._data.data_age_seconds = 999.0
                self._data.is_stale = True

            # Return a copy of GPSData
            return self._data.model_copy()

    def run(self):
        reconnect_delay = 1.0
        while self.running:
            try:
                logger.info("Opening serial port %s...", self.port)
                self._ser = serial.Serial(self.port, self.baudrate, timeout=settings.GPS_TIMEOUT)
                self._ser.reset_input_buffer()
                
                with self._lock:
                    self._data.connected = True
                reconnect_delay = 1.0
                logger.info("Connected to GPS port %s", self.port)

                while self.running and self._ser.is_open:
                    try:
                        line = self._ser.readline().decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                            
                        with self._lock:
                            parse_nmea_sentence(line, self._data)
                    except (serial.SerialException, OSError) as read_err:
                        logger.warning("Serial read error on %s: %s", self.port, read_err)
                        break

            except (serial.SerialException, OSError) as conn_err:
                logger.warning("Failed to open %s: %s. Retrying in %.1fs...", self.port, conn_err, reconnect_delay)
                with self._lock:
                    self._data.connected = False
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, 5.0)

            finally:
                if self._ser:
                    try:
                        self._ser.close()
                    except Exception:
                        pass
                with self._lock:
                    self._data.connected = False
                    
            time.sleep(0.5)

# Singleton global instance
gps_reader = GPSReader()
