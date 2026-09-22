#!/usr/bin/env python3
"""
GENEX ASV - RC Receiver Hardware Diagnostic Tool
Monitors GPIO 22 (physical pin 15) to detect receiver activity, measure pulse intervals,
and determine whether PPM, i-BUS, or no signal is present.
"""

import time
import sys
import lgpio

GPIO_PIN = 22
CHIP = 0

def run_diagnostic(duration_sec=5.0):
    print("=" * 65)
    print("GENEX ASV — RC RECEIVER HARDWARE DIAGNOSTIC (GPIO 22 / PIN 15)")
    print("=" * 65)

    try:
        h = lgpio.gpiochip_open(CHIP)
    except Exception as e:
        print(f"[FATAL] Cannot open gpiochip {CHIP}: {e}")
        return

    # Check pin initial state
    try:
        lgpio.gpio_claim_input(h, GPIO_PIN)
        initial_val = lgpio.gpio_read(h, GPIO_PIN)
        print(f"[*] GPIO {GPIO_PIN} initial logic level: {initial_val} ({'HIGH (3.3V)' if initial_val else 'LOW (0V)'})")
    except Exception as e:
        print(f"[ERROR] Failed to claim GPIO {GPIO_PIN}: {e}")
        lgpio.gpiochip_close(h)
        return

    edges = []
    def edge_callback(chip, gpio, level, timestamp_ns):
        edges.append((timestamp_ns, level))

    cb = lgpio.callback(h, GPIO_PIN, lgpio.BOTH_EDGES, edge_callback)
    print(f"[*] Monitoring GPIO {GPIO_PIN} for {duration_sec:.1f} seconds...")
    print("    (Please ensure FlySky transmitter is powered ON, bound, and sticks are centered)")
    
    t_start = time.time()
    while time.time() - t_start < duration_sec:
        time.sleep(0.5)
        if edges:
            print(f"    ... captured {len(edges)} edges so far")

    cb.cancel()
    lgpio.gpiochip_close(h)

    print("-" * 65)
    print(f"[*] Total edge transitions captured: {len(edges)}")
    
    if not edges:
        print("\n[RESULT: NO SIGNAL / STATIC LINE]")
        print("  GPIO 22 remained static HIGH (1).")
        print("  Possible causes to investigate:")
        print("  1. FlySky Transmitter is powered OFF (turn ON transmitter).")
        print("  2. Receiver is NOT bound to transmitter (check FS-iA10B LED: solid = bound, flashing = unbound).")
        print("  3. Receiver power (5V & GND) disconnected or unpowered.")
        print("  4. Receiver signal wire connected to wrong pin (ensure it is connected to FS-iA10B CH1/PPM or i-BUS).")
        print("  5. Transmitter Output Mode setting in FS-i6/FS-i6X menu:")
        print("     Go to: Menu -> System -> RX Setup -> Output mode:")
        print("     - For PPM on GPIO 22: Set Output mode to 'PPM'. Connect signal to CH1.")
        print("     - For i-BUS: Set Serial output to 'i-BUS'. (Requires USB-UART on Pi 3).")
        print("=" * 65)
        return

    # Analyze edge transitions
    intervals_us = []
    for i in range(1, len(edges)):
        dt_us = (edges[i][0] - edges[i-1][0]) / 1000.0
        intervals_us.append((dt_us, edges[i][1]))

    print(f"[*] Analyzing {len(intervals_us)} pulse intervals...")
    sync_gaps = [dt for dt, lvl in intervals_us if dt > 3000.0]
    channel_pulses = [dt for dt, lvl in intervals_us if 800.0 <= dt <= 2200.0]
    short_pulses = [dt for dt, lvl in intervals_us if dt < 500.0]

    print(f"    - Pulses in servo/channel range (800 - 2200 us): {len(channel_pulses)}")
    print(f"    - Sync gaps (> 3000 us): {len(sync_gaps)}")
    print(f"    - High-frequency pulses (< 500 us): {len(short_pulses)}")

    if len(sync_gaps) > 2 and len(channel_pulses) > 10:
        avg_sync = sum(sync_gaps) / len(sync_gaps)
        print("\n[RESULT: VALID PPM SIGNAL CONFIRMED!]")
        print(f"  Detected repeated PPM frames with avg sync gap: {avg_sync:.1f} us")
        print(f"  Approx frame rate: {1000.0 / (sum(sync_gaps[:5])/len(sync_gaps[:5]) if sync_gaps else 20.0):.1f} Hz")
    elif len(short_pulses) > 50:
        print("\n[RESULT: HIGH-FREQUENCY SERIAL / i-BUS SIGNAL DETECTED]")
        print("  High-frequency transitions detected. If this is 115,200 baud i-BUS,")
        print("  it requires a hardware UART or USB-UART adapter on Raspberry Pi 3.")
    else:
        print("\n[RESULT: IRREGULAR OR NOISY SIGNAL]")
        print("  Edge transitions do not clearly match standard PPM or i-BUS.")

    print("=" * 65)

if __name__ == "__main__":
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    run_diagnostic(dur)
