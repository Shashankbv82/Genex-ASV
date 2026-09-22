import time
import urllib.request
import json
import smbus2
from backend.hardware.i2c_lock import i2c1_lock

def get_pca_ticks():
    try:
        with i2c1_lock:
            bus = smbus2.SMBus(1)
            ch0 = bus.read_i2c_block_data(0x40, 0x06, 4)
            ch1 = bus.read_i2c_block_data(0x40, 0x0A, 4)
            bus.close()
        t0 = ch0[2] | (ch0[3] << 8)
        t1 = ch1[2] | (ch1[3] << 8)
        return t0, t1
    except Exception as e:
        return -1, -1

def trace(samples=10, interval=1.0):
    print('========================================================================================================================')
    print('  GENEX ASV — RUNTIME MANUAL CONTROL SIGNAL TRACE (2 Hz)')
    print('========================================================================================================================')
    print(f'{"TIME":<8} | {"CH1":<5} {"CH3":<5} {"CH5":<5} | {"STR":<6} {"THR":<6} | {"L_CMD":<6} {"R_CMD":<6} | {"L_PWM":<7} {"R_PWM":<7} | {"PCA_CH0":<7} {"PCA_CH1":<7} | {"STATE":<12} {"AGE":<6}')
    print('-'*120)

    for i in range(samples):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/api/telemetry', timeout=1.0) as resp:
                data = json.loads(resp.read().decode())
            
            rc = data.get('rc', {})
            mc = data.get('manual_control', {})
            mot = data.get('motors', {})
            t0, t1 = get_pca_ticks()

            t_str = f'{time.monotonic():.1f}'
            ch1 = str(rc.get('ch1_raw') or '--')
            ch3 = str(rc.get('ch3_raw') or '--')
            ch5 = str(rc.get('ch5_raw') or '--')
            n_str = f"{rc.get('normalized_steering', 0.0):+.2f}"
            n_thr = f"{rc.get('normalized_throttle', 0.0):.2f}"
            l_out = f"{mot.get('left_output', 0.0):+.2f}"
            r_out = f"{mot.get('right_output', 0.0):+.2f}"
            l_pwm = f"{mot.get('left_pwm_us', 1500.0):.1f}"
            r_pwm = f"{mot.get('right_pwm_us', 1500.0):.1f}"
            pca0 = f"{t0}t"
            pca1 = f"{t1}t"
            st = mc.get('state', 'UNKNOWN')
            age = f"{rc.get('data_age_seconds', 999.0):.2f}s"

            print(f'{t_str:<8} | {ch1:<5} {ch3:<5} {ch5:<5} | {n_str:<6} {n_thr:<6} | {l_out:<6} {r_out:<6} | {l_pwm:<7} {r_pwm:<7} | {pca0:<7} {pca1:<7} | {st:<12} {age:<6}')
        except Exception as exc:
            print(f'Error reading telemetry: {exc}')

        time.sleep(interval)

if __name__ == '__main__':
    trace(samples=5, interval=1.0)
