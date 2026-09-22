import time
import smbus2
from backend.config import settings
from backend.control.motor_driver import MotorController
from backend.rc.signal_processing import SignalProcessor
from backend.hardware.i2c_lock import i2c1_lock

def read_pca_channels(bus):
    with i2c1_lock:
        ch0 = bus.read_i2c_block_data(0x40, 0x06, 4)
        ch1 = bus.read_i2c_block_data(0x40, 0x0A, 4)
    ch0_ticks = ch0[2] | (ch0[3] << 8)
    ch1_ticks = ch1[2] | (ch1[3] << 8)
    ch0_us = (ch0_ticks / 4095.0) * 20000.0
    ch1_us = (ch1_ticks / 4095.0) * 20000.0
    return ch0_ticks, ch0_us, ch1_ticks, ch1_us

def run_audit():
    print('======================================================================')
    print('  GENEX ASV - DUAL-MOTOR ACTUATION & SAFETY INTERLOCK AUDIT')
    print('======================================================================')
    bus = smbus2.SMBus(1)
    processor = SignalProcessor()
    mc = MotorController(motors_enabled=True)

    # 1. Zero Throttle Startup Interlock Test
    print('\n[TEST 1] Zero-Throttle Arming Interlock Verification')
    # Try arming with non-zero throttle (CH3 = 1400)
    ch5_active = processor.is_manual_requested(2000)
    is_zero = processor.is_throttle_at_zero(1400)
    armed = mc.update_arming_state(ch5_active, is_zero)
    t0_ticks, t0_us, t1_ticks, t1_us = read_pca_channels(bus)
    print(f'Attempting arm with CH5=2000, CH3=1400 -> is_armed={armed}, require_zero={mc.require_throttle_zero}')
    print(f'PCA9685 Register State: CH0={t0_ticks} ({t0_us:.1f}us), CH1={t1_ticks} ({t1_us:.1f}us)')
    assert not armed, 'FAILED: MotorController must not arm when throttle is not zero!'
    assert t0_ticks == 307 and t1_ticks == 307, 'FAILED: Hardware PWM must remain neutral (307 ticks)!'
    print('PASS: Zero-throttle startup lockout successfully blocked arming.')

    # Now confirm zero throttle (CH3 = 1000)
    is_zero = processor.is_throttle_at_zero(1000)
    armed = mc.update_arming_state(ch5_active, is_zero)
    print(f'Arming with CH5=2000, CH3=1000 (idle zero) -> is_armed={armed}')
    assert armed, 'FAILED: Vehicle must arm when throttle is confirmed zero!'
    print('PASS: Arming successfully confirmed upon throttle zeroing.')

    # 2. Forward Throttle Sweep (1500, 1550, 1600, 1650, 1700 us)
    print('\n[TEST 2] Symmetric Forward Throttle Sweep (CH0 Left + CH1 Right)')
    test_pwms = [1500, 1550, 1600, 1650, 1700]
    for target_pwm in test_pwms:
        # Map target_pwm back to raw CH3 pulse:
        # norm_thr = (target_pwm - 1500) / 500
        # raw CH3 in main piecewise zone: raw = 1200 + (norm_thr - 0.15) / 0.85 * 800
        norm_thr = max(0.0, (target_pwm - 1500.0) / 500.0)
        norm_str = 0.0 # Straight ahead

        # Run multiple steps to let rate-limiter settle
        for _ in range(30):
            mc.process_and_output(norm_thr, norm_str, dt=0.02)
            time.sleep(0.01)

        t0_ticks, t0_us, t1_ticks, t1_us = read_pca_channels(bus)
        exp_ticks = int(round((target_pwm / 20000.0) * 4095))
        diff0 = abs(t0_ticks - exp_ticks)
        diff1 = abs(t1_ticks - exp_ticks)
        print(f'Target: {target_pwm} us | CH0 (Left): {t0_ticks} ticks ({t0_us:.1f} us) | CH1 (Right): {t1_ticks} ticks ({t1_us:.1f} us) | Delta: CH0={diff0}t, CH1={diff1}t')
        assert diff0 <= 1 and diff1 <= 1, f'FAILED: Mismatch at {target_pwm} us (CH0={t0_ticks}, CH1={t1_ticks}, exp={exp_ticks})'
    print('PASS: Both motors respond identically and symmetrically across entire throttle sweep.')

    # 3. Differential Steering Tests (1650/1350 and 1350/1650)
    print('\n[TEST 3] Differential Steering Tests')
    # Scenario A: Right Turn (Left motor faster, Right motor slower)
    norm_thr = 0.0 # center around neutral for clear differential, or with forward throttle
    # Throttle = 0.0, Steering = +0.3 (Right):
    # Mixer: left = +0.3, right = -0.3
    # Left PWM = 1500 + 0.3*500 = 1650 us, Right PWM = 1500 - 0.3*500 = 1350 us
    norm_thr = 0.0
    norm_str = 0.3 # Turn Right
    for _ in range(30):
        mc.process_and_output(norm_thr, norm_str, dt=0.02)
        time.sleep(0.01)

    t0_ticks, t0_us, t1_ticks, t1_us = read_pca_channels(bus)
    print(f'Steering RIGHT (+0.3) -> Target: CH0=1650us, CH1=1350us | Actual: CH0={t0_us:.1f}us ({t0_ticks}t), CH1={t1_us:.1f}us ({t1_ticks}t)')
    assert abs(t0_us - 1650.0) < 5.0 and abs(t1_us - 1350.0) < 5.0, 'FAILED: Differential Right turn mismatch!'
    print('PASS: Differential turn RIGHT produced correct left=1650us, right=1350us.')

    # Scenario B: Left Turn (Left motor slower, Right motor faster)
    norm_str = -0.3 # Turn Left
    for _ in range(30):
        mc.process_and_output(norm_thr, norm_str, dt=0.02)
        time.sleep(0.01)

    t0_ticks, t0_us, t1_ticks, t1_us = read_pca_channels(bus)
    print(f'Steering LEFT (-0.3) -> Target: CH0=1350us, CH1=1650us | Actual: CH0={t0_us:.1f}us ({t0_ticks}t), CH1={t1_us:.1f}us ({t1_ticks}t)')
    assert abs(t0_us - 1350.0) < 5.0 and abs(t1_us - 1650.0) < 5.0, 'FAILED: Differential Left turn mismatch!'
    print('PASS: Differential turn LEFT produced correct left=1350us, right=1650us.')

    # 4. CH5 Switch OFF Immediate Neutralization Test
    print('\n[TEST 4] CH5 Switch OFF Immediate Motor Neutralization')
    # First drive motors forward to 1700 us
    for _ in range(30):
        mc.process_and_output(0.4, 0.0, dt=0.02)
    t0_ticks, t0_us, t1_ticks, t1_us = read_pca_channels(bus)
    print(f'Motors running at active thrust: CH0={t0_us:.1f}us, CH1={t1_us:.1f}us')
    assert t0_ticks > 320 and t1_ticks > 320

    t_start = time.monotonic()
    # User flips CH5 switch OFF:
    mc.update_arming_state(ch5_active=False, is_throttle_zero=False)
    mc.snap_to_neutral()
    t_snap = (time.monotonic() - t_start) * 1000.0

    t0_ticks, t0_us, t1_ticks, t1_us = read_pca_channels(bus)
    print(f'CH5 flipped OFF -> Hardware snapped to Neutral in {t_snap:.2f} ms')
    print(f'Actual PCA9685 State: CH0={t0_ticks} ({t0_us:.1f}us), CH1={t1_ticks} ({t1_us:.1f}us)')
    assert t0_ticks == 307 and t1_ticks == 307, 'FAILED: Motors did not snap to 307 ticks!'
    assert not mc.is_armed and mc.require_throttle_zero, 'FAILED: Controller must require zero throttle to rearm!'
    print('PASS: CH5 switch OFF immediately and atomically neutralizes BOTH motors to 1500 us and engages lockout.')

    # Clean shutdown
    mc.shutdown()
    print('\n======================================================================')
    print('  AUDIT COMPLETE: ALL MOTOR ACTUATION & SAFETY INTERLOCKS VERIFIED!')
    print('======================================================================')

if __name__ == '__main__':
    run_audit()
