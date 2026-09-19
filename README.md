# GPS Time Integrity

![tests](https://github.com/KenKadilar/GPS-Time-Integrity/actions/workflows/ci.yml/badge.svg)

A Raspberry Pi that takes the time from GPS satellites, checks it against internet time servers, and raises an
alarm when they disagree.

![The bench setup](setup_photo.jpg)

## Catching a faked receiver

The GPS pulse and four internet servers, all agreeing within milliseconds.

```
MS Name/IP address         Stratum Poll Reach LastRx Last sample
#? NMEA                          0   3     7     5  -3438us[-3437us] +/-  100ms
#* PPS                           0   2    77     4   +649ns[+1294ns] +/-  446ns
^- archer.fsck.ca                2   6    17    19  -4056us[ -951us] +/-   11ms
^- ntp.netlinkify.com            2   6    17    19  -5600us[-2827us] +/- 8838us
```

The receiver is then fed a time two minutes wrong. Same command, moments later.

```
#? NMEA  reach 37   -120.1s      the receiver, lying
#* PPS   reach 377  -120.0s      the hardware pulse, carrying the lie
^- tangent.muug.ca  -7740us      the internet server, unmoved
```

```
10 UNTRUSTED | compared against PPS | satellite vs servers 119.997858 s
```

The hardware pulse is accurate to 400 nanoseconds and carries no date, so it takes its second number from the
receiver's text. Shifting that text moves the pulse's reported time with it. The internet servers are
unaffected, which is what makes the disagreement visible.

Each verdict goes into a log where every entry carries the fingerprint of the one before it and a signature
made on the device, so an edited or forged entry fails the checker.

## Measured

| | |
|---|---|
| clock held against the pulse, 23 hours | 71 ns median |
| drift after the antenna is pulled, 14 minutes | 12 microseconds |
| the same crystal with nothing correcting it | 679 ms a day |
| a two minute spoof | caught |
| two microcontrollers stamping one shared event | within 1.2 microseconds |
| hardware timestamp against software interrupt | 52 ns against 420 ns of jitter |

![23 hours locked](logs/soak_2026-09-18.png)

## A 37 second error

PTP runs on a timescale that counts every second that has ever passed. Ordinary computers use one that pauses
for leap seconds. The two are 37 seconds apart.

The grandmaster here announced the first while sending the second, so a client converted a number that had not
needed converting and set its clock 37 seconds behind. chrony was locked to GPS, the network card was holding
127 nanoseconds, and every component reported healthy. No part of the stack compared the two claims against
each other.

## Parts

| part | CAD |
|---|---:|
| Whadda WPSH456 NEO-6M GPS shield, u-blox NEO-6M | 59.95 |
| TP-Link TL-SG1005D gigabit switch | 29.95 |
| two Cat6 patch cables | 5.90 |
| total with tax | 108.25 |

Already owned and used here: a Raspberry Pi 5, two ESP32 DevKit V1 boards, a breadboard and jumpers.

## Running it

- [SETUP.md](SETUP.md), wiring, the Pi configuration and what is easy to get wrong
- [TEST_PROCEDURE.md](TEST_PROCEDURE.md), how each number above was measured
- `pytest tests -v`, ten tests, no hardware needed
