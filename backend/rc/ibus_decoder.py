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
import os
import queue
import subprocess
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
        failsafe_timeout: float = 1.00,
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
        self.last_frame_recv_time: float = 0.0
        self.last_frame_decoded_time: float = 0.0
        self.frame_ready_event = threading.Event()
        self.total_frames: int = 0
        self.valid_frames: int = 0
        self.checksum_errors: int = 0

        # Serial stream buffer
        self._buf = bytearray()

        # GPIO edge stream buffer
        self._edge_buf: List[Tuple[int, int]] = []
        self._last_edge_ns: int = 0
        self._frame_queue: queue.Queue = queue.Queue(maxsize=20)
        self._worker_thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None
        self._running: bool = False

    def open(self) -> bool:
        """Initialize iBUS input: prefer GPIO if pin is configured, else open serial."""
        if self.pin is not None:
            return self._open_gpio()
        return self._open_serial()

    def _open_gpio(self) -> bool:
        """Open BCM GPIO line for i-BUS decoding via native helper or lgpio fallback."""
        bin_paths = [
            os.path.join(os.path.dirname(__file__), "ibus_reader"),
            "/home/southpolexp1/genex_asv/backend/rc/ibus_reader",
        ]
        chosen_bin = None
        for bp in bin_paths:
            if os.path.isfile(bp) and os.access(bp, os.X_OK):
                chosen_bin = bp
                break

        if chosen_bin is not None:
            try:
                logger.info("Launching native C i-BUS reader on GPIO %d: %s", self.pin, chosen_bin)
                self._proc = subprocess.Popen(
                    [chosen_bin, str(self.pin)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0
                )
                self._running = True
                self._worker_thread = threading.Thread(
                    target=self._native_read_worker,
                    name="IBusNativeWorker",
                    daemon=True
                )
                self._worker_thread.start()
                logger.info("Native C i-BUS reader registered successfully on BCM GPIO %d.", self.pin)
                return True
            except Exception as exc:
                logger.warning("Failed to launch native i-BUS reader (%s): %s. Falling back to lgpio.", chosen_bin, exc)

        return self._open_gpio_lgpio()

    def _native_read_worker(self) -> None:
        """Streams verified 32-byte frames from native C reader process."""
        while self._running and self._proc and self._proc.poll() is None:
            try:
                raw_32 = self._proc.stdout.read(32)
                if not raw_32 or len(raw_32) != 32:
                    time.sleep(0.005)
                    continue

                if raw_32[0] != 0x20 or raw_32[1] != 0x40:
                    continue

                if not self._verify_checksum(raw_32):
                    with self._lock:
                        self.checksum_errors += 1
                    continue

                t_now = time.monotonic()
                with self._lock:
                    self._unpack_frame(raw_32)
                    self.total_frames += 1
                    self.valid_frames += 1
                    self.last_frame_recv_time = t_now
                    self.last_frame_decoded_time = t_now
                    self.last_frame_time = t_now
                    if self.valid_frames == 1 or self.valid_frames % 500 == 0:
                        logger.info(
                            "i-BUS frame locked on GPIO %d: valid=%d [CH1=%s, CH3=%s, CH5=%s]",
                            self.pin,
                            self.valid_frames,
                            self.channels[1],
                            self.channels[3],
                            self.channels[5]
                        )
                self.frame_ready_event.set()

            except Exception as exc:
                logger.error("Error in native i-BUS read worker: %s", exc)
                time.sleep(0.05)

    def _open_gpio_lgpio(self) -> bool:
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

            self._running = True
            self._worker_thread = threading.Thread(
                target=self._decode_worker,
                name="IBusDecoderWorker",
                daemon=True
            )
            self._worker_thread.start()

            self._cb = lgpio.callback(
                self._handle,
                self.pin,
                lgpio.BOTH_EDGES,
                self._edge_callback
            )
            logger.info("i-BUS decoder registered successfully on BCM GPIO %d with worker thread.", self.pin)
            return True
        except Exception as exc:
            logger.warning("Failed to initialize i-BUS on BCM GPIO %d: %s", self.pin, exc)
            self.close()
            return False

    def _decode_worker(self) -> None:
        """Decoupled background worker thread that processes frame edge buffers."""
        while self._running:
            try:
                item = self._frame_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], list):
                    t_recv, f_edges = item
                else:
                    t_recv = time.monotonic()
                    f_edges = item
                self._process_frame_edges(f_edges, t_recv)
            except Exception as exc:
                logger.error("Error in i-BUS decode worker: %s", exc)

    def close(self) -> None:
        """Clean shutdown of native subprocess, GPIO alerts or serial port."""
        self._running = False
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=0.2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.5)

        if self._cb is not None:
            try:
                self._cb.cancel()
            except Exception:
                pass
            self._cb = None

        if self._handle is not None and HAS_LGPIO:
            try:
                lgpio.gpiochip_close(self._handle)
            except Exception:
                pass
            self._handle = None

        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

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
        Accumulates transitions and enqueues completed frame buffers on inter-frame gap.
        Ultra-lightweight: strictly avoids decoding inside callback to prevent GIL lag.
        """
        if self._last_edge_ns == 0:
            self._last_edge_ns = tick
            self._edge_buf.append((tick, level))
            return

        gap_us = (tick - self._last_edge_ns) / 1000.0
        self._last_edge_ns = tick

        # Inter-frame silence gap: At 115200 baud, FS-iA10B inter-frame gap is ~4.9 ms (4900 us).
        # Any gap >= 3500 us cleanly indicates end of frame without false splits.
        if gap_us >= 3500.0:
            if len(self._edge_buf) >= 30:
                frame_edges = self._edge_buf
                t_recv = time.monotonic()
                self._edge_buf = [(tick, level)]
                try:
                    self._frame_queue.put_nowait((t_recv, frame_edges))
                except queue.Full:
                    try:
                        self._frame_queue.get_nowait()
                        self._frame_queue.put_nowait((t_recv, frame_edges))
                    except Exception:
                        pass
            else:
                self._edge_buf = [(tick, level)]
        else:
            if len(self._edge_buf) < 600:
                self._edge_buf.append((tick, level))

    def _process_frame_edges(self, f_edges: List[Tuple[int, int]], t_recv: Optional[float] = None) -> None:
        """Decodes raw frame edges into 32 bytes and verifies i-BUS frame."""
        if t_recv is None:
            t_recv = time.monotonic()

        raw_bytes = self._decode_edges_to_bytes(f_edges)
        if raw_bytes is None or len(raw_bytes) != 32:
            return

        if raw_bytes[0] != 0x20 or raw_bytes[1] != 0x40:
            return

        with self._lock:
            self.total_frames += 1

        candidate = bytes(raw_bytes)
        if self._verify_checksum(candidate):
            t_decoded = time.monotonic()
            with self._lock:
                self._unpack_frame(candidate)
                self.last_frame_recv_time = t_recv
                self.last_frame_decoded_time = t_decoded
                self.last_frame_time = t_decoded
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
            self.frame_ready_event.set()
        else:
            with self._lock:
                self.checksum_errors += 1

    def _decode_edges_to_bytes(self, f_edges: List[Tuple[int, int]]) -> Optional[List[int]]:
        """
        Deserializes 115200 baud UART bytes from edge timestamps using dynamic baud calibration
        from Byte 0 (0x20) and start-bit resynchronization via bisect.
        """
        if len(f_edges) < 30:
            return None

        times = [e[0] for e in f_edges]
        lvls = [e[1] for e in f_edges]

        def get_lvl(t: int) -> int:
            p = bisect.bisect_right(times, t) - 1
            return lvls[p] if p >= 0 else 1

        # Locate initial falling edge of Byte 0 start bit
        idx = 0
        while idx < len(f_edges) and f_edges[idx][1] != 0:
            idx += 1
        if idx >= len(f_edges) - 5:
            return None

        # Dynamically measure baud rate: Byte 0 is 0x20 (0010 0000).
        # Start bit (0) + bits 0..4 (0) = 6 bit periods of LOW before bit 5 (1) rising edge.
        r_idx = idx + 1
        while r_idx < len(f_edges) and f_edges[r_idx][1] != 1:
            r_idx += 1
        if r_idx >= len(f_edges):
            return None

        bit_ns = (f_edges[r_idx][0] - f_edges[idx][0]) / 6.0
        if not (7500.0 <= bit_ns <= 9500.0):
            bit_ns = 8680.555  # Fallback to nominal 115200 baud bit time

        t_cur = f_edges[idx][0]
        bytes_out: List[int] = []

        for b_num in range(32):
            val = 0
            for bit in range(8):
                st = t_cur + int((1.5 + bit) * bit_ns)
                if get_lvl(st):
                    val |= (1 << bit)

            # Early exit on header mismatch saves compute on glitches
            if b_num == 0 and val != 0x20:
                return None
            if b_num == 1 and val != 0x40:
                return None

            bytes_out.append(val)

            if b_num < 31:
                # Look for falling edge of next byte's start bit strictly after stop bit (>= 9.8 bits)
                min_next = t_cur + int(9.8 * bit_ns)
                max_next = t_cur + int(12.5 * bit_ns)
                pos = bisect.bisect_left(times, min_next)
                next_fall = None
                while pos < len(times) and times[pos] <= max_next:
                    if lvls[pos] == 0:
                        next_fall = times[pos]
                        break
                    pos += 1

                if next_fall is not None:
                    t_cur = next_fall
                else:
                    t_cur += int(11.0 * bit_ns)

        if len(bytes_out) == 32:
            chk = 0xFFFF - sum(bytes_out[:30])
            fchk = bytes_out[30] | (bytes_out[31] << 8)
            if chk == fchk:
                return bytes_out

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
