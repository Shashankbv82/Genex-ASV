"""
GENEX ASV - Unified RC Receiver Manager (RCReader)
Supports both PPM on GPIO 22 and i-BUS on hardware UART / USB serial.
Publishes calibrated, normalized control inputs with 200 ms failsafe monitoring.
"""

import logging
import threading
import time
from typing import Dict, Optional, Tuple

from backend.config import settings
from backend.telemetry.state import RCStatus
from backend.rc.signal_processing import SignalProcessor
from backend.rc.ppm_decoder import PPMDecoder
from backend.rc.ibus_decoder import IBusDecoder

logger = logging.getLogger("genex.rc.reader")


class RCReader:
    """Thread-safe manager for the active FlySky RC receiver decoder."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self.processor = SignalProcessor()
        self.protocol = settings.RC_PROTOCOL.upper()

        if self.protocol == "IBUS":
            self.decoder = IBusDecoder(
                pin=settings.RC_GPIO_PIN,
                port=settings.RC_SERIAL_PORT,
                baudrate=settings.RC_SERIAL_BAUDRATE,
                failsafe_timeout=settings.RC_FAILSAFE_TIMEOUT_SEC,
            )
        else:
            self.decoder = PPMDecoder(
                pin=settings.RC_GPIO_PIN,
                failsafe_timeout=settings.RC_FAILSAFE_TIMEOUT_SEC,
            )

        # Internal state
        self._status = RCStatus(
            rc_enabled=settings.RC_ENABLED,
            protocol=self.protocol,
            connected=False,
            signal_health="DISCONNECTED",
            failsafe_active=True,
        )

        self._raw_channels: Dict[int, Optional[int]] = {ch: None for ch in range(1, 15)}
        self._norm_steering: float = 0.0
        self._norm_throttle: float = 0.0
        self._manual_requested: bool = False
        self._is_throttle_zero: bool = False
        self._frame_age: float = 999.0
        self._is_healthy: bool = False
        self.frame_ready_event = threading.Event()
        self.last_rcreader_update_time: float = 0.0

    def start(self) -> None:
        """Start the RC receiver decoder and background monitor thread."""
        with self._lock:
            if self._running:
                logger.warning("RCReader is already running.")
                return

            if not settings.RC_ENABLED:
                logger.info("RCReader is disabled in configuration.")
                return

            self._running = True
            opened = self.decoder.open()
            if not opened:
                logger.warning("Failed to open %s decoder on hardware. Will keep polling safely.", self.protocol)

            self._thread = threading.Thread(
                target=self._monitor_loop,
                name="RCReaderThread",
                daemon=True
            )
            self._thread.start()
            logger.info("RCReader thread started (%s mode).", self.protocol)

    def stop(self) -> None:
        """Clean shutdown handler."""
        with self._lock:
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        self.decoder.close()
        logger.info("RCReader stopped.")

    def _monitor_loop(self) -> None:
        """Event-driven consumer loop with 50 Hz fallback."""
        loop_interval = 1.0 / settings.RC_LOOP_HZ
        dec_event = getattr(self.decoder, "frame_ready_event", None)

        while self._running:
            if dec_event is not None:
                dec_event.wait(timeout=loop_interval)
                dec_event.clear()
            else:
                time.sleep(loop_interval)

            if not self._running:
                break

            t_now = time.monotonic()

            try:
                channels, frame_age, is_healthy = self.decoder.read_channels()
                valid_cnt = getattr(self.decoder, "valid_frames", 0)
                last_t = getattr(self.decoder, "last_frame_time", 0.0)

                # Authoritative RC health condition:
                # 1. Decoder reports healthy
                # 2. At least one valid frame has been received
                # 3. Last frame timestamp is non-zero
                # 4. Frame age is within configured failsafe timeout
                is_valid_link = bool(
                    is_healthy
                    and (valid_cnt > 0)
                    and (last_t > 0.0)
                    and (frame_age <= settings.RC_FAILSAFE_TIMEOUT_SEC)
                )

                if is_valid_link:
                    connected = True
                    sig_health = "HEALTHY"
                    failsafe = False

                    ch1 = channels.get(settings.RC_STEERING_CHANNEL)
                    ch3 = channels.get(settings.RC_THROTTLE_CHANNEL)
                    ch5 = channels.get(settings.RC_ARM_CHANNEL)

                    norm_str = self.processor.process_steering(ch1)
                    norm_thr = self.processor.process_throttle(ch3)
                    manual_req = self.processor.is_manual_requested(ch5)
                    thr_zero = self.processor.is_throttle_at_zero(ch3)
                else:
                    # When RC link is unhealthy, disconnected, or in failsafe:
                    # MUST NOT treat any channel value as valid operator input.
                    connected = bool(valid_cnt > 0 and frame_age < 2.0)
                    sig_health = "LOST" if connected else "DISCONNECTED"
                    failsafe = True

                    ch1 = None
                    ch3 = None
                    ch5 = None
                    norm_str = 0.0
                    norm_thr = 0.0
                    manual_req = False
                    thr_zero = False
                    channels = {ch: None for ch in range(1, 15)}

                with self._lock:
                    self._raw_channels = channels
                    self._norm_steering = norm_str
                    self._norm_throttle = norm_thr
                    self._manual_requested = manual_req
                    self._is_throttle_zero = thr_zero
                    self._frame_age = frame_age
                    self._is_healthy = is_valid_link
                    self.last_rcreader_update_time = t_now

                    self._status = RCStatus(
                        rc_enabled=settings.RC_ENABLED,
                        protocol=self.protocol,
                        connected=connected,
                        signal_health=sig_health,
                        failsafe_active=failsafe,
                        data_age_seconds=round(frame_age, 3),
                        last_frame_monotonic=last_t,
                        ch1_raw=ch1,
                        ch3_raw=ch3,
                        ch5_raw=ch5,
                        normalized_steering=norm_str,
                        normalized_throttle=norm_thr,
                        manual_requested=manual_req,
                        total_frames=getattr(self.decoder, "total_frames", 0),
                        valid_frames=valid_cnt,
                        rejected_frames=getattr(self.decoder, "rejected_frames", 0) + getattr(self.decoder, "checksum_errors", 0),
                        glitch_count=getattr(self.decoder, "glitch_count", 0),
                    )

                self.frame_ready_event.set()

            except Exception as exc:
                logger.error("Error in RCReader monitor loop: %s", exc)

    def get_status(self) -> RCStatus:
        """Returns thread-safe copy of latest RC status telemetry model."""
        with self._lock:
            return self._status.model_copy()

    def get_control_inputs(self) -> Tuple[float, float, bool, bool, bool, float]:
        """
        Returns latest processed control values:
        (norm_steering, norm_throttle, manual_requested, is_throttle_zero, is_healthy, frame_age)
        """
        with self._lock:
            return (
                self._norm_steering,
                self._norm_throttle,
                self._manual_requested,
                self._is_throttle_zero,
                self._is_healthy,
                self._frame_age
            )

    def get_latency_timestamps(self) -> Tuple[float, float, float]:
        """Returns (last_frame_recv, last_frame_decoded, last_rcreader_update)."""
        with self._lock:
            t_recv = getattr(self.decoder, "last_frame_recv_time", 0.0)
            t_dec = getattr(self.decoder, "last_frame_decoded_time", 0.0)
            t_rc = self.last_rcreader_update_time
            return t_recv, t_dec, t_rc


# Global singleton instance
rc_reader = RCReader()
