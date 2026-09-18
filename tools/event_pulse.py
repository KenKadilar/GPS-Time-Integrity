"""fires a shared event on a Pi GPIO and records when it fired, so both ESP32s can be lined up against it"""

import subprocess
import sys
import time

eventGpio = 17
holdSeconds = 0.01
repeats = 5
gapSeconds = 3.0

if len(sys.argv) > 1:
    repeats = int(sys.argv[1])


def setPin(level):
    state = "dl"
    if level == 1:
        state = "dh"
    subprocess.run(["pinctrl", "set", str(eventGpio), "op", state], check=True)


setPin(0)
print("event  pi_unix_time  pi_offset_into_second_us")

fired = 0
while fired < repeats:
    fired += 1
    firedAt = time.time()
    setPin(1)
    time.sleep(holdSeconds)
    setPin(0)
    offsetIntoSecond = (firedAt % 1) * 1000000
    print("%d  %.6f  %.0f" % (fired, firedAt, offsetIntoSecond))
    time.sleep(gapSeconds)

setPin(0)
