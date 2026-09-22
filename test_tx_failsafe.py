import urllib.request
import json
import time
import smbus2

PCA_ADDR = 0x40
try:
    bus = smbus2.SMBus(1)
except Exception:
    bus = None

def get_telemetry():
    try:
        with urllib.request.urlopen("http://localhost:8000/api/telemetry", timeout=1.0) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return None

def read_pca9685_pwm():
    if bus is None:
        return None, None
    try:
        # Channel 0 (Left)
        off0 = bus.read_byte_data(PCA_ADDR, 0x08) | (bus.read_byte_data(PCA_ADDR, 0x09) << 8)
        # Channel 1 (Right)
        off1 = bus.read_byte_data(PCA_ADDR, 0x0C) | (bus.read_byte_data(PCA_ADDR, 0x0D) << 8)
        return round(off0 * 4.8828, 1), round(off1 * 4.8828, 1)
    except Exception:
        return None, None

print("="*65)
print("GENEX ASV — RC TX ON / MAX AGE / TX OFF / FAILSAFE MEASUREMENT")
print("="*65)

# 1. Warm up & verify TX is ON
data = get_telemetry()
if not data:
    print("ERROR: Cannot connect to http://localhost:8000/api/telemetry")
    exit(1)

rc = data["rc"]
if not rc["connected"] or rc["signal_health"] != "HEALTHY":
    print(f"WARNING: Transmitter appears not healthy: connected={rc['connected']}, health={rc['signal_health']}, age={rc['data_age_seconds']}s")
else:
    print(f"SUCCESS: Transmitter is ON and HEALTHY. valid_frames={rc['valid_frames']}, age={rc['data_age_seconds']}s")

print("\n--- PHASE 1: RECORDING FRAME AGE (TX ON) ---")
print("Collecting samples for 10 seconds to determine baseline and maximum frame age...")

samples = []
max_age = 0.0
min_age = 999.0
t_start = time.time()
last_report = t_start

while time.time() - t_start < 10.0:
    t_now = time.time()
    data = get_telemetry()
    if data:
        rc = data["rc"]
        age = rc["data_age_seconds"]
        vf = rc["valid_frames"]
        ch1 = rc["ch1_raw"]
        ch3 = rc["ch3_raw"]
        ch5 = rc["ch5_raw"]
        samples.append((t_now, age, vf, ch1, ch3, ch5))
        if age > max_age:
            max_age = age
        if age < min_age:
            min_age = age

        if t_now - last_report >= 1.0:
            print(f"  [TX ON] t={t_now-t_start:4.1f}s | valid_frames={vf:5d} | age={age:5.3f}s | max_age={max_age:5.3f}s | CH1={ch1} CH3={ch3} CH5={ch5}")
            last_report = t_now
    time.sleep(0.04)

avg_age = sum(s[1] for s in samples) / len(samples) if samples else 0.0
print("\n" + "="*65)
print("PHASE 1 RESULTS (TX ON):")
print(f"  Total samples collected: {len(samples)}")
print(f"  Minimum frame age:       {min_age:.3f} s")
print(f"  Average frame age:       {avg_age:.3f} s")
print(f"  MAXIMUM FRAME AGE:       {max_age:.3f} s")
print("="*65)

print("\n--- PHASE 2: AWAITING TRANSMITTER POWER-OFF ---")
print(">>> PLEASE TURN OFF THE FLYSKY TRANSMITTER NOW <<<")
print("Monitoring for signal cessation and failsafe engagement...")

tx_off_detected = False
t_tx_off = None
last_valid_frames = samples[-1][2] if samples else 0
last_frame_mono = data["rc"]["last_frame_monotonic"] if data else time.monotonic()
failsafe_triggered = False
t_failsafe_detected = None
t_failsafe_from_last_frame = None
pwm_1500_detected = False
t_pwm_1500_from_last_frame = None

wait_start = time.time()
while time.time() - wait_start < 40.0:
    loop_t = time.time()
    data = get_telemetry()
    if not data:
        time.sleep(0.02)
        continue

    rc = data["rc"]
    mc = data["manual_control"]
    mot = data["motors"]
    hw_l, hw_r = read_pca9685_pwm()

    cur_vf = rc["valid_frames"]
    cur_age = rc["data_age_seconds"]
    cur_health = rc["signal_health"]
    cur_fs = rc["failsafe_active"]
    cur_state = mc["state"]
    cur_lpwm = mot["left_pwm_us"]
    cur_rpwm = mot["right_pwm_us"]

    # Detect TX power off: valid_frames stops incrementing and age exceeds (max_age + 0.4s)
    if not tx_off_detected:
        if cur_vf == last_valid_frames and cur_age > (max(max_age, 0.4) + 0.3):
            tx_off_detected = True
            t_tx_off = loop_t
            last_frame_mono = rc["last_frame_monotonic"]
            print(f"\n[EVENT] TX POWER-OFF DETECTED! (Frame age reached {cur_age:.3f}s at valid_frames={cur_vf})")
            print(f"  Tracking exact delay to failsafe and PWM neutral (1500 µs)...")
        else:
            last_valid_frames = cur_vf
            if int(loop_t * 2) % 2 == 0:
                print(f"  Waiting for TX OFF... current age={cur_age:.3f}s, valid_frames={cur_vf}", end="\r")

    if tx_off_detected:
        t_since_last_frame = cur_age

        if cur_fs and not failsafe_triggered:
            failsafe_triggered = True
            t_failsafe_detected = loop_t
            t_failsafe_from_last_frame = cur_age
            print(f"\n[EVENT] FAILSAFE ENGAGED:")
            print(f"  Signal Health:      {cur_health}")
            print(f"  Failsafe Active:    {cur_fs}")
            print(f"  Controller State:   {cur_state}")
            print(f"  Time until failsafe (from last valid frame): {t_failsafe_from_last_frame:.3f} s")

        is_pwm_neutral = (cur_lpwm == 1500.0 and cur_rpwm == 1500.0)
        is_hw_neutral = (hw_l is None or abs(hw_l - 1500.0) < 5.0) and (hw_r is None or abs(hw_r - 1500.0) < 5.0)

        if is_pwm_neutral and is_hw_neutral and not pwm_1500_detected and failsafe_triggered:
            pwm_1500_detected = True
            t_pwm_1500_from_last_frame = cur_age
            print(f"\n[EVENT] PWM NEUTRAL (1500 µs) CONFIRMED:")
            print(f"  Telemetry Left PWM:   {cur_lpwm} µs")
            print(f"  Telemetry Right PWM:  {cur_rpwm} µs")
            print(f"  PCA9685 Hardware CH0: {hw_l} µs")
            print(f"  PCA9685 Hardware CH1: {hw_r} µs")
            print(f"  Time until PWM = 1500 (from last valid frame): {t_pwm_1500_from_last_frame:.3f} s")
            break

    time.sleep(0.03)

print("\n" + "="*65)
print("FINAL TEST MEASUREMENT SUMMARY:")
print("="*65)
print(f"1. TX ON Baseline:")
print(f"   - Minimum frame age:                     {min_age:.3f} s")
print(f"   - Average frame age:                     {avg_age:.3f} s")
print(f"   - MAXIMUM FRAME AGE RECORDED (TX ON):    {max_age:.3f} s")
print(f"2. TX OFF Failsafe Response:")
print(f"   - TIME UNTIL FAILSAFE:                   {t_failsafe_from_last_frame if t_failsafe_from_last_frame else 'N/A'} s")
print(f"   - TIME UNTIL PWM = 1500 µs:              {t_pwm_1500_from_last_frame if t_pwm_1500_from_last_frame else 'N/A'} s")
print(f"   - Final PCA9685 Hardware Registers:     CH0={hw_l} µs, CH1={hw_r} µs")
print("="*65)
