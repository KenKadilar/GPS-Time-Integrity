# Setup

Everything needed to rebuild this on a Raspberry Pi 5.

## Hardware

| part | note |
|---|---|
| Raspberry Pi 5, 1 GB | Debian 13, kernel 6.18 |
| Whadda WPSH456 NEO-6M GPS shield | 5 pin header broken out, jumpered so the antenna reaches a window |
| ESP32 DOIT DevKit V1, two of them | pulse on GPIO 4 on both, shared event line on GPIO 18 |
| TP-Link TL-SG1005D | 5 port gigabit switch, for the PTP work |

Shield J3 to the Pi's 40 pin header:

| J3 | Pi pin | what it is |
|---|---|---|
| 5V | 2 | supply |
| GND | 6 | ground |
| TXD | 10 | GPIO 15, the GPS talking |
| RXD | 8 | GPIO 14 |
| PPS | 12 | GPIO 18, the once a second pulse |

The ESP32 boards take the pulse from the same breadboard row and share the Pi's ground.

## The Pi

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

## What is easy to get wrong

**The Pi 5's serial port is off by default.** `dtoverlay=uart0-pi5` turns it on. Using `enable_uart=1` instead
sends kernel logging out of those same pins when no debug cable is attached.

**The pulse device number changes between boots**, because the Ethernet port's own clock registers one too.
Match on `/sys/class/pps/pps*/name` rather than assuming `pps0`.

**The gpsd package only enables `gpsd.socket`**, which starts the daemon when a client connects. chrony reads
shared memory rather than connecting, so `gpsd.service` needs enabling or a reboot leaves the chain dead.

**The text sentences arrive 119 ms after the second they describe**, at 9600 baud. chrony needs that as
`offset`, and `noselect` stops a late source steering the clock.

**gpsd shared memory units 0 and 1 are root only.** Units 2 and up are for a gpsd running as an ordinary user,
which is why `gpsfake` cannot reach chrony.

**A PTP server whose network card holds UTC while its announcement claims TAI puts every client 37 seconds
out.** `phc2sys -O 37` puts TAI in the card, where the announcement already says it is.

**The Pi 5's network card offers only `none` and `all` as receive timestamp filters.** linuxptp asks for a PTP
specific one by default and gets nothing, so it needs `hwts_filter full` before it can answer a delay request.

**Two ESP32 boards with the same chip can have completely different header layouts.** Find pins by the
silkscreen on that board rather than by position.

## The verdict states

| state | the fact behind it |
|---|---|
| `WARMING` | the receiver has no fix yet |
| `LOCKED` | the pulse is the chosen reference and a sample arrived within the last minute |
| `HOLDOVER` | no recent pulse, the clock running on the rate it learned |
| `UNTRUSTED` | the pulse is alive and a server disagrees by more than 50 ms |

The 50 ms threshold is about five times the worst disagreement measured here while healthy.

## How the comparison works

Every offset chrony reports is measured against the system clock, so subtracting two of them removes the clock
from the question:

```
(GPS - clock) - (server - clock) = GPS - server
```

Comparing each source against the system clock instead fails exactly when it matters, because a spoof that
drags the clock along makes the honest servers look like the liars.

`tools/spoof_shm_time.py` writes a chosen offset into the gpsd shared memory unit that chrony reads, which is
the interface a spoofed receiver's time arrives through. Nothing is transmitted over the air.

## Checking a log

```
python3 service/verify_log.py logs/verdict_log_signed_2026-09-17.jsonl service/device_key.pub
```

Each entry carries `prevHash`, its own `hash` over the previous fingerprint plus its contents, and an Ed25519
signature. The chain gives ordering and tamper evidence. The signature gives origin, since a forger who
recomputes every fingerprint correctly still cannot sign.

The public key is in the repository. The private key stays on the device at mode 600, so the guarantee is that
entries were signed by something holding that file. A secure element would raise that bar, since the key could
then never be exported.

A real entry is in [`logs/sample_verdict_entry.json`](logs/sample_verdict_entry.json).

## Tests

```
pytest tests -v
```

Ten tests, run by GitHub Actions on every push, none needing the hardware.

Six feed the decision logic source tables taken from real runs, including the two minute spoof and the 12.6 ms
of healthy network noise, so the threshold is tested against both sides of the line. One covers a defect the
spoof test found: chrony leaves its star on the last reference it used, so a stale pulse reads `LOCKED` unless
the check also asks when the last sample arrived.

Four attack the log: an edited entry, a forgery that rebuilds every fingerprint correctly, and a log signed by
a different device.

## Layout

```
service/                the verdict service, its systemd unit, key generation, the log checker
firmware/pps_crystal/               measures an ESP32 crystal against the pulse
firmware/two_board_event/           two boards stamping one shared event, reporting over WiFi
firmware/capture_vs_interrupt/      one pin stamped by hardware capture and by a software interrupt
tools/                  the AWS publisher, the spoof injector, an NMEA time shifter, listeners and analysers
tools/aws/              the IoT and IAM policy documents used for the cloud path
tests/                  the ten tests
logs/                   every measured run, the soak chart, a sample log entry
```
