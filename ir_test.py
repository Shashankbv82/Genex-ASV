from gpiozero import DigitalInputDevice
from time import sleep

sensor = DigitalInputDevice(17)

print("IR sensor test started. Press Ctrl+C to stop.")

try:
    while True:
        if sensor.value == 0:
            print("NO OBSTACLe")
        else:
            print("OBSTACLE")

        sleep(0.5)

except KeyboardInterrupt:
    print("\nTest stopped.")

finally:
    sensor.close()
