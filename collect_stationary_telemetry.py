"""
GENEX ASV - Live Stationary Telemetry Logger and Statistical Analyzer
Records 180 seconds (3 minutes) of live telemetry at 5 Hz from the running backend.
Calculates variances, RMS displacement, mode transitions, and velocity generation.
"""

import urllib.request
import json
import time
import math
import csv
import sys

WGS84_A = 6378137.0

def wgs84_to_enu(lat, lon, lat0, lon0):
    phi0 = math.radians(lat0)
    phi = math.radians(lat)
    lam = math.radians(lon)
    lam0 = math.radians(lon0)
    x_east = (lam - lam0) * math.cos(phi0) * WGS84_A
    y_north = (phi - phi0) * WGS84_A
    return x_east, y_north

DURATION_SEC = 180.0  # 3 minutes
INTERVAL_SEC = 0.20   # 5 Hz
TOTAL_SAMPLES = int(DURATION_SEC / INTERVAL_SEC)

print(f"Starting 3-minute stationary telemetry collection ({TOTAL_SAMPLES} samples at 5 Hz)...")
print("Target: http://127.0.0.1:8000/api/telemetry")

samples = []
start_time = time.monotonic()
next_tick = start_time

lat0 = None
lon0 = None

for i in range(TOTAL_SAMPLES):
    t_now = time.monotonic()
    t_elapsed = t_now - start_time
    
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/api/telemetry", headers={"User-Agent": "StationaryLogger"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"[{t_elapsed:.1f}s] Sample {i+1} fetch failed: {e}")
        time.sleep(INTERVAL_SEC)
        continue

    gps = data.get("gps", {})
    filt = data.get("filtered", {})
    diag = filt.get("diagnostics", {})

    raw_lat = gps.get("latitude")
    raw_lon = gps.get("longitude")
    filt_lat = filt.get("latitude")
    filt_lon = filt.get("longitude")

    if lat0 is None and raw_lat is not None and raw_lon is not None:
        lat0 = raw_lat
        lon0 = raw_lon
        print(f"Reference anchor established: lat0={lat0:.7f}, lon0={lon0:.7f}")

    raw_enu_e, raw_enu_n = (wgs84_to_enu(raw_lat, raw_lon, lat0, lon0) if (raw_lat and raw_lon and lat0) else (0.0, 0.0))
    filt_enu_e, filt_enu_n = (wgs84_to_enu(filt_lat, filt_lon, lat0, lon0) if (filt_lat and filt_lon and lat0) else (0.0, 0.0))

    raw_speed = gps.get("speed_mps") or 0.0
    filt_speed = filt.get("speed_mps") or 0.0
    raw_course = gps.get("course_deg")
    filt_course = filt.get("course_deg")

    # Estimated ENU velocity from filtered speed and course
    if filt_course is not None:
        c_rad = math.radians(filt_course)
        ve = filt_speed * math.sin(c_rad)
        vn = filt_speed * math.cos(c_rad)
    else:
        ve = 0.0
        vn = 0.0

    record = {
        "sample_index": i + 1,
        "t_elapsed_sec": round(t_elapsed, 3),
        "raw_lat": raw_lat,
        "raw_lon": raw_lon,
        "raw_enu_e": round(raw_enu_e, 3),
        "raw_enu_n": round(raw_enu_n, 3),
        "raw_speed_mps": raw_speed,
        "raw_course_deg": raw_course,
        "raw_hdop": gps.get("hdop"),
        "raw_sats": gps.get("satellites_used"),
        "gnss_age_sec": gps.get("data_age_seconds"),
        "filt_lat": filt_lat,
        "filt_lon": filt_lon,
        "filt_enu_e": round(filt_enu_e, 3),
        "filt_enu_n": round(filt_enu_n, 3),
        "filt_speed_mps": filt_speed,
        "filt_course_deg": filt_course,
        "filt_ve": round(ve, 3),
        "filt_vn": round(vn, 3),
        "is_filtered": filt.get("is_filtered"),
        "filter_mode": diag.get("filter_mode"),
        "innovation_dist_m": diag.get("innovation_distance_m"),
        "displacement_m": diag.get("displacement_m"),
        "accepted_count": diag.get("accepted_count"),
        "rejected_count": diag.get("rejected_count"),
        "reseed_count": diag.get("reseed_count"),
        "filter_gnss_age_sec": diag.get("gnss_age_seconds")
    }
    samples.append(record)

    if (i + 1) % 50 == 0 or (i + 1) == TOTAL_SAMPLES:
        print(f"[{t_elapsed:.1f}s] Captured {i+1}/{TOTAL_SAMPLES} samples | Raw spd={raw_speed:.2f}, Filt spd={filt_speed:.2f}, Mode={diag.get('filter_mode')}, Disp={diag.get('displacement_m')}m")

    next_tick += INTERVAL_SEC
    sleep_time = next_tick - time.monotonic()
    if sleep_time > 0:
        time.sleep(sleep_time)

# Save samples to JSON
json_path = "/home/southpolexp1/genex_asv/stationary_telemetry_3min.json"
csv_path = "/home/southpolexp1/genex_asv/stationary_telemetry_3min.csv"

with open(json_path, "w") as f:
    json.dump(samples, f, indent=2)

# Save samples to CSV
if samples:
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(samples[0].keys()))
        writer.writeheader()
        writer.writerows(samples)

print(f"\nCaptured {len(samples)} samples. Saved to {json_path} and {csv_path}")

# ==================== STATISTICAL ANALYSIS ====================
print("\n" + "="*70)
print("STATISTICAL ANALYSIS OF STATIONARY DATA (3 MINUTES @ 5 HZ)")
print("="*70)

valid_raw = [s for s in samples if s["raw_lat"] is not None and s["raw_lon"] is not None]
valid_filt = [s for s in samples if s["filt_lat"] is not None and s["filt_lon"] is not None and s["is_filtered"]]

print(f"Total samples collected: {len(samples)}")
print(f"Valid raw fixes: {len(valid_raw)}")
print(f"Valid filtered fixes: {len(valid_filt)}")

if not valid_raw or not valid_filt:
    print("Insufficient valid samples to compute statistics.")
    sys.exit(0)

# 1. Position Variances and Displacements
raw_e = [s["raw_enu_e"] for s in valid_raw]
raw_n = [s["raw_enu_n"] for s in valid_raw]
filt_e = [s["filt_enu_e"] for s in valid_filt]
filt_n = [s["filt_enu_n"] for s in valid_filt]

mean_raw_e = sum(raw_e) / len(raw_e)
mean_raw_n = sum(raw_n) / len(raw_n)
mean_filt_e = sum(filt_e) / len(filt_e)
mean_filt_n = sum(filt_n) / len(filt_n)

var_raw_e = sum((x - mean_raw_e)**2 for x in raw_e) / len(raw_e)
var_raw_n = sum((y - mean_raw_n)**2 for y in raw_n) / len(raw_n)
var_raw_pos = var_raw_e + var_raw_n

var_filt_e = sum((x - mean_filt_e)**2 for x in filt_e) / len(filt_e)
var_filt_n = sum((y - mean_filt_n)**2 for y in filt_n) / len(filt_n)
var_filt_pos = var_filt_e + var_filt_n

# RMS and Max displacement from anchor (0, 0)
disp_raw = [math.hypot(x, y) for x, y in zip(raw_e, raw_n)]
disp_filt = [math.hypot(x, y) for x, y in zip(filt_e, filt_n)]

rms_disp_raw = math.sqrt(sum(d**2 for d in disp_raw) / len(disp_raw))
rms_disp_filt = math.sqrt(sum(d**2 for d in disp_filt) / len(disp_filt))
max_disp_raw = max(disp_raw)
max_disp_filt = max(disp_filt)

# 2. Speed Statistics
raw_speeds = [s["raw_speed_mps"] for s in valid_raw]
filt_speeds = [s["filt_speed_mps"] for s in valid_filt]

mean_raw_spd = sum(raw_speeds) / len(raw_speeds)
mean_filt_spd = sum(filt_speeds) / len(filt_speeds)
var_raw_spd = sum((s - mean_raw_spd)**2 for s in raw_speeds) / len(raw_speeds)
var_filt_spd = sum((s - mean_filt_spd)**2 for s in filt_speeds) / len(filt_speeds)
max_raw_spd = max(raw_speeds)
max_filt_spd = max(filt_speeds)

# 3. Mode Transitions
modes = [s["filter_mode"] for s in samples]
mode_counts = {}
for m in modes:
    mode_counts[m] = mode_counts.get(m, 0) + 1

mode_transitions = 0
for k in range(1, len(modes)):
    if modes[k] != modes[k-1]:
        mode_transitions += 1

# 4. Accepted and Rejected Counts
acc_counts = [s["accepted_count"] for s in samples if s["accepted_count"] is not None]
rej_counts = [s["rejected_count"] for s in samples if s["rejected_count"] is not None]
total_accepted = acc_counts[-1] - acc_counts[0] if len(acc_counts) > 1 else 0
total_rejected = rej_counts[-1] - rej_counts[0] if len(rej_counts) > 1 else 0

# 5. Internally Generated Velocity
nonzero_speed_count = sum(1 for s in filt_speeds if s > 0.05)
pct_nonzero_speed = (nonzero_speed_count / len(filt_speeds)) * 100.0

print(f"POSITION METRICS:")
print(f"  Raw East Var:        {var_raw_e:.4f} m^2 (Std: {math.sqrt(var_raw_e):.2f} m)")
print(f"  Raw North Var:       {var_raw_n:.4f} m^2 (Std: {math.sqrt(var_raw_n):.2f} m)")
print(f"  Raw 2D Position Var: {var_raw_pos:.4f} m^2 (Std: {math.sqrt(var_raw_pos):.2f} m)")
print(f"  Filtered East Var:   {var_filt_e:.4f} m^2 (Std: {math.sqrt(var_filt_e):.2f} m)")
print(f"  Filtered North Var:  {var_filt_n:.4f} m^2 (Std: {math.sqrt(var_filt_n):.2f} m)")
print(f"  Filtered 2D Pos Var: {var_filt_pos:.4f} m^2 (Std: {math.sqrt(var_filt_pos):.2f} m)")
print(f"  RMS Displacement:    Raw = {rms_disp_raw:.2f} m  ||  Filtered = {rms_disp_filt:.2f} m")
print(f"  Max Displacement:    Raw = {max_disp_raw:.2f} m  ||  Filtered = {max_disp_filt:.2f} m")

print(f"\nSPEED METRICS:")
print(f"  Raw Speed:           Mean = {mean_raw_spd:.3f} m/s, Var = {var_raw_spd:.4f} (m/s)^2, Max = {max_raw_spd:.2f} m/s")
print(f"  Filtered Speed:      Mean = {mean_filt_spd:.3f} m/s, Var = {var_filt_spd:.4f} (m/s)^2, Max = {max_filt_spd:.2f} m/s")
print(f"  Nonzero Speed Pct:   {pct_nonzero_speed:.1f}% of filtered samples had speed > 0.05 m/s")

print(f"\nFILTER OPERATIONAL METRICS:")
print(f"  Filter Modes:        {mode_counts}")
print(f"  Mode Transitions:    {mode_transitions}")
print(f"  Accepted Fixes:      {total_accepted}")
print(f"  Rejected Fixes:      {total_rejected}")

# Output summary dictionary for parsing
summary = {
    "var_raw_pos": round(var_raw_pos, 4),
    "var_filt_pos": round(var_filt_pos, 4),
    "std_raw_pos": round(math.sqrt(var_raw_pos), 3),
    "std_filt_pos": round(math.sqrt(var_filt_pos), 3),
    "mean_raw_spd": round(mean_raw_spd, 3),
    "mean_filt_spd": round(mean_filt_spd, 3),
    "var_raw_spd": round(var_raw_spd, 4),
    "var_filt_spd": round(var_filt_spd, 4),
    "max_raw_spd": round(max_raw_spd, 3),
    "max_filt_spd": round(max_filt_spd, 3),
    "rms_disp_raw": round(rms_disp_raw, 3),
    "rms_disp_filt": round(rms_disp_filt, 3),
    "max_disp_raw": round(max_disp_raw, 3),
    "max_disp_filt": round(max_disp_filt, 3),
    "mode_counts": mode_counts,
    "mode_transitions": mode_transitions,
    "total_accepted": total_accepted,
    "total_rejected": total_rejected,
    "pct_nonzero_speed": round(pct_nonzero_speed, 1)
}

with open("/home/southpolexp1/genex_asv/stationary_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print("\nSummary saved to /home/southpolexp1/genex_asv/stationary_summary.json")
