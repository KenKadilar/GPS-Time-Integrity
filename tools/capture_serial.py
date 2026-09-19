# reads lines off the board and writes each one straight to disk, so a killed run still keeps what it saw
import sys, time

portPath = sys.argv[1]
outPath = sys.argv[2]
runSeconds = float(sys.argv[3])

endAt = time.monotonic() + runSeconds
lineCount = 0
with open(portPath, "rb", buffering=0) as port, open(outPath, "w", encoding="utf-8") as out:
    pending = b""
    while time.monotonic() < endAt:
        chunk = port.read(64)
        if chunk:
            pending += chunk
            while b"\n" in pending:
                one, pending = pending.split(b"\n", 1)
                out.write(one.decode("utf-8", "replace").strip() + "\n")
                out.flush()
                lineCount += 1
print(f"lines {lineCount}")
