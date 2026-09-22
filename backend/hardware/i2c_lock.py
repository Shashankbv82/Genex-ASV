"""
GENEX ASV - Shared I2C Bus Mutex
Prevents concurrent transaction collisions on Linux /dev/i2c-1
between PCA9685 PWM controller (0x40) and BNO055 IMU (0x28).
"""

import threading

# Reentrant lock for /dev/i2c-1 access
i2c1_lock = threading.RLock()
