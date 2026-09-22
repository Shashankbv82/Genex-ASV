"""
Monitor GPIO 22 for 10 seconds and report edge counts and intervals.
"""
import time
import lgpio

h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_input(h, 22)

edges = []
def cb(chip, gpio, level, tick):
    edges.append((tick, level))

c = lgpio.callback(h, 22, lgpio.BOTH_EDGES, cb)
print("Listening on GPIO 22 for 10 seconds (turn on transmitter or move sticks if on)...")
t0 = time.time()
while time.time() - t0 < 10.0:
    time.sleep(0.5)
    if edges:
        print(f"Edges detected so far: {len(edges)}")

c.cancel()
lgpio.gpiochip_close(h)
print(f"Final edge count: {len(edges)}")
if edges:
    print("Sample edges (first 20):")
    for i, (t, lvl) in enumerate(edges[:20]):
        dt = (t - edges[i-1][0]) if i > 0 else 0
        print(f"  edge {i}: lvl={lvl}, dt={dt/1000.0:.2f}us, tick={t}")
