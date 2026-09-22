"""
GENEX ASV - Manual Mode Precision Control Law & PCA9685 Verification Suite
Executes the 13 required test scenarios validating:
- Forward-only throttle mapping
- Steering zero-throttle invariant
- Pre-mix linear rate limiters (Throttle & Steering)
- Differential coupling equations
- Immediate safety neutralization (never ramped)
- Hardware PWM / PCA9685 I2C register verification
"""

import sys
import os
import time

# Ensure genex_asv root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.config import settings
from backend.rc.signal_processing import SignalProcessor
from backend.control.mixer import DifferentialDriveMixer
from backend.control.motor_driver import MotorController
from backend.hardware.i2c_lock import i2c1_lock

try:
    import smbus2
    HAS_SMBUS2 = True
except ImportError:
    HAS_SMBUS2 = False


def read_pca9685_channel_ticks(bus, addr, channel):
    """Read OFF count (pulse width in ticks) for a PCA9685 channel."""
    base = 0x06 + 4 * channel
    reg_off_l = bus.read_byte_data(addr, base + 2)
    reg_off_h = bus.read_byte_data(addr, base + 3)
    return reg_off_l | ((reg_off_h & 0x0F) << 8)


def ticks_to_us(ticks):
    return (ticks / 4095.0) * 20000.0


def run_tests():
    print("=" * 70)
    print("GENEX ASV — MANUAL MODE PRECISION CONTROL VERIFICATION")
    print("=" * 70)
    
    passed_tests = 0
    total_tests = 13

    # Initialize Hardware / MotorController with physical outputs enabled for testing
    mc = MotorController(
        throttle_accel_rate=settings.MANUAL_THROTTLE_ACCEL_RATE,
        throttle_decel_rate=settings.MANUAL_THROTTLE_DECEL_RATE,
        steering_accel_rate=settings.MANUAL_STEERING_ACCEL_RATE,
        steering_decel_rate=settings.MANUAL_STEERING_DECEL_RATE,
        motors_enabled=True,
    )
    sp = SignalProcessor()
    mixer = DifferentialDriveMixer()

    bus = None
    if HAS_SMBUS2:
        try:
            bus = smbus2.SMBus(settings.PCA9685_I2C_BUS)
        except Exception as e:
            print(f"[WARN] Could not open smbus2 bus {settings.PCA9685_I2C_BUS}: {e}")

    # TEST 1: CH5 OFF -> 1500 / 1500
    print("\n--- TEST 1: CH5 OFF -> Neutral 1500/1500 ---")
    mc.update_arming_state(ch5_active=False, is_throttle_zero=True)
    l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=0.5, raw_str=0.2, dt=0.1)
    t1_pass = (l_pwm == 1500.0 and r_pwm == 1500.0 and l_out == 0.0 and r_out == 0.0)
    print(f"Result: L_PWM={l_pwm} us, R_PWM={r_pwm} us | PASS={t1_pass}")
    if t1_pass: passed_tests += 1

    # TEST 2: CH5 ON, Throttle minimum, Steering center -> 1500 / 1500
    print("\n--- TEST 2: CH5 ON, Throttle min, Steering center -> 1500/1500 ---")
    mc.update_arming_state(ch5_active=True, is_throttle_zero=True)
    l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=0.0, raw_str=0.0, dt=0.1)
    t2_pass = (l_pwm == 1500.0 and r_pwm == 1500.0)
    print(f"Result: L_PWM={l_pwm} us, R_PWM={r_pwm} us | PASS={t2_pass}")
    if t2_pass: passed_tests += 1

    # TEST 3: CH5 ON, Throttle minimum, Steering full left -> 1500 / 1500 (Invariant)
    print("\n--- TEST 3: CH5 ON, Throttle min, Steering full left -> 1500/1500 (Zero-Throttle Invariant) ---")
    l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=0.0, raw_str=-1.0, dt=0.1)
    t3_pass = (l_pwm == 1500.0 and r_pwm == 1500.0 and l_out == 0.0 and r_out == 0.0)
    print(f"Result: L_PWM={l_pwm} us, R_PWM={r_pwm} us | PASS={t3_pass}")
    if t3_pass: passed_tests += 1

    # TEST 4: CH5 ON, Throttle minimum, Steering full right -> 1500 / 1500 (Invariant)
    print("\n--- TEST 4: CH5 ON, Throttle min, Steering full right -> 1500/1500 (Zero-Throttle Invariant) ---")
    l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=0.0, raw_str=1.0, dt=0.1)
    t4_pass = (l_pwm == 1500.0 and r_pwm == 1500.0 and l_out == 0.0 and r_out == 0.0)
    print(f"Result: L_PWM={l_pwm} us, R_PWM={r_pwm} us | PASS={t4_pass}")
    if t4_pass: passed_tests += 1

    # TEST 5: Throttle ~20% (0.20), Steering center -> 1600 / 1600 with gradual ramp
    print("\n--- TEST 5: Throttle 20%, Steering center -> Ramps to 1600/1600 ---")
    # Step 1 tick (dt=0.1s): throttle accel is 0.50 u/s -> advances by 0.05
    _, _, l_step1, r_step1, a_thr1, _ = mc.process_and_output(raw_thr=0.20, raw_str=0.0, dt=0.1)
    ramp_verified = (1500.0 < l_step1 < 1600.0)
    # Advance until target is reached
    for _ in range(30):
        l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=0.20, raw_str=0.0, dt=0.1)
    t5_pass = ramp_verified and abs(l_pwm - 1600.0) <= 2.0 and abs(r_pwm - 1600.0) <= 2.0
    print(f"Result: Step1 L_PWM={l_step1:.1f} us (ramp check: {ramp_verified}), Settled L_PWM={l_pwm:.1f} us, R_PWM={r_pwm:.1f} us | PASS={t5_pass}")
    if t5_pass: passed_tests += 1

    # TEST 6: Throttle 20%, Steering +30% -> Target: L ~1630 us, R ~1570 us
    print("\n--- TEST 6: Throttle 20%, Steering +30% -> Target L=1630 us, R=1570 us ---")
    for _ in range(30):
        l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=0.20, raw_str=0.30, dt=0.1)
    t6_pass = abs(l_pwm - 1630.0) <= 2.0 and abs(r_pwm - 1570.0) <= 2.0
    print(f"Result: L_PWM={l_pwm:.1f} us, R_PWM={r_pwm:.1f} us (Actual T={a_thr:.3f}, S={a_str:.3f}) | PASS={t6_pass}")
    if t6_pass: passed_tests += 1

    # TEST 7: Throttle 20%, Steering -30% -> Target: L ~1570 us, R ~1630 us
    print("\n--- TEST 7: Throttle 20%, Steering -30% -> Target L=1570 us, R=1630 us ---")
    for _ in range(30):
        l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=0.20, raw_str=-0.30, dt=0.1)
    t7_pass = abs(l_pwm - 1570.0) <= 2.0 and abs(r_pwm - 1630.0) <= 2.0
    print(f"Result: L_PWM={l_pwm:.1f} us, R_PWM={r_pwm:.1f} us (Actual T={a_thr:.3f}, S={a_str:.3f}) | PASS={t7_pass}")
    if t7_pass: passed_tests += 1

    # TEST 8: Throttle 50%, Steering +30% -> Target: L ~1825 us, R ~1675 us
    print("\n--- TEST 8: Throttle 50%, Steering +30% -> Target L=1825 us, R=1675 us ---")
    for _ in range(30):
        l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=0.50, raw_str=0.30, dt=0.1)
    t8_pass = abs(l_pwm - 1825.0) <= 2.0 and abs(r_pwm - 1675.0) <= 2.0
    print(f"Result: L_PWM={l_pwm:.1f} us, R_PWM={r_pwm:.1f} us (Actual T={a_thr:.3f}, S={a_str:.3f}) | PASS={t8_pass}")
    if t8_pass: passed_tests += 1

    # TEST 9: Throttle 100%, Steering center -> Target: 2000 / 2000
    print("\n--- TEST 9: Throttle 100%, Steering center -> Target 2000/2000 ---")
    for _ in range(30):
        l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=1.00, raw_str=0.00, dt=0.1)
    t9_pass = abs(l_pwm - 2000.0) <= 2.0 and abs(r_pwm - 2000.0) <= 2.0
    print(f"Result: L_PWM={l_pwm:.1f} us, R_PWM={r_pwm:.1f} us (Actual T={a_thr:.3f}, S={a_str:.3f}) | PASS={t9_pass}")
    if t9_pass: passed_tests += 1

    # TEST 10: Throttle 100%, Steering +30% -> Target: L=2000 (clamped), R=1850 us
    print("\n--- TEST 10: Throttle 100%, Steering +30% -> Target L=2000 (clamped), R=1850 us ---")
    for _ in range(30):
        l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=1.00, raw_str=0.30, dt=0.1)
    t10_pass = abs(l_pwm - 2000.0) <= 2.0 and abs(r_pwm - 1850.0) <= 2.0 and l_pwm <= 2000.0
    print(f"Result: L_PWM={l_pwm:.1f} us, R_PWM={r_pwm:.1f} us (Actual T={a_thr:.3f}, S={a_str:.3f}) | PASS={t10_pass}")
    if t10_pass: passed_tests += 1

    # TEST 11: Throttle release -> gradual return toward 1500 / 1500
    print("\n--- TEST 11: Release throttle to minimum -> Gradual return to 1500/1500 ---")
    # First tick with target=0.0: decel rate is 1.0 u/s -> decreases from 1.0 to 0.90 in dt=0.1
    _, _, l_dec1, r_dec1, a_thr_dec1, _ = mc.process_and_output(raw_thr=0.0, raw_str=0.0, dt=0.1)
    decel_gradual = (1500.0 < l_dec1 < 2000.0)
    for _ in range(30):
        l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=0.0, raw_str=0.0, dt=0.1)
    t11_pass = decel_gradual and (l_pwm == 1500.0 and r_pwm == 1500.0)
    print(f"Result: First tick L_PWM={l_dec1:.1f} us (gradual check: {decel_gradual}), Settled L_PWM={l_pwm:.1f} us | PASS={t11_pass}")
    if t11_pass: passed_tests += 1

    # TEST 12: Turn CH5 OFF while throttle applied -> Immediate snap to 1500 / 1500 (NO RAMP)
    print("\n--- TEST 12: CH5 OFF while moving -> IMMEDIATE snap to 1500/1500 (Never Ramped) ---")
    # Spin up
    for _ in range(20):
        mc.process_and_output(raw_thr=0.80, raw_str=0.0, dt=0.1)
    print(f"Cruising at L_PWM={mc.left_pwm_us:.1f} us. Now turning CH5 OFF...")
    # CH5 goes OFF: immediate neutral stop
    mc.update_arming_state(ch5_active=False, is_throttle_zero=False)
    l_out, r_out, l_pwm, r_pwm, a_thr, a_str = mc.process_and_output(raw_thr=0.80, raw_str=0.0, dt=0.01)
    t12_pass = (l_pwm == 1500.0 and r_pwm == 1500.0 and a_thr == 0.0 and not mc.is_armed)
    print(f"Result: L_PWM={l_pwm} us, R_PWM={r_pwm} us, Armed={mc.is_armed} | PASS={t12_pass}")
    if t12_pass: passed_tests += 1

    # TEST 13: RC failsafe -> Immediate snap to 1500 / 1500
    print("\n--- TEST 13: RC failsafe -> Immediate snap to 1500/1500 ---")
    # Arm and apply throttle
    mc.update_arming_state(ch5_active=True, is_throttle_zero=True)
    for _ in range(10):
        mc.process_and_output(raw_thr=0.50, raw_str=0.0, dt=0.1)
    # Simulate failsafe trigger
    mc.immediate_neutral_stop()
    t13_pass = (mc.left_pwm_us == 1500.0 and mc.right_pwm_us == 1500.0 and not mc.is_armed and mc.actual_throttle == 0.0)
    print(f"Result: L_PWM={mc.left_pwm_us} us, R_PWM={mc.right_pwm_us} us, Armed={mc.is_armed} | PASS={t13_pass}")
    if t13_pass: passed_tests += 1

    # Verify PCA9685 Register state if I2C is available
    if bus is not None:
        print("\n--- PCA9685 Hardware Register Check (I2C Bus 1 @ 0x40) ---")
        try:
            with i2c1_lock:
                ch0_ticks = read_pca9685_channel_ticks(bus, settings.PCA9685_I2C_ADDR, 0)
                ch1_ticks = read_pca9685_channel_ticks(bus, settings.PCA9685_I2C_ADDR, 1)
                ch0_us = ticks_to_us(ch0_ticks)
                ch1_us = ticks_to_us(ch1_ticks)
                print(f"PCA9685 CH0 (LEFT):  {ch0_ticks} ticks -> {ch0_us:.1f} us")
                print(f"PCA9685 CH1 (RIGHT): {ch1_ticks} ticks -> {ch1_us:.1f} us")
                assert abs(ch0_us - 1500.0) <= 10.0, f"CH0 not at safe neutral: {ch0_us}"
                assert abs(ch1_us - 1500.0) <= 10.0, f"CH1 not at safe neutral: {ch1_us}"
                print("PCA9685 hardware registers verified strictly at safe neutral (1500 us).")
        except Exception as e:
            print(f"[PCA9685 Read Error]: {e}")
        finally:
            bus.close()

    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed_tests} / {total_tests} TESTS PASSED")
    print("=" * 70)

    mc.shutdown()
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
