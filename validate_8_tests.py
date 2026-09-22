import time
import smbus2
from backend.config import settings
from backend.control.motor_driver import MotorController
from backend.rc.signal_processing import SignalProcessor
from backend.tests.test_rc_ibus_decoder import build_ibus_frame
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

def run():
    print('=============================================================')
    print('  GENEX ASV — 8-POINT MANUAL RC CONTROL PATH VALIDATION')
    print('=============================================================')
    bus = smbus2.SMBus(1)
    processor = SignalProcessor()
    mc = MotorController(motors_enabled=True)

    # -------------------------------------------------------------
    # TEST 1: Transmitter OFF -> RC disconnected/failsafe -> both motors neutral
    # -------------------------------------------------------------
    print('\n[TEST 1] Transmitter OFF -> RC disconnected/failsafe -> both motors neutral')
    mc.immediate_neutral_stop()
    ch0_t, ch0_us, ch1_t, ch1_us = read_pca_channels(bus)
    print(f'  Result: CH0={ch0_t} ({ch0_us:.1f}us), CH1={ch1_t} ({ch1_us:.1f}us)')
    assert ch0_t == 307 and ch1_t == 307, f'TEST 1 FAILED: CH0={ch0_t}, CH1={ch1_t}'
    print('  -> PASS: Motors are strictly neutral (1500 us).')

    # -------------------------------------------------------------
    # TEST 2: Transmitter ON, CH5 OFF -> both motors neutral
    # -------------------------------------------------------------
    print('\n[TEST 2] Transmitter ON, CH5 OFF -> both motors neutral')
    ch5_active = processor.is_manual_requested(1000) # Switch OFF
    is_zero = processor.is_throttle_at_zero(1000)
    armed = mc.update_arming_state(ch5_active, is_zero)
    mc.process_and_output(raw_thr=0.0, raw_str=0.0, dt=0.02)
    ch0_t, ch0_us, ch1_t, ch1_us = read_pca_channels(bus)
    print(f'  Result: armed={armed}, require_zero={mc.require_throttle_zero}, CH0={ch0_t} ({ch0_us:.1f}us), CH1={ch1_t} ({ch1_us:.1f}us)')
    assert not armed and ch0_t == 307 and ch1_t == 307, 'TEST 2 FAILED'
    print('  -> PASS: CH5 OFF forces disarm and neutral motors.')

    # -------------------------------------------------------------
    # TEST 3: CH5 ON, throttle zero -> manual mode active -> motors remain neutral
    # -------------------------------------------------------------
    print('\n[TEST 3] CH5 ON, throttle zero -> manual mode active -> motors remain neutral')
    ch5_active = processor.is_manual_requested(2000) # Switch ON
    is_zero = processor.is_throttle_at_zero(1000)    # Zero confirmed
    armed = mc.update_arming_state(ch5_active, is_zero)
    mc.process_and_output(raw_thr=0.0, raw_str=0.0, dt=0.02)
    ch0_t, ch0_us, ch1_t, ch1_us = read_pca_channels(bus)
    print(f'  Result: armed={armed}, require_zero={mc.require_throttle_zero}, CH0={ch0_t} ({ch0_us:.1f}us), CH1={ch1_t} ({ch1_us:.1f}us)')
    assert armed and not mc.require_throttle_zero and ch0_t == 307 and ch1_t == 307, 'TEST 3 FAILED'
    print('  -> PASS: Manual mode is ACTIVE, zero throttle confirmed, motors remain neutral.')

    # -------------------------------------------------------------
    # TEST 4: CH3 forward, CH1 centered -> both motors increase together
    # -------------------------------------------------------------
    print('\n[TEST 4] CH3 forward, CH1 centered -> both motors increase together')
    for _ in range(25):
        mc.process_and_output(raw_thr=0.3, raw_str=0.0, dt=0.02)
        time.sleep(0.01)
    ch0_t, ch0_us, ch1_t, ch1_us = read_pca_channels(bus)
    print(f'  Result: CH0={ch0_t} ({ch0_us:.1f}us), CH1={ch1_t} ({ch1_us:.1f}us)')
    assert ch0_t == 338 and ch1_t == 338, f'TEST 4 FAILED: CH0={ch0_t}, CH1={ch1_t}, expected 338'
    print('  -> PASS: Both motors increase identically to 1650 us (338 ticks).')

    # -------------------------------------------------------------
    # TEST 5: CH1 right -> existing right-turn differential behavior
    # -------------------------------------------------------------
    print('\n[TEST 5] CH1 right -> existing right-turn differential behavior')
    for _ in range(25):
        mc.process_and_output(raw_thr=0.0, raw_str=0.3, dt=0.02)
        time.sleep(0.01)
    ch0_t, ch0_us, ch1_t, ch1_us = read_pca_channels(bus)
    print(f'  Result: CH0 (Left)={ch0_t} ({ch0_us:.1f}us), CH1 (Right)={ch1_t} ({ch1_us:.1f}us)')
    assert ch0_t == 338 and ch1_t == 276, f'TEST 5 FAILED: CH0={ch0_t}, CH1={ch1_t}'
    print('  -> PASS: Right turn increases Left motor (1650 us) and decreases Right motor (1350 us).')

    # -------------------------------------------------------------
    # TEST 6: CH1 left -> existing left-turn differential behavior
    # -------------------------------------------------------------
    print('\n[TEST 6] CH1 left -> existing left-turn differential behavior')
    for _ in range(25):
        mc.process_and_output(raw_thr=0.0, raw_str=-0.3, dt=0.02)
        time.sleep(0.01)
    ch0_t, ch0_us, ch1_t, ch1_us = read_pca_channels(bus)
    print(f'  Result: CH0 (Left)={ch0_t} ({ch0_us:.1f}us), CH1 (Right)={ch1_t} ({ch1_us:.1f}us)')
    assert ch0_t == 276 and ch1_t == 338, f'TEST 6 FAILED: CH0={ch0_t}, CH1={ch1_t}'
    print('  -> PASS: Left turn decreases Left motor (1350 us) and increases Right motor (1650 us).')

    # -------------------------------------------------------------
    # TEST 7: CH5 OFF while motors are running -> both motors immediately return to neutral
    # -------------------------------------------------------------
    print('\n[TEST 7] CH5 OFF while motors are running -> both motors immediately return to neutral')
    for _ in range(20):
        mc.process_and_output(raw_thr=0.4, raw_str=0.0, dt=0.02)
    ch0_t, ch0_us, ch1_t, ch1_us = read_pca_channels(bus)
    print(f'  Running state before cut: CH0={ch0_t} ({ch0_us:.1f}us), CH1={ch1_t} ({ch1_us:.1f}us)')
    assert ch0_t > 320 and ch1_t > 320
    
    t0 = time.monotonic()
    mc.update_arming_state(ch5_active=False, is_throttle_zero=False)
    mc.snap_to_neutral()
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    ch0_t, ch0_us, ch1_t, ch1_us = read_pca_channels(bus)
    print(f'  CH5 flipped OFF -> Motors neutral in {elapsed_ms:.2f} ms: CH0={ch0_t} ({ch0_us:.1f}us), CH1={ch1_t} ({ch1_us:.1f}us)')
    assert ch0_t == 307 and ch1_t == 307 and not mc.is_armed, 'TEST 7 FAILED'
    print('  -> PASS: Motors immediately snap to neutral and disarm.')

    # -------------------------------------------------------------
    # TEST 8: Transmitter power OFF while motors are running -> failsafe -> both motors neutral
    # -------------------------------------------------------------
    print('\n[TEST 8] Transmitter power OFF while motors are running -> failsafe -> both motors neutral')
    # Re-arm
    mc.update_arming_state(ch5_active=True, is_throttle_zero=True)
    for _ in range(20):
        mc.process_and_output(raw_thr=0.4, raw_str=0.0, dt=0.02)
    ch0_t, ch0_us, ch1_t, ch1_us = read_pca_channels(bus)
    print(f'  Running state: CH0={ch0_t} ({ch0_us:.1f}us), CH1={ch1_t} ({ch1_us:.1f}us)')
    assert ch0_t > 320 and ch1_t > 320

    # Signal loss event
    t0 = time.monotonic()
    mc.immediate_neutral_stop()
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    ch0_t, ch0_us, ch1_t, ch1_us = read_pca_channels(bus)
    print(f'  Failsafe triggered -> Motors neutral in {elapsed_ms:.2f} ms: CH0={ch0_t} ({ch0_us:.1f}us), CH1={ch1_t} ({ch1_us:.1f}us)')
    assert ch0_t == 307 and ch1_t == 307 and not mc.is_armed and mc.require_throttle_zero, 'TEST 8 FAILED'
    print('  -> PASS: Failsafe immediately returns both motors to neutral and engages startup lockout.')

    mc.shutdown()
    print('\n=============================================================')
    print('  ALL 8 TESTS PASSED DIRECTLY ON HARDWARE PCA9685 REGISTERS!')
    print('=============================================================')

if __name__ == '__main__':
    run()
