"""
GENEX ASV - Threaded UART GPS Serial Reader
Continuously consumes /dev/ttyS0 at 115200 baud, 8N1 with graceful error handling and auto-reconnect.
Includes dynamic AT-port discovery, freshness-based GNSS watchdog, bounded exponential backoff,
concurrency safety, and SIMCom A7672S initialization.
"""

import os
import glob
import threading
import time
import math
import logging
import serial
from typing import Optional, List
from datetime import datetime, timezone
from backend.telemetry.state import GPSData
from backend.gps.parser import parse_nmea_sentence
from backend.gps.persistence import save_last_known_fix, load_last_known_fix
from backend.config import settings

logger = logging.getLogger("genex.gps.reader")


class GPSReader(threading.Thread):
    def __init__(self, port: str = settings.GPS_SERIAL_PORT, baudrate: int = settings.GPS_BAUDRATE):
        super().__init__(daemon=True, name="GPSReaderThread")
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self._lock = threading.Lock()
        
        # Internal GPS state
        self._data = GPSData(source=f"SIMCom A7672S UART ({port})")
        self._ser: Optional[serial.Serial] = None

        # Freshness watchdog & recovery state machine
        # States: STARTING | HEALTHY | STALE | RECOVERING | BACKOFF | STOPPING
        self._recovery_state: str = "STARTING"
        self._last_valid_nmea_mono: float = 0.0
        self._recovery_lock = threading.Lock()
        self._recovery_in_progress: bool = False
        self._retry_count: int = 0
        self._next_retry_time_mono: float = 0.0
        self._active_at_port: Optional[str] = None
        self._recovery_worker_thread: Optional[threading.Thread] = None

        # Load persistent last-known GPS fix on startup
        cached_fix = load_last_known_fix(settings.GPS_CACHE_FILE)
        if cached_fix:
            self._data.latitude = cached_fix.get("latitude")
            self._data.longitude = cached_fix.get("longitude")
            self._data.altitude_m = cached_fix.get("altitude_m")
            self._data.speed_mps = 0.0
            self._data.speed_knots = 0.0
            self._data.course_deg = cached_fix.get("course_deg")
            self._data.satellites_used = cached_fix.get("satellites_used", 0)
            self._data.hdop = cached_fix.get("hdop")
            self._data.timestamp_utc = cached_fix.get("timestamp_utc")
            self._data.position_source = "last_known"
            self._data.live_fix_valid = False
            self._data.awaiting_live_fix = True
            self._data.last_known_timestamp_iso = cached_fix.get("saved_at_iso")
            saved_epoch = cached_fix.get("saved_at_epoch")
            if saved_epoch:
                self._cached_fix_epoch: Optional[float] = float(saved_epoch)
                self._data.last_known_fix_age_seconds = round(max(0.0, time.time() - self._cached_fix_epoch), 1)
            else:
                self._cached_fix_epoch = None
            logger.info("GPSReader initialized with LAST KNOWN fix: lat=%.7f, lon=%.7f (awaiting live GNSS)",
                        self._data.latitude, self._data.longitude)
        else:
            self._data.position_source = "none"
            self._data.live_fix_valid = False
            self._data.awaiting_live_fix = True
            self._cached_fix_epoch = None
            logger.info("GPSReader initialized with NO cached fix (awaiting live GNSS)")

        # Throttling state for saving live fixes to disk
        self._last_saved_time = 0.0
        self._last_saved_lat: Optional[float] = None
        self._last_saved_lon: Optional[float] = None

    def _send_at(self, ser_port: serial.Serial, cmd: bytes, timeout: float = 1.5) -> str:
        """Sends an AT command and reads response until OK, ERROR, or timeout."""
        ser_port.reset_input_buffer()
        ser_port.write(cmd)
        deadline = time.monotonic() + timeout
        buf = []
        while time.monotonic() < deadline:
            if ser_port.in_waiting:
                chunk = ser_port.read(ser_port.in_waiting).decode("ascii", errors="replace")
                buf.append(chunk)
                full = "".join(buf)
                if "OK" in full or "ERROR" in full:
                    break
            time.sleep(0.03)
        return "".join(buf)

    def _verify_simcom_port(self, ser_port: serial.Serial) -> bool:
        """
        Validates that the serial port responds to AT and belongs to a SIMCom modem
        with GNSS capability. Rejects unrelated serial adapters or unresponsive ports.
        """
        resp_at = self._send_at(ser_port, b"AT\r\n", 1.0)
        if "OK" not in resp_at:
            return False

        # Test GNSS command support on this AT port
        resp_gnss = self._send_at(ser_port, b"AT+CGNSSPWR=?\r\n", 1.5)
        if "OK" in resp_gnss or "+CGNSSPWR:" in resp_gnss:
            return True

        # Secondary check: module identification
        resp_ati = self._send_at(ser_port, b"ATI\r\n", 1.5)
        if any(ident in resp_ati for ident in ("SIMCom", "A76", "SIM76")):
            return True

        return False

    def find_simcom_at_port(self) -> Optional[str]:
        """
        Dynamically discovers and verifies an accessible SIMCom AT command port.
        Checks:
        1. Previously active verified port
        2. Configured candidate ports (settings.SIMCOM_AT_PORT_CANDIDATES)
        3. Dynamic glob discovery of /dev/ttyUSB*
        """
        candidates: List[str] = []

        # 1. Check previously active port first
        if self._active_at_port and os.path.exists(self._active_at_port):
            candidates.append(self._active_at_port)

        # 2. Add configured candidate ports
        config_candidates = getattr(settings, "SIMCOM_AT_PORT_CANDIDATES", ["/dev/ttyUSB2", "/dev/ttyUSB1"])
        for p in config_candidates:
            if p not in candidates and os.path.exists(p):
                candidates.append(p)

        # 3. Add dynamically enumerated /dev/ttyUSB* ports
        for p in sorted(glob.glob("/dev/ttyUSB*")):
            if p not in candidates:
                candidates.append(p)

        for port in candidates:
            try:
                with serial.Serial(port, 115200, timeout=1.0) as ser:
                    if self._verify_simcom_port(ser):
                        logger.info("Verified SIMCom AT control port: %s", port)
                        self._active_at_port = port
                        with self._lock:
                            self._data.modem_at_port = port
                        return port
            except (serial.SerialException, OSError) as e:
                logger.debug("Port %s not usable for SIMCom AT commands: %s", port, e)
                continue

        return None

    def _execute_modem_init_sequence(self, at_port: str) -> bool:
        """
        Sends the required SIMCom GNSS startup sequence:
        AT
        AT+CGNSSPWR=1
        AT+CGNSSPORTSWITCH=1,1
        AT+CGNSSTST=1
        AT+CGPSAUTO=1 (optional persistent auto-start, non-blocking response)

        NOTE: AT+CGPSWARM is strictly OMITTED from the startup path.
        Issuing AT+CGPSWARM with outdated or unverified ephemeris triggers
        $EPHABNORMAL,1*50 errors and delays satellite acquisition significantly.
        """
        try:
            with serial.Serial(at_port, 115200, timeout=1.5) as ser:
                # 1. Sync AT interface
                self._send_at(ser, b"AT\r\n", 1.0)

                # 2. Turn on GNSS receiver power
                resp_pwr = self._send_at(ser, b"AT+CGNSSPWR=1\r\n", 3.0)
                time.sleep(0.3)
                if ser.in_waiting:
                    ser.read(ser.in_waiting)

                # 3. Configure output port switch: mode 1 (enable), port 1 (UART /dev/ttyS0)
                resp_port = self._send_at(ser, b"AT+CGNSSPORTSWITCH=1,1\r\n", 2.0)
                time.sleep(0.2)

                # 4. Enable continuous NMEA sentence output stream
                resp_tst = self._send_at(ser, b"AT+CGNSSTST=1\r\n", 2.0)
                time.sleep(0.2)

                # 5. Set modem firmware NVRAM auto-start (optional capability)
                resp_auto = self._send_at(ser, b"AT+CGPSAUTO=1\r\n", 2.0)

                success = "OK" in resp_pwr and "OK" in resp_port and "OK" in resp_tst
                logger.info("SIMCom GNSS sequence executed via %s (PWR: %s, SW: %s, TST: %s, AUTO: %s)",
                            at_port,
                            "OK" if "OK" in resp_pwr else "RESP",
                            "OK" if "OK" in resp_port else "RESP",
                            "OK" if "OK" in resp_tst else "RESP",
                            "OK" if "OK" in resp_auto else "RESP")
                return success
        except Exception as e:
            logger.warning("Error executing GNSS initialization on %s: %s", at_port, e)
            return False

    def _run_recovery_worker(self):
        """
        Background recovery worker thread.
        Protected by _recovery_lock to guarantee strictly ONE worker runs at a time.
        Executes dynamic port discovery, sends the initialization sequence, and applies
        bounded exponential backoff on failure.
        """
        try:
            if not self.running:
                return

            at_port = self.find_simcom_at_port()
            if not at_port:
                with self._recovery_lock:
                    self._recovery_state = "BACKOFF"
                    base = getattr(settings, "GPS_RECOVERY_BACKOFF_BASE_SEC", 2.0)
                    max_b = getattr(settings, "GPS_RECOVERY_BACKOFF_MAX_SEC", 30.0)
                    delay = min(base * (2 ** self._retry_count), max_b)
                    self._retry_count += 1
                    self._next_retry_time_mono = time.monotonic() + delay
                    with self._lock:
                        self._data.gnss_health_state = "BACKOFF"
                logger.warning("No responsive SIMCom AT port found. Entering backoff for %.1fs (retry #%d).",
                               delay, self._retry_count)
                return

            with self._recovery_lock:
                self._recovery_state = "RECOVERING"
                with self._lock:
                    self._data.gnss_health_state = "RECOVERING"

            init_ok = self._execute_modem_init_sequence(at_port)
            if init_ok:
                # Sequence executed; state remains RECOVERING until actual valid NMEA resumes on /dev/ttyS0
                with self._recovery_lock:
                    timeout = getattr(settings, "GPS_NMEA_SILENCE_TIMEOUT_SEC", 10.0)
                    self._next_retry_time_mono = time.monotonic() + timeout
                logger.info("GNSS init sequence succeeded on %s. Awaiting valid NMEA stream on %s.", at_port, self.port)
            else:
                with self._recovery_lock:
                    self._recovery_state = "BACKOFF"
                    base = getattr(settings, "GPS_RECOVERY_BACKOFF_BASE_SEC", 2.0)
                    max_b = getattr(settings, "GPS_RECOVERY_BACKOFF_MAX_SEC", 30.0)
                    delay = min(base * (2 ** self._retry_count), max_b)
                    self._retry_count += 1
                    self._next_retry_time_mono = time.monotonic() + delay
                    with self._lock:
                        self._data.gnss_health_state = "BACKOFF"
                logger.warning("GNSS init sequence failed on %s. Entering backoff for %.1fs (retry #%d).",
                               at_port, delay, self._retry_count)
        except Exception as e:
            logger.error("Unexpected error in GNSS recovery worker: %s", e)
            with self._recovery_lock:
                self._recovery_state = "BACKOFF"
                self._next_retry_time_mono = time.monotonic() + getattr(settings, "GPS_RECOVERY_BACKOFF_BASE_SEC", 2.0)
        finally:
            with self._recovery_lock:
                self._recovery_in_progress = False

    def _trigger_recovery(self, reason: str) -> bool:
        """
        Attempts to launch the recovery worker if no worker is currently running
        and backoff deadline has passed.
        """
        with self._recovery_lock:
            if not self.running:
                return False
            if self._recovery_in_progress:
                return False
            if time.monotonic() < self._next_retry_time_mono:
                return False

            self._recovery_in_progress = True
            logger.info("Triggering GNSS recovery worker: %s", reason)
            self._recovery_worker_thread = threading.Thread(
                target=self._run_recovery_worker,
                name="GNSSRecoveryWorker",
                daemon=True
            )
            self._recovery_worker_thread.start()
            return True

    def start_reader(self):
        """Starts the GPS reader thread and non-blocking background initialization."""
        self.running = True
        with self._recovery_lock:
            self._recovery_state = "STARTING"
            with self._lock:
                self._data.gnss_health_state = "STARTING"
        # Trigger initial non-blocking recovery / modem initialization immediately
        self._trigger_recovery(reason="initial service startup")
        self.start()
        logger.info("GPSReader started on %s @ %d baud", self.port, self.baudrate)

    def stop_reader(self):
        """Stops the GPS reader thread and cleanly releases serial resources."""
        self.running = False
        with self._recovery_lock:
            self._recovery_state = "STOPPING"
            with self._lock:
                self._data.gnss_health_state = "STOPPING"

        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:
                pass

        if self._recovery_worker_thread and self._recovery_worker_thread.is_alive():
            self._recovery_worker_thread.join(timeout=2.0)

        logger.info("GPSReader stopped.")

    def get_state(self) -> GPSData:
        """Returns a thread-safe copy of the latest GPS telemetry state."""
        with self._lock:
            now = time.monotonic()
            if self._data.last_update_monotonic > 0:
                age = round(now - self._data.last_update_monotonic, 2)
                self._data.data_age_seconds = age
                if age > settings.GPS_STALE_THRESHOLD_SEC:
                    self._data.is_stale = True
            else:
                self._data.data_age_seconds = 999.0
                self._data.is_stale = True

            with self._recovery_lock:
                self._data.gnss_health_state = self._recovery_state

            if self._data.position_source == "last_known" and self._cached_fix_epoch:
                self._data.last_known_fix_age_seconds = round(max(0.0, time.time() - self._cached_fix_epoch), 1)

            return self._data.model_copy()

    def run(self):
        """
        Main serial consumer loop consuming /dev/ttyS0.
        Continuously tracks freshness of valid NMEA sentences and triggers
        recovery whenever the stream falls silent.
        """
        try:
            reconnect_delay = 1.0
            opened_time = 0.0

            while self.running:
                try:
                    logger.info("Opening serial port %s...", self.port)
                    self._ser = serial.Serial(self.port, self.baudrate, timeout=settings.GPS_TIMEOUT)
                    self._ser.reset_input_buffer()
                    opened_time = time.monotonic()
                    
                    with self._lock:
                        self._data.connected = True
                    reconnect_delay = 1.0
                    logger.info("Connected to GPS port %s", self.port)

                    while self.running and self._ser.is_open:
                        try:
                            line = self._ser.readline().decode("utf-8", errors="replace").strip()
                            now_mono = time.monotonic()

                            if line:
                                with self._lock:
                                    parsed = parse_nmea_sentence(line, self._data)

                                if parsed:
                                    self._last_valid_nmea_mono = now_mono
                                    with self._recovery_lock:
                                        if self._recovery_state != "HEALTHY":
                                            self._recovery_state = "HEALTHY"
                                            self._retry_count = 0
                                            self._next_retry_time_mono = 0.0
                                            logger.info("GNSS stream is HEALTHY. Resumed valid NMEA data on %s.", self.port)
                                        with self._lock:
                                            self._data.gnss_health_state = "HEALTHY"

                                    # Manage Live GPS vs Cached GPS state transitions
                                    with self._lock:
                                        if self._data.fix_valid and self._data.latitude is not None and self._data.longitude is not None:
                                            self._data.position_source = "live"
                                            self._data.live_fix_valid = True
                                            self._data.awaiting_live_fix = False
                                            self._data.last_known_fix_age_seconds = None
                                            self._cached_fix_epoch = time.time()
                                            self._data.last_known_timestamp_iso = datetime.now(timezone.utc).isoformat()

                                            # Throttled disk persistence for valid live fixes
                                            now_t = time.monotonic()
                                            dist_moved = 0.0
                                            if self._last_saved_lat is not None and self._last_saved_lon is not None:
                                                dlat = (self._data.latitude - self._last_saved_lat) * 111139.0
                                                dlon = (self._data.longitude - self._last_saved_lon) * 111139.0 * math.cos(math.radians(self._data.latitude))
                                                dist_moved = math.hypot(dlat, dlon)

                                            time_elapsed = now_t - self._last_saved_time
                                            should_save = (
                                                self._last_saved_time == 0.0 or
                                                dist_moved >= settings.GPS_CACHE_MIN_DISPLACEMENT_M or
                                                time_elapsed >= settings.GPS_CACHE_MIN_INTERVAL_SEC
                                            )
                                            if should_save:
                                                save_last_known_fix(self._data, settings.GPS_CACHE_FILE)
                                                self._last_saved_time = now_t
                                                self._last_saved_lat = self._data.latitude
                                                self._last_saved_lon = self._data.longitude
                                        else:
                                            # Fix lost or awaiting satellite lock
                                            self._data.live_fix_valid = False
                                            self._data.awaiting_live_fix = True
                                            if self._data.latitude is not None and self._data.longitude is not None:
                                                self._data.position_source = "last_known"

                            # Stream silence monitor: check if valid NMEA has stopped arriving
                            silence_threshold = getattr(settings, "GPS_NMEA_SILENCE_TIMEOUT_SEC", 10.0)
                            time_since_valid = (now_mono - self._last_valid_nmea_mono) if self._last_valid_nmea_mono > 0 else (now_mono - opened_time)

                            if silence_threshold > 0 and time_since_valid >= silence_threshold:
                                with self._recovery_lock:
                                    if self._recovery_state == "HEALTHY":
                                        self._recovery_state = "STALE"
                                        logger.warning("GNSS stream became STALE (no valid NMEA for %.1fs).", time_since_valid)
                                    with self._lock:
                                        self._data.gnss_health_state = self._recovery_state
                                self._trigger_recovery(reason=f"NMEA silence for {time_since_valid:.1f}s")

                        except (serial.SerialException, OSError, ValueError, TypeError) as read_err:
                            if not self.running:
                                break
                            logger.warning("Serial read error on %s: %s", self.port, read_err)
                            break
                        except Exception as e:
                            if not self.running:
                                break
                            logger.warning("Unexpected serial read exception on %s: %s", self.port, e)
                            break

                except (serial.SerialException, OSError) as conn_err:
                    if not self.running:
                        break
                    logger.warning("Failed to open %s: %s. Retrying in %.1fs...", self.port, conn_err, reconnect_delay)
                    with self._lock:
                        self._data.connected = False
                        with self._recovery_lock:
                            self._recovery_state = "STALE"
                            self._data.gnss_health_state = "STALE"
                    self._trigger_recovery(reason=f"UART open error on {self.port}")
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
        except Exception as e:
            if self.running:
                logger.error("Unhandled exception in GPSReader thread: %s", e, exc_info=True)


# Singleton global instance
gps_reader = GPSReader()
