# Soak test procedure

A 24 hour unattended run that checks the clock stays locked, measures how much the crystal's rate moves, and
records how far the internet cross-check wanders when nothing is wrong.

## Setup

- GPS shield wired as in SETUP.md, antenna at a window, a fix held before the start.
- chrony selecting `PPS` (`#*` in `chronyc sources`), internet servers online as the cross-check.
- `gps-verdict.service` running, logging every state change and a heartbeat every 5 minutes, each entry
  chained and signed.
- Leave the bench alone for the whole run. A moved wire shows up in the log, which is useful and also ends
  the run as a clean baseline.

## What gets recorded

Each heartbeat carries the verdict, chrony's frequency correction and residual, the system clock offset, the
pulse's reach and error, the worst gap between the satellite source and the internet servers, the board
temperature, and the ESP32's crystal reading.

## Pass criteria

Set from the first run on 2026-09-17 to 18, so they describe this hardware on this bench rather than a
standard.

| check | pass |
|---|---|
| verdict | `LOCKED` for the whole run, with every other state explained by a logged action |
| log integrity | `verify_log.py` reports the chain intact and every entry signed |
| system clock offset | under 1 microsecond at every heartbeat |
| satellite against internet servers | every sample under the 50 ms `UNTRUSTED` threshold |

## After the run

```
python3 service/verify_log.py <log> service/device_key.pub
python3 tools/plot_soak.py <log> <out.png> <start of the untouched window, UTC>
```

## First run, 2026-09-17 21:16 to 2026-09-18 21:23 Toronto time

**Passed on every criterion.** 294 entries, chain intact, all signed. The clean window is 267 heartbeats from
22:47 onward, after the day's deliberate tests finished.

| measure | result |
|---|---|
| verdict | `LOCKED` for all 267 heartbeats, 23 hours without a state change |
| system clock offset | median 71 ns, worst 744 ns |
| crystal rate | 7.40 to 8.04 ppm fast, hourly means 7.65 to 7.89 |
| residual after correction | median 0.002 ppm, worst 0.087 ppm |
| board temperature | 44.65 to 49.60 C, hourly means 46.3 to 48.0 |
| rate against temperature | -0.087 ppm per degree, r = -0.54 |
| satellite against servers | median 6.2 ms, 95th percentile 8.5 ms, worst 12.9 ms |
| ESP32 crystal | 31.59 to 33.00 ppm |

### What it showed

The processor holds the board at 46 to 48 C whatever the room does, so the day barely reaches the crystal. The
night is visible but faint: the coolest hour, 03:00, is also when the crystal ran fastest.

**Most of the rate's movement happens inside each hour**, 0.26 to 0.64 ppm, against 0.24 ppm between the
hourly means. That fits the holdover results: 12 microseconds over 14 minutes, 577 microseconds over 70, with
the learned correction going stale at minute scale as load heats and cools the board.

The worst healthy disagreement with the internet servers in 23 hours was 12.9 ms, so the 50 ms threshold sits
about four times above anything the network produced on its own.

![soak](logs/soak_2026-09-18.png)
