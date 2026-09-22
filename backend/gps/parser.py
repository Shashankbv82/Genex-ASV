"""
GENEX ASV - Robust NMEA GPS Parser
Processes RMC, GGA, GSA, and GSV sentences from SIMCom A7672S UART stream.
"""

import time
import logging
from typing import Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger("genex.gps.parser")

def nmea_coord_to_decimal(raw_coord: str, direction: str) -> Optional[float]:
    """
    Converts NMEA lat/lon (DDMM.MMMM / DDDMM.MMMM) to signed decimal degrees.
    Rejects 0.0, 0.0 and out-of-bounds coordinates.
    """
    if not raw_coord or not direction:
        return None
    try:
        raw_val = float(raw_coord)
        if raw_val == 0.0:
            return None
        
        # In DDMM.MMMM or DDDMM.MMMM format, degrees are before the last 2 digits before dot
        dot_idx = raw_coord.find(".")
        if dot_idx < 2:
            return None
            
        deg_str = raw_coord[:dot_idx - 2]
        min_str = raw_coord[dot_idx - 2:]
        
        degrees = float(deg_str)
        minutes = float(min_str)
        
        decimal = degrees + (minutes / 60.0)
        if direction.upper() in ["S", "W"]:
            decimal = -decimal
            
        # Range validation
        if direction.upper() in ["N", "S"] and not (-90.0 <= decimal <= 90.0):
            return None
        if direction.upper() in ["E", "W"] and not (-180.0 <= decimal <= 180.0):
            return None
            
        return round(decimal, 7)
    except (ValueError, IndexError):
        return None

def parse_nmea_sentence(line: str, gps_data) -> bool:
    """
    Parses a single NMEA sentence and updates fields of the GPSData instance.
    Returns True if valid data was parsed.
    """
    if not line or not line.startswith("$"):
        return False
        
    line = line.strip()
    # Validate checksum (standard valid NMEA sentences must have checksum)
    if "*" not in line:
        return False

    body, checksum_hex = line[1:].split("*", 1)
    try:
        expected_cksum = int(checksum_hex[:2], 16)
        calculated_cksum = 0
        for char in body:
            calculated_cksum ^= ord(char)
        if calculated_cksum != expected_cksum:
            # Checksum mismatch, ignore corrupted sentence
            return False
    except (ValueError, IndexError):
        return False

    parts = body.split(",")
    if not parts:
        return False

    talker_type = parts[0]
    sentence_type = talker_type[-3:] if len(talker_type) >= 3 else talker_type
    if sentence_type not in ("RMC", "GGA", "GSA", "GSV"):
        # Not a recognized standard navigation sentence
        return False

    gps_data.sentence_counts[talker_type] = gps_data.sentence_counts.get(talker_type, 0) + 1
    gps_data.raw_sample = line

    now_mono = time.monotonic()
    # Update stream freshness timestamp whenever a valid, checksummed NMEA sentence is parsed
    gps_data.last_update_monotonic = now_mono
    gps_data.last_valid_nmea_monotonic = now_mono
    gps_data.is_stale = False
    updated = False

    try:
        # ==================== RMC: Recommended Minimum ====================
        if sentence_type == "RMC":
            # $xxRMC,time,status,lat,NS,lon,EW,spd,cog,date,mv,mvE,mode,nav*cs
            if len(parts) > 2:
                status = parts[2].upper()
                if status == "A":
                    gps_data.fix_valid = True
                elif status == "V" and gps_data.fix_quality == 0:
                    gps_data.fix_valid = False
                
                if len(parts) > 6 and (status == "A" or gps_data.fix_valid):
                    lat = nmea_coord_to_decimal(parts[3], parts[4])
                    lon = nmea_coord_to_decimal(parts[5], parts[6])
                    if lat is not None and lon is not None:
                        gps_data.latitude = lat
                        gps_data.longitude = lon
                        updated = True
                        
                if len(parts) > 7 and parts[7]:
                    try:
                        spd_knots = float(parts[7])
                        gps_data.speed_knots = round(spd_knots, 2)
                        gps_data.speed_mps = round(spd_knots * 0.514444, 2)
                    except ValueError:
                        pass
                        
                if len(parts) > 8 and parts[8]:
                    try:
                        gps_data.course_deg = round(float(parts[8]), 1)
                    except ValueError:
                        pass
                        
                if len(parts) > 1 and parts[1]:
                    gps_data.timestamp_utc = parts[1]

        # ==================== GGA: Global Positioning System Fix Data ====================
        elif sentence_type == "GGA":
            # $xxGGA,time,lat,NS,lon,EW,quality,numSV,HDOP,alt,M,sep,M,diffAge,diffStation*cs
            if len(parts) > 6:
                try:
                    fix_quality = int(parts[6]) if parts[6] else 0
                    gps_data.fix_quality = fix_quality
                    if fix_quality > 0:
                        gps_data.fix_valid = True
                except ValueError:
                    pass
                    
                if len(parts) > 5 and (gps_data.fix_quality > 0 or gps_data.fix_valid):
                    lat = nmea_coord_to_decimal(parts[2], parts[3])
                    lon = nmea_coord_to_decimal(parts[4], parts[5])
                    if lat is not None and lon is not None:
                        gps_data.latitude = lat
                        gps_data.longitude = lon
                        updated = True
                        
                if len(parts) > 7 and parts[7]:
                    try:
                        gps_data.satellites_used = int(parts[7])
                    except ValueError:
                        pass
                        
                if len(parts) > 8 and parts[8]:
                    try:
                        hdop_val = round(float(parts[8]), 2)
                        if 0.0 < hdop_val < 90.0:
                            gps_data.hdop = hdop_val
                    except ValueError:
                        pass
                        
                if len(parts) > 9 and parts[9]:
                    try:
                        gps_data.altitude_m = round(float(parts[9]), 1)
                    except ValueError:
                        pass

        # ==================== GSA: GNSS DOP and Active Satellites ====================
        elif sentence_type == "GSA":
            # $xxGSA,opMode,navMode,prn1..prn12,PDOP,HDOP,VDOP,systemId*cs
            if len(parts) > 2:
                nav_mode = parts[2]
                if nav_mode == "3":
                    gps_data.fix_type = "3D"
                elif nav_mode == "2":
                    if gps_data.fix_type != "3D":
                        gps_data.fix_type = "2D"
                elif nav_mode == "1":
                    # Only demote to "none" if no valid fix across constellations
                    if not gps_data.fix_valid and gps_data.fix_type not in ("2D", "3D"):
                        gps_data.fix_type = "none"
                    
            if len(parts) >= 17:
                # Active PRNs are in fields 3 to 14
                new_prns = [p for p in parts[3:15] if p.strip()]
                if new_prns:
                    # Merge unique PRNs across constellations
                    existing = set(gps_data.active_prns)
                    existing.update(new_prns)
                    gps_data.active_prns = sorted(list(existing))
                try:
                    # Only accept DOP values that indicate an active fix (< 90.0)
                    if parts[15]:
                        pdop_val = round(float(parts[15]), 2)
                        if 0.0 < pdop_val < 90.0:
                            gps_data.pdop = pdop_val
                    if parts[16]:
                        hdop_val = round(float(parts[16]), 2)
                        if 0.0 < hdop_val < 90.0:
                            gps_data.hdop = hdop_val
                    if len(parts) > 17 and parts[17]:
                        vdop_val = round(float(parts[17].split("*")[0]), 2)
                        if 0.0 < vdop_val < 90.0:
                            gps_data.vdop = vdop_val
                except ValueError:
                    pass

        # ==================== GSV: Satellites in View ====================
        elif sentence_type == "GSV":
            # $xxGSV,numMsgs,msgNum,numSats,...
            if len(parts) > 3 and parts[3]:
                try:
                    total_sats = int(parts[3])
                    # Update visible satellites count
                    gps_data.satellites_visible = max(gps_data.satellites_visible, total_sats)
                except ValueError:
                    pass

    except Exception as e:
        logger.debug("Error parsing NMEA line %s: %s", line, e)
        return False

    return True
