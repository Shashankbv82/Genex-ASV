import time
import smbus2
from backend.config import settings
from backend.control.manual_controller import ManualModeController
from backend.rc.reader import rc_reader
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

def run_failsafe_test():
    print('======================================================================')
    print('  GENEX ASV - TRANSMITTER POWER-OFF FAILSAFE LATENCY AUDIT')
    print('======================================================================')
    bus = smbus2.SMBus(1)
    
    # 1. Start RCReader and ManualModeController
    rc_reader.start()
    ctrl = ManualModeController()
    ctrl.motor_controller.motors_enabled = True
    ctrl.start()

    zero_frame = build_ibus_frame([1500, 1500, 1000, 1500, 2000] + [1500]*9)
    active_frame = build_ibus_frame([1500, 1500, 1600, 1500, 2000] + [1500]*9)

    print('\nStep 1: Arming vehicle with zero throttle frame...')
    for _ in range(15):
        rc_reader.decoder.feed_bytes_for_testing(zero_frame)
        time.sleep(0.01)

    status = ctrl.get_manual_status()
    print(f'Manual status: state={status.state}, armed={ctrl.motor_controller.is_armed}')
    assert status.state == 'ACTIVE' and ctrl.motor_controller.is_armed, f'Arming failed: state={status.state}'
    print('PASS: Armed and ready.')

    print('\nStep 2: Sending active throttle frames (CH3=1600 us, target=1600 us PWM)...')
    for _ in range(25):
        rc_reader.decoder.feed_bytes_for_testing(active_frame)
        time.sleep(0.01)

    t0_ticks, t0_us, t1_ticks, t1_us = read_pca_channels(bus)
    print(f'Motors active: CH0={t0_ticks} ({t0_us:.1f}us), CH1={t1_ticks} ({t1_us:.1f}us)')
    assert t0_ticks > 320 and t1_ticks > 320, 'Motors did not actuate!'
    print('PASS: Both motors actively driving at forward throttle.')

    print('\nStep 3: Simulating TRANSMITTER POWER-OFF (stopping all RC frames)...')
    t_poweroff = time.monotonic()
    t_failsafe_detected = None
    
    while time.monotonic() - t_poweroff < 2.0:
        time.sleep(0.005)
        st = ctrl.get_manual_status()
        t0_ticks, t0_us, t1_ticks, t1_us = read_pca_channels(bus)
        if st.state in ('FAILSAFE', 'DISCONNECTED') and t0_ticks == 307 and t1_ticks == 307:
            t_failsafe_detected = time.monotonic()
            break

    assert t_failsafe_detected is not None, 'FAILED: Failsafe did not engage within 2.0 seconds!'
    shutdown_latency_ms = (t_failsafe_detected - t_poweroff) * 1000.0

    print(f'>>> FAILSAFE TRIGGERED! Shutdown Latency: {shutdown_latency_ms:.1f} ms <<<')
    print(f'Final State={st.state}, lockout_reason={st.lockout_reason}')
    print(f'Verified PCA9685 Registers: CH0={t0_ticks} ({t0_us:.1f}us), CH1={t1_ticks} ({t1_us:.1f}us)')
    assert shutdown_latency_ms <= 400.0, f'FAILED: Shutdown latency {shutdown_latency_ms:.1f}ms exceeds 400ms target!'
    print(f'PASS: Transmitter OFF shutdown latency ({shutdown_latency_ms:.1f} ms) is within 400ms safety requirement.')

    ctrl.stop()
    rc_reader.stop()
    print('\n======================================================================')
    print('  FAILSAFE AUDIT COMPLETE: DUAL-MOTOR SHUTDOWN VERIFIED!')
    print('======================================================================')

if __name__ == '__main__':
    run_failsafe_test()
