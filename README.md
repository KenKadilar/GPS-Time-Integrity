# GPS Time Integrity

![tests](https://github.com/KenKadilar/GPS-Time-Integrity/actions/workflows/ci.yml/badge.svg)

A Raspberry Pi 5 disciplined to GPS, cross-checked against internet time servers, with a service that decides
whether the clock can be trusted and writes every verdict into a signed, hash chained log.

Built 2026-09-17 on a Raspberry Pi 5 and an ESP32, with a Whadda WPSH456 NEO-6M GPS shield.

## What it does

- Takes time from the GPS receiver two ways: the text sentences over a serial port, and the once a second pulse
  on a GPIO pin.
- Disciplines the system clock with chrony, using the pulse for the instant and the sentences for which second.
- Keeps four internet time servers as an independent cross-check.
- Runs `verdict_service.py`, which every five seconds decides one of `WARMING`, `LOCKED`, `HOLDOVER` or
  `UNTRUSTED`, and appends each change to `verdict_log.jsonl`.
- Chains each log entry to the previous one by SHA-256 and signs it with an Ed25519 key held on the device, so
  an edited or forged log fails `verify_log.py`.
- Measures an ESP32's crystal against the same pulse, as an independent oscillator under test.

## Measured results

All figures measured on 2026-09-17, logs in `logs/`.

| what | result |
|---|---|
| clock offset while locked | tens of nanoseconds, chrony estimating the pulse at +/- 400 ns |
| the Pi's crystal | 7.86 ppm fast, which is 679 ms a day uncorrected |
| holdover, 14 minutes without the antenna | 12 microseconds of accumulated error |
| holdover, 70 minutes without the pulse | 577 microseconds, so the error grows faster than a straight line |
| the ESP32's crystal | 32.1 ppm fast, 1 microsecond of jitter between readings |
| the GPS receiver's own crystal, with no fix | about 30 ppm |
| cold start to first fix, indoors at a window | 11 minutes |
| hot restart after 14 blind minutes | fix in 9 seconds, pulse in 16 |
| internet servers against the pulse, healthy | 1.8 ms to 12.6 ms |
| a 120 second spoof | detected, `satelliteVersusServersWorst 119.997858` |

## How the spoof detection works

Every offset chrony reports is measured against the system clock, so subtracting two of them removes the clock
from the question:

```
(GPS - clock) - (server - clock) = GPS - server
```

The service compares the satellite source against each internet server and calls `UNTRUSTED` when the largest
gap passes 50 ms, a threshold set at about five times the worst healthy disagreement measured here.

Comparing each source against the system clock instead fails exactly when it matters, because a spoof that
drags the clock along makes the honest servers look like the liars.

### What the spoof test showed

A spoofed text source drags the honest hardware pulse with it. The pulse carries no date, so it takes its
second number from the sentences. During the test the pulse itself was arriving within 400 nanoseconds and
reporting a time 120 seconds wrong.

`tools/spoof_shm_time.py` writes a chosen offset into the gpsd shared memory unit that chrony reads, which is
the interface a spoofed receiver's time arrives through. Nothing is transmitted over the air.

## Layout

```
firmware/pps_crystal/   ESP32 firmware, measures its crystal against the pulse
service/                the verdict service, its systemd unit, key generation and the log checker
tools/                  the spoof injector and an NMEA time shifter
logs/                   measurements from the 2026-09-17 build
```

## Hardware

| part | note |
|---|---|
| Raspberry Pi 5, 1 GB | Debian 13, kernel 6.18 |
| Whadda WPSH456 NEO-6M GPS shield | 5 pin header broken out, jumpered so the antenna reaches a window |
| ESP32 DOIT DevKit V1 | pulse on GPIO 4, USB to the Pi |
| TP-Link TL-SG1005D | 5 port gigabit switch, for the PTP work |

Wiring, shield J3 to the Pi's 40 pin header: 5V to pin 2, GND to pin 6, TXD to pin 10, RXD to pin 8, PPS to
pin 12.

## Setup on the Pi

```
sudo apt install gpsd gpsd-clients chrony pps-tools
```

`/boot/firmware/config.txt`:

```
dtoverlay=uart0-pi5
dtoverlay=pps-rp1,pin=18
```

`/etc/default/gpsd`:

```
DEVICES="/dev/ttyAMA0"
GPSD_OPTIONS="-n"
```

`/etc/chrony/conf.d/gps.conf`:

```
refclock SHM 0 refid NMEA offset 0.119 delay 0.2 poll 3 noselect
refclock PPS /dev/pps0 refid PPS lock NMEA prefer poll 2
```

Then:

```
sudo systemctl enable gpsd.service
python3 service/make_device_key.py
sudo cp service/gps-verdict.service /etc/systemd/system/
sudo systemctl enable --now gps-verdict
```

### Notes that cost time

- On a Pi 5 the UART on GPIO 14 and 15 is off by default and `dtoverlay=uart0-pi5` enables it. Setting
  `enable_uart=1` instead routes kernel logging onto those pins when no debug cable is attached.
- The GPS pulse device number depends on boot order, since the Ethernet port's PTP clock also registers one.
  Match on `/sys/class/pps/pps*/name` rather than assuming `pps0`.
- The gpsd package enables only `gpsd.socket`, which starts the daemon when a client connects. chrony reads
  shared memory rather than connecting, so `gpsd.service` needs enabling for the chain to survive a reboot.
- The text sentences arrive about 119 ms after the second they describe, measured at 9600 baud. chrony needs
  that as `offset`, and `noselect` keeps a late source from steering the clock.
- gpsd shared memory units 0 and 1 are root only, 2 and up are for a gpsd running as an ordinary user.

## Tests

```
pytest tests -v
```

Ten tests, run by GitHub Actions on every push, none of them needing the hardware.

The decision tests feed the logic source tables taken from real runs, including the 120 second spoof and the
12.6 ms of healthy network noise, so the threshold is tested against both sides of the line. One test covers
the defect that the spoof found: chrony leaves its star on the last reference it used, so a stale pulse reads
`LOCKED` unless the check also asks when the last sample arrived.

The log tests build a small signed log with a throwaway key, then attack it: an edited entry, a forgery that
rebuilds every fingerprint correctly, and a log signed by a different device. The first breaks the chain, the
other two break the signature.

## Checking a log

```
python3 service/verify_log.py logs/verdict_log_signed_2026-09-17.jsonl service/device_key.pub
```

The public key is in the repository. The private key stays on the device at mode 600, which means the
guarantee is that entries were signed by something holding that file. A secure element would raise that bar,
since the key could then never be exported.
