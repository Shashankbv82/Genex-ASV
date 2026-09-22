"""
GENEX ASV - System Health Monitor
Reads Raspberry Pi hardware telemetry (CPU temp, throttling, memory, LTE status)
"""

import subprocess
import shutil
import time
from backend.telemetry.state import SystemHealth

_boot_time = time.time()

def get_system_health() -> SystemHealth:
    health = SystemHealth()
    health.uptime_seconds = round(time.time() - _boot_time, 1)

    # 1. CPU Temperature
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_raw = int(f.read().strip())
            health.cpu_temp_c = round(temp_raw / 1000.0, 1)
    except Exception:
        pass

    # 2. Throttled Status
    try:
        res = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=1.0)
        if res.returncode == 0:
            val_str = res.stdout.strip().split("=")[-1]
            health.throttled_hex = val_str
            val = int(val_str, 16)
            if val & 0x1:
                health.throttled_description = "Under-voltage Active"
            elif val & 0x8:
                health.throttled_description = "Thermal Throttling Active"
            elif val == 0:
                health.throttled_description = "Normal"
            else:
                health.throttled_description = f"Flag: {val_str}"
    except Exception:
        pass

    # 3. Memory Stats
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
            mem_dict = {}
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2:
                    k = parts[0].strip()
                    v = parts[1].strip().split()[0]
                    mem_dict[k] = int(v)
            total_kb = mem_dict.get("MemTotal", 0)
            avail_kb = mem_dict.get("MemAvailable", 0)
            used_kb = total_kb - avail_kb
            health.memory_total_mb = round(total_kb / 1024.0, 1)
            health.memory_used_mb = round(used_kb / 1024.0, 1)
    except Exception:
        pass

    # 4. LTE usb0 Interface Status
    try:
        res = subprocess.run(["ip", "-br", "addr", "show", "usb0"], capture_output=True, text=True, timeout=1.0)
        if res.returncode == 0:
            tokens = res.stdout.strip().split()
            if len(tokens) >= 3 and "/" in tokens[2]:
                health.lte_connected = True
                health.lte_ip = tokens[2].split("/")[0]
            else:
                health.lte_connected = False
        else:
            health.lte_connected = False
    except Exception:
        health.lte_connected = False

    return health
