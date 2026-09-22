"""
Probe signal on GPIO 22: check logic level, edge counts, and pulse widths.
"""
import time
import lgpio

CHIP = 0
PIN = 22

try:
    h = lgpio.gpiochip_open(CHIP)
    lgpio.gpio_claim_input(h, PIN)
    val = lgpio.gpio_read(h, PIN)
    print(f"GPIO {PIN} initial level: {val}")

    # Set up alert callback
    edges = []
    def callback(chip, gpio, level, timestamp):
        edges.append((timestamp, level))

    cb = lgpio.callback(h, PIN, lgpio.BOTH_EDGES, callback)

    print("Sampling for 2.0 seconds...")
    time.sleep(2.0)
    cb.cancel()
    lgpio.gpiochip_close(h)

    print(f"Total edges recorded: {len(edges)}")
    if len(edges) > 0:
        print("First 10 edges:")
        for i, (ts, lvl) in enumerate(edges[:10]):
            dt = (ts - edges[i-1][0]) / 1000.0 if i > 0 else 0
            print(f"  {i}: level={lvl}, dt={dt:.2f}us, ts={ts}")
    else:
        print("No edges detected. Receiver may be unpowered, disconnected, transmitter off, or pin held static.")

except Exception as e:
    print(f"Error: {e}")
