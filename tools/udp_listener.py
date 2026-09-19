"""receives the ESP32 reports over UDP and logs each one with the Pi's own receive time"""

import socket
import sys
import time

listenPort = 5005
logPath = "/home/pi/gps_timing/two_board_log.txt"
if len(sys.argv) > 1:
    logPath = sys.argv[1]

receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
receiver.bind(("0.0.0.0", listenPort))
print("listening on UDP %d, writing %s" % (listenPort, logPath))

with open(logPath, "a", encoding="utf-8", buffering=1) as handle:
    while True:
        payload, sender = receiver.recvfrom(512)
        receivedAt = time.time()
        text = payload.decode("ascii", "ignore").strip()
        row = "%.6f %s %s" % (receivedAt, sender[0], text)
        handle.write(row + "\n")
        if text.startswith("EVENT") or text.startswith("board"):
            print(row)
