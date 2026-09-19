# reads the CAP lines and reports how much each timestamping path wobbles
import sys, statistics

rows = []
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    parts = line.split()
    if len(parts) == 5 and parts[0] == "CAP":
        try:
            rows.append((int(parts[2]), int(parts[3]), int(parts[4])))
        except ValueError:
            continue

hardwareIntervals = []
cpuIntervals = []
for first, second in zip(rows, rows[1:]):
    if second[0] - first[0] != 1:
        continue
    hardwareIntervals.append((second[1] - first[1]) & 0xFFFFFFFF)
    cpuIntervals.append((second[2] - first[2]) & 0xFFFFFFFF)

# the cpu counter runs at 240 MHz and the capture counter at 80 MHz, so three cpu cycles is one capture tick
relative = [cpu / 3.0 - hardware for cpu, hardware in zip(cpuIntervals, hardwareIntervals)]

print(f"pulses                 {len(rows)}, intervals {len(hardwareIntervals)}")
print(f"hardware median        {statistics.median(hardwareIntervals):.0f} ticks, {(statistics.median(hardwareIntervals)-80_000_000)/80.0:+.2f} ppm")
print(f"hardware jitter stdev  {statistics.stdev(hardwareIntervals)*12.5:.0f} ns")
print(f"hardware worst swing   {(max(hardwareIntervals)-min(hardwareIntervals))*12.5:.0f} ns")
print(f"software median        {statistics.median(cpuIntervals):.0f} cycles, {(statistics.median(cpuIntervals)-240_000_000)/240.0:+.2f} ppm")
print(f"software jitter stdev  {statistics.stdev(cpuIntervals)/0.24:.0f} ns")
print(f"software worst swing   {(max(cpuIntervals)-min(cpuIntervals))/0.24:.0f} ns")
print(f"software against hardware, same edge:")
print(f"  median offset        {statistics.median(relative)*12.5:+.0f} ns")
print(f"  stdev                {statistics.stdev(relative)*12.5:.0f} ns")
print(f"  worst                {min(relative)*12.5:+.0f} to {max(relative)*12.5:+.0f} ns")
print(f"ratio of the two jitters {statistics.stdev(cpuIntervals)/0.24 / (statistics.stdev(hardwareIntervals)*12.5):.1f}x")
