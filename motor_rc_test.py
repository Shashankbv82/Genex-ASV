import time
import signal
import sys
import importlib.util

import smbus2


# ============================================================
# LOAD IBUS DECODER DIRECTLY
# ============================================================

spec = importlib.util.spec_from_file_location(
    "ibus_decoder",
    "/home/southpolexp1/genex_asv/backend/rc/ibus_decoder.py"
)

ibus_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ibus_module)

IBusDecoder = ibus_module.IBusDecoder


# ============================================================
# CONFIG
# ============================================================

RC_GPIO = 22

PCA_ADDR = 0x40
PCA_BUS = 1

LEFT_CH = 0
RIGHT_CH = 1

NEUTRAL = 1500
MIN_PWM = 1000
MAX_PWM = 2000

running = True


# ============================================================
# SIGNAL HANDLER
# ============================================================

def stop(signum, frame):
    global running
    running = False


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)


# ============================================================
# PCA9685
# ============================================================

class PCA9685:

    def __init__(self):

        self.bus = smbus2.SMBus(PCA_BUS)

        # 50 Hz
        old_mode = self.bus.read_byte_data(
            PCA_ADDR,
            0x00
        )

        self.bus.write_byte_data(
            PCA_ADDR,
            0x00,
            (old_mode & 0x7F) | 0x10
        )

        prescale = int(
            round(
                25_000_000 /
                (4096 * 50)
            ) - 1
        )

        self.bus.write_byte_data(
            PCA_ADDR,
            0xFE,
            prescale
        )

        self.bus.write_byte_data(
            PCA_ADDR,
            0x00,
            old_mode & 0xEF
        )

        time.sleep(0.005)

        self.bus.write_byte_data(
            PCA_ADDR,
            0x00,
            0x20
        )

        self.bus.write_byte_data(
            PCA_ADDR,
            0x01,
            0x04
        )

    def us_to_ticks(self, us):

        us = max(
            MIN_PWM,
            min(MAX_PWM, us)
        )

        return int(
            round(
                us * 4096 * 50 / 1_000_000
            )
        )

    def set_both(self, left_us, right_us):

        left = self.us_to_ticks(left_us)
        right = self.us_to_ticks(right_us)

        payload = [
            0,
            0,
            left & 0xFF,
            (left >> 8) & 0x0F,

            0,
            0,
            right & 0xFF,
            (right >> 8) & 0x0F,
        ]

        self.bus.write_i2c_block_data(
            PCA_ADDR,
            0x06,
            payload
        )

    def neutral(self):

        self.set_both(
            NEUTRAL,
            NEUTRAL
        )

    def close(self):

        try:
            self.neutral()
        finally:
            self.bus.close()


# ============================================================
# RC MAPPING
# ============================================================

def throttle(ch3):

    if ch3 <= 1050:
        return 0.0

    return max(
        0.0,
        min(
            1.0,
            (ch3 - 1050) / 950.0
        )
    )


def steering(ch1):

    if abs(ch1 - 1500) <= 50:
        return 0.0

    return max(
        -1.0,
        min(
            1.0,
            (ch1 - 1500) / 500.0
        )
    )


def pwm_from_normalized(value):

    value = max(
        -1.0,
        min(1.0, value)
    )

    return 1500 + value * 500


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 55)
    print("GENEX ASV - STANDALONE RC MOTOR TEST")
    print("=" * 55)
    print("GPIO22 : FlySky i-BUS")
    print("CH1    : Steering")
    print("CH3    : Forward throttle")
    print("CH5    : Enable")
    print("PCA9685 CH0 : LEFT")
    print("PCA9685 CH1 : RIGHT")
    print("=" * 55)
    print()

    pwm = None
    decoder = None

    try:

        # -----------------------------------------------
        # PCA9685
        # -----------------------------------------------

        pwm = PCA9685()

        pwm.neutral()

        print("PCA9685 initialized.")
        print("ESCs forced to 1500 / 1500 us.")

        # -----------------------------------------------
        # i-BUS
        # -----------------------------------------------

        decoder = IBusDecoder(
            pin=RC_GPIO,
            chip=0,
            baudrate=115200,
            failsafe_timeout=0.50
        )

        if not decoder.open():

            print("ERROR: Could not open i-BUS.")

            return 1

        print("i-BUS decoder started.")
        print()
        print("Keep CH5 OFF and throttle at minimum.")
        print("Waiting for transmitter...")
        print()

        last_display = 0

        while running:

            channels, age, healthy = (
                decoder.read_channels()
            )

            # -------------------------------------------
            # FAILSAFE
            # -------------------------------------------

            if not healthy:

                pwm.neutral()

                now = time.monotonic()

                if now - last_display > 0.5:

                    print(
                        "FAILSAFE | "
                        "age=%.3fs | "
                        "PWM=1500 / 1500"
                        % age
                    )

                    last_display = now

                time.sleep(0.01)

                continue

            ch1 = channels[1]
            ch3 = channels[3]
            ch5 = channels[5]

            # -------------------------------------------
            # CH5 OFF
            # -------------------------------------------

            if ch5 is None or ch5 < 1500:

                pwm.neutral()

                now = time.monotonic()

                if now - last_display > 0.5:

                    print(
                        "DISARMED | "
                        "CH1=%d CH3=%d CH5=%d | "
                        "PWM=1500 / 1500"
                        % (ch1, ch3, ch5)
                    )

                    last_display = now

                time.sleep(0.01)

                continue

            # -------------------------------------------
            # ACTIVE RC
            # -------------------------------------------

            t = throttle(ch3)
            s = steering(ch1)

            left = max(
                -1.0,
                min(1.0, t + s)
            )

            right = max(
                -1.0,
                min(1.0, t - s)
            )

            left_pwm = pwm_from_normalized(left)
            right_pwm = pwm_from_normalized(right)

            pwm.set_both(
                left_pwm,
                right_pwm
            )

            now = time.monotonic()

            if now - last_display > 0.1:

                print(
                    "ACTIVE | "
                    "CH1=%4d CH3=%4d CH5=%4d | "
                    "T=%.2f S=%+.2f | "
                    "LEFT=%7.1f RIGHT=%7.1f"
                    % (
                        ch1,
                        ch3,
                        ch5,
                        t,
                        s,
                        left_pwm,
                        right_pwm
                    )
                )

                last_display = now

            time.sleep(0.01)

    except Exception as e:

        print()
        print("ERROR:")
        print(e)

        return 1

    finally:

        print()
        print("FORCING BOTH ESCs TO 1500 us...")

        if pwm:

            try:
                pwm.neutral()
            except Exception:
                pass

        if decoder:

            try:
                decoder.close()
            except Exception:
                pass

        if pwm:

            try:
                pwm.close()
            except Exception:
                pass

        print("Test stopped safely.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
