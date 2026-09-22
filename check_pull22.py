"""
Test if GPIO 22 is externally driven or floating by applying pull-down.
"""
import time
import lgpio

h = lgpio.gpiochip_open(0)
# Test with pull-down
lgpio.gpio_claim_input(h, 22, lgpio.SET_PULL_DOWN)
time.sleep(0.1)
val_down = lgpio.gpio_read(h, 22)

# Test with pull-up
lgpio.gpio_claim_input(h, 22, lgpio.SET_PULL_UP)
time.sleep(0.1)
val_up = lgpio.gpio_read(h, 22)

# Test with no pull (floating)
lgpio.gpio_claim_input(h, 22, lgpio.SET_PULL_NONE)
time.sleep(0.1)
val_none = lgpio.gpio_read(h, 22)

lgpio.gpiochip_close(h)
print(f"GPIO 22: with PULL_DOWN={val_down}, with PULL_UP={val_up}, with PULL_NONE={val_none}")
