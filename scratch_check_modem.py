import serial
import time

commands = [
    b"AT\r\n",
    b"AT+CGNSXTRA=?\r\n",
    b"AT+CGPSAUTO=?\r\n",
    b"AT+CGPSMODE=?\r\n",
    b"AT+CGPSHOT\r\n",
    b"AT+CGPSWARM\r\n",
    b"AT+CGNSSINFO\r\n",
]

ser = serial.Serial("/dev/ttyUSB2", 115200, timeout=2)
for cmd in commands:
    ser.write(cmd)
    time.sleep(0.5)
    resp = ser.read(ser.in_waiting or 256).decode("ascii", errors="replace")
    print("CMD:", cmd.strip().decode())
    print("RESP:", repr(resp))
    print("-" * 40)
ser.close()
