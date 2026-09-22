"""
GENEX ASV - GPS Fix Persistence Module
Provides atomic persistence for the last known valid GPS fix.
Ensures zero file corruption during sudden power drops and safe recovery from malformed files.
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger("genex.gps.persistence")

def get_default_cache_path() -> str:
    """Returns absolute path to data/last_gps_fix.json anchored to repository root."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "data", "last_gps_fix.json")

def is_valid_coordinate(lat: Any, lon: Any) -> bool:
    """Validates that lat/lon are numeric, in WGS84 range, and not (0.0, 0.0)."""
    if lat is None or lon is None:
        return False
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        return False

    if abs(lat_f) < 1e-6 and abs(lon_f) < 1e-6:
        return False
    if not (-90.0 <= lat_f <= 90.0):
        return False
    if not (-180.0 <= lon_f <= 180.0):
        return False
    return True

def save_last_known_fix(gps_data: Any, file_path: Optional[str] = None) -> bool:
    """
    Atomically persists a valid GPS fix to disk.
    Uses temp-file write + flush + fsync + atomic rename (os.replace).
    """
    lat = getattr(gps_data, "latitude", None)
    lon = getattr(gps_data, "longitude", None)

    if not is_valid_coordinate(lat, lon):
        return False

    target_path = file_path or get_default_cache_path()
    temp_path = f"{target_path}.tmp.{os.getpid()}_{int(time.monotonic() * 1000)}"

    now_utc = datetime.now(timezone.utc)
    now_epoch = time.time()

    payload: Dict[str, Any] = {
        "latitude": round(float(lat), 7),
        "longitude": round(float(lon), 7),
        "altitude_m": getattr(gps_data, "altitude_m", None),
        "speed_mps": getattr(gps_data, "speed_mps", None),
        "course_deg": getattr(gps_data, "course_deg", None),
        "satellites_used": getattr(gps_data, "satellites_used", 0),
        "hdop": getattr(gps_data, "hdop", None),
        "timestamp_utc": getattr(gps_data, "timestamp_utc", None),
        "saved_at_iso": now_utc.isoformat(),
        "saved_at_epoch": now_epoch
    }

    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, target_path)
        logger.debug("Persisted GPS fix to %s: lat=%.7f, lon=%.7f", target_path, payload["latitude"], payload["longitude"])
        return True
    except Exception as e:
        logger.error("Failed to persist GPS fix to %s: %s", target_path, e)
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        return False

def load_last_known_fix(file_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Loads and validates the last known GPS fix from persistent storage.
    Safely recovers from missing, empty, or corrupt files without raising exceptions.
    """
    target_path = file_path or get_default_cache_path()

    if not os.path.exists(target_path):
        logger.info("No persistent GPS fix file found at %s", target_path)
        return None

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            logger.warning("Persistent GPS fix file %s is empty", target_path)
            return None

        data = json.loads(content)
        if not isinstance(data, dict):
            logger.warning("Persistent GPS fix in %s is not a valid JSON object", target_path)
            return None

        lat = data.get("latitude")
        lon = data.get("longitude")

        if not is_valid_coordinate(lat, lon):
            logger.warning("Persistent GPS fix in %s contains invalid coordinates (lat=%s, lon=%s)", target_path, lat, lon)
            return None

        logger.info("Loaded last known GPS fix from %s: lat=%.7f, lon=%.7f (saved %s)",
                    target_path, float(lat), float(lon), data.get("saved_at_iso", "unknown"))
        return data

    except json.JSONDecodeError as jde:
        logger.warning("Corrupt JSON in persistent GPS fix file %s: %s", target_path, jde)
        return None
    except Exception as e:
        logger.error("Unexpected error reading persistent GPS fix from %s: %s", target_path, e)
        return None
