"""
GENEX ASV - FlySky iBUS Hardware Serial & GPIO Protocol Decoder
Supports both raw GPIO pin bitstream decoding via lgpio on BCM GPIO 22
and POSIX hardware UART / USB serial ports via pyserial.

Protocol Format (32 Bytes @ 115200 Baud, 8N1):
  Header  : 0x20 0x40 (2 Bytes)
  Channels: 14 Channels x 2 Bytes (Little-Endian 16-bit uint) = 28 Bytes
  Checksum: 2 Bytes (Sum of first 30 bytes subtracted from 0xFFFF)
"""

import bisect
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("genex.rc.ibus_decoder")

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

try:
    import lgpio
    HAS_LGPIO = True
except ImportError:
    HAS_LGPIO = False


class IBusDecoder:
    """Zero-copy, low-latency FlySky iBUS protocol decoder with GPIO and Serial transport."""

    def __init__(
        self,
        port: str = "/dev/ttyUSB3",
        baudrate: int = 115200,
        failsafe_timeout: float = 0.50,
        pin: Optional[int] = None,
        chip: int = 0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.failsafe_timeout = failsafe_timeout
        self.pin = pin
        self.chip = chip

        self._lock = threading.Lock()
        self.ser: Optional[serial.Serial] = None
        self._handle: Optional[int] = None
        self._cb = None

        self.channels: Dict[int, Optional[int]] = {ch: None for ch in range(1, 15)}
        self.last_frame_time: float = 0.0
        self.total_frames: int = 0
        self.valid_frames: int = 0
        self.checksum_errors: int = 0

        # Serial stream buffer
        self._buf = bytearray()

        # GPIO edge stream buffer
        self._edge_buf: List[Tuple[int, int]] = []
        self._last_edge_ns: int = 0

    def open(self) -> bool:
        """Initialize iBUS input: prefer GPIO if pin is configured, else open serial."""
        if self.pin is not None:
            return self._open_gpio()
        return self._open_serial()

    def _open_gpio(self) -> bool:
        """Open BCM GPIO line for edge alerts via lgpio."""
        if not HAS_LGPIO:
            logger.warning("lgpio is not installed. GPIO i-BUS decoding unavailable.")
            return False
        try:
            logger.info("Opening lgpio chip %d for i-BUS on BCM GPIO %d...", self.chip, self.pin)
            self._handle = lgpio.gpiochip_open(self.chip)
            res = lgpio.gpio_claim_alert(self._handle, self.pin, lgpio.BOTH_EDGES)
            if res < 0:
                raise RuntimeError(f"lgpio.gpio_claim_alert failed on GPIO {self.pin} with code {res}")

            self._cb = lgpio.callback(
                self._handle,
                self.pin,
                lgpio.BOTH_EDGES,
                self._edge_callback
            )
            logger.info("i-BUS decoder registered successfully on BCM GPIO %d.", self.pin)
            return True
        except Exception as exc:
            logger.warning("Failed to initialize i-BUS on BCM GPIO %d: %s", self.pin, exc)
            self.close()
            return False

    def _open_serial(self) -> bool:
        """Open serial port for iBUS."""
        if not HAS_SERIAL:
            logger.warning("pyserial is not installed. iBUS serial mode unavailable.")
            return False

        try:
            logger.info("Opening iBUS serial port %s @ %d baud...", self.port, self.baudrate)
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.005,
            )
            self.ser.reset_input_buffer()
            logger.info("iBUS serial port %s opened successfully.", self.port)
            return True
        except Exception as exc:
            logger.warning("Failed to open iBUS serial port %s: %s", self.port, exc)
            self.ser = None
            return False

    def _edge_callback(self, chip: int, gpio: int, level: int, tick: int) -> None:
        """
        Kernel edge alert callback on GPIO.
        Accumulates transitions and segments frames on inter-frame gap (> 3500 µs).
        """
        if self._last_edge_ns == 0:
            self._last_edge_ns = tick
            self._edge_buf.append((tick, level))
            return

        gap_us = (tick - self._last_edge_ns) / 1000.0
        self._last_edge_ns = tick

        # Inter-frame silence gap: At 115200 baud, maximum inter-edge gap during a frame
        # is < 100 us. Any gap >= 2000 us (2 ms) indicates end of frame.
        if gap_us >= 2000.0:
            if len(self._edge_buf) >= 30:
                frame_edges = self._edge_buf
                self._edge_buf = [(tick, level)]
                self._process_frame_edges(frame_edges)
            else:
                self._edge_buf = [(tick, level)]
        else:
            if len(self._edge_buf) < 400:
                self._edge_buf.append((tick, level))

    def _process_frame_edges(self, f_edges: List[Tuple[int, int]]) -> None:
        """Decodes raw frame edges into 32 bytes and verifies i-BUS frame."""
        raw_bytes = self._decode_edges_to_bytes(f_edges)
        if raw_bytes is None or len(raw_bytes) != 32:
            return

        if raw_bytes[0] != 0x20 or raw_bytes[1] != 0x40:
            return

        with self._lock:
            self.total_frames += 1

        candidate = bytes(raw_bytes)
        if self._verify_checksum(candidate):
            with self._lock:
                self._unpack_frame(candidate)
                self.last_frame_time = time.monotonic()
                self.valid_frames += 1
                if self.valid_frames == 1 or self.valid_frames % 500 == 0:
                    logger.info(
                        "i-BUS frame locked on GPIO %d: valid=%d [CH1=%s, CH3=%s, CH5=%s]",
                        self.pin,
                        self.valid_frames,
                        self.channels[1],
                        self.channels[3],
                        self.channels[5]
                    )
        else:
            with self._lock:
                self.checksum_errors += 1

    def _decode_edges_to_bytes(self, f_edges: List[Tuple[int, int]]) -> Optional[List[int]]:
        """
        Deserializes 115200 baud UART bytes from edge timestamps using start-bit resynchronization.
        Features early header rejection (0x20 0x40) to minimize CPU usage and prevent callback lag.
        """
        times = [e[0] for e in f_edges]
        lvls = [e[1] for e in f_edges]

        def get_lvl(t: int) -> int:
            p = bisect.bisect_right(times, t) - 1
            return lvls[p] if p >= 0 else 1

        # Locate initial falling edge of Byte 0
        idx = 0
        while idx < len(f_edges) and f_edges[idx][1] != 0:
            idx += 1
        if idx >= len(f_edges):
            return None

        t_start_0 = f_edges[idx][0]

        # Multi-phase search: test standard baud 8680.555 and slight crystal offsets
        for b_ns in (8680.555, 8715.0, 8645.0):
            for phase in (1.4, 1.5, 1.35, 1.45):
                t_cur = t_start_0
                bytes_out = []
                mismatch = False

                for b_num in range(32):
                    val = 0
                    for bit in range(8):
                        st = t_cur + int((phase + bit) * b_ns)
                        if get_lvl(st):
                            val |= (1 << bit)

                    # Early exit on header mismatch: saves 95%+ compute on invalid edge sequences
                    if b_num == 0 and val != 0x20:
                        mismatch = True
                        break
                    if b_num == 1 and val != 0x40:
                        mismatch = True
                        break

                    bytes_out.append(val)

                    # Look for falling edge of next byte's start bit around 10 bit times
                    min_next = t_cur + int(9.4 * b_ns)
                    max_next = t_cur + int(11.5 * b_ns)
                    pos = bisect.bisect_left(times, min_next)
                    next_fall = None
                    while pos < len(times) and times[pos] <= max_next:
                        if lvls[pos] == 0:
                            next_fall = times[pos]
                            break
                        pos += 1

                    # Standard UART 8N1 nominal inter-byte step is exactly 10.0 bit times
                    t_cur = next_fall if next_fall is not None else t_cur + int(10.0 * b_ns)

                if not mismatch and len(bytes_out) == 32:
                    chk = 0xFFFF - sum(bytes_out[:30])
                    fchk = bytes_out[30] | (bytes_out[31] << 8)
                    if chk == fchk:
                        return bytes_out

        return None

    def read_channels(self) -> Tuple[Dict[int, Optional[int]], float, bool]:
        """
        Returns thread-safe copy of latest decoded channels and health status.
        When link is unhealthy, disconnected, or stale, returns None for all channels.
        """
        now = time.monotonic()

        # If serial port transport is active, poll incoming buffer
        if self.ser is not None and self.ser.is_open:
            self._poll_serial(now)

        with self._lock:
            ch_copy = self.channels.copy()
            last_t = self.last_frame_time
            valid_cnt = self.valid_frames

        frame_age = now - last_t if last_t > 0.0 else 999.0
        is_healthy = (last_t > 0.0) and (valid_cnt > 0) and (frame_age <= self.failsafe_timeout)

        if not is_healthy:
            return {ch: None for ch in range(1, 15)}, frame_age, False

        return ch_copy, frame_age, True

    def _poll_serial(self, now: float) -> None:
        """Drains serial queue and parses newest complete 32-byte frame."""
        try:
            waiting = self.ser.in_waiting
            if waiting > 0:
                chunk = self.ser.read(waiting)
                if chunk:
                    self._buf.extend(chunk)

            if len(self._buf) > 256:
                self._buf = self._buf[-128:]

            latest_frame: Optional[bytes] = None
            idx = 0
            while idx <= len(self._buf) - 32:
                if self._buf[idx] == 0x20 and self._buf[idx + 1] == 0x40:
                    with self._lock:
                        self.total_frames += 1
                    candidate = bytes(self._buf[idx : idx + 32])
                    if self._verify_checksum(candidate):
                        latest_frame = candidate
                        with self._lock:
                            self.valid_frames += 1
                        idx += 32
                    else:
                        with self._lock:
                            self.checksum_errors += 1
                        idx += 1
                else:
                    idx += 1

            if idx > 0:
                del self._buf[:idx]

            if latest_frame is not None:
                with self._lock:
                    self._unpack_frame(latest_frame)
                    self.last_frame_time = now

        except Exception as exc:
            logger.error("Error reading iBUS serial data: %s", exc)

    def _verify_checksum(self, frame: bytes) -> bool:
        """16-bit summation checksum algorithm: 0xFFFF - sum(first 30 bytes)."""
        chk_sum = 0xFFFF - sum(frame[0:30])
        frame_chk = frame[30] | (frame[31] << 8)
        return chk_sum == frame_chk

    def _unpack_frame(self, frame: bytes) -> None:
        """Unpacks 14 channel values (microseconds 1000..2000) from 32-byte payload."""
        for ch in range(14):
            offset = 2 + (ch * 2)
            val = frame[offset] | (frame[offset + 1] << 8)
            # Clamp valid RC pulse range
            if 800 <= val <= 2200:
                self.channels[ch + 1] = val

    def feed_bytes_for_testing(self, frame_bytes: bytes) -> bool:
        """Test helper to directly process a raw 32-byte iBUS frame."""
        if len(frame_bytes) != 32 or frame_bytes[0] != 0x20 or frame_bytes[1] != 0x40:
            return False
        with self._lock:
            self.total_frames += 1
        if self._verify_checksum(frame_bytes):
            with self._lock:
                self._unpack_frame(frame_bytes)
                self.last_frame_time = time.monotonic()
                self.valid_frames += 1
            return True
        else:
            with self._lock:
                self.checksum_errors += 1
            return False

    def close(self) -> None:
        """Clean shutdown handler releasing GPIO and Serial resources."""
        if self._cb:
            try:
                self._cb.cancel()
            except Exception:
                pass
            self._cb = None

        if self._handle is not None and HAS_LGPIO:
            if self.pin is not None:
                try:
                    lgpio.gpio_free(self._handle, self.pin)
                except Exception:
                    pass
            try:
                lgpio.gpiochip_close(self._handle)
                logger.info("i-BUS decoder on GPIO %s closed.", self.pin)
            except Exception as exc:
                logger.warning("Error closing lgpio handle: %s", exc)
            finally:
                self._handle = None

        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                logger.info("iBUS serial port closed.")
            except Exception as exc:
                logger.warning("Error closing serial port: %s", exc)
            finally:
                self.ser = None
