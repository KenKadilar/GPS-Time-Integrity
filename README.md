# GPS Time Integrity

![tests](https://github.com/KenKadilar/GPS-Time-Integrity/actions/workflows/ci.yml/badge.svg)

A Raspberry Pi that takes the time from GPS satellites, checks it against internet time servers, and raises an
alarm when they disagree.

![The bench setup](setup_photo.jpg)

## Catching a faked receiver

Normal. The GPS pulse and four internet servers all agree, within milliseconds.

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

**The hardware pulse is dragged along with the lie.** It is accurate to 400 nanoseconds and it carries no date,
so it takes its second number from the receiver's text. A perfect pulse then reports a perfect time that is two
minutes wrong.

**The internet servers are what catch it**, because they have no idea the GPS is lying. One reference cannot
catch its own spoof. Two independent ones can.

Every verdict goes into a log where each entry carries the fingerprint of the one before it and a signature
made on the device, so an edited or forged entry fails the checker.

## Measured

| | |
|---|---|
| clock held against the pulse, 23 hours | **71 ns** median |
| drift after the antenna is pulled, 14 minutes | **12 microseconds** |
| the same crystal with nothing correcting it | **679 ms a day** |
| a two minute spoof | **caught** |
| two microcontrollers stamping one shared event | **±1.2 microseconds** apart |
| hardware timestamp against software interrupt | **52 ns** against 420 ns of jitter |

![23 hours locked](logs/soak_2026-09-18.png)

## One thing worth knowing

A client on the network once ran **37 seconds wrong while every part reported healthy.**

Network timing counts every second that has ever passed. Ordinary computers use a clock that pauses for leap
seconds. The two are 37 seconds apart. The server was announcing the first and sending the second, so the
client converted a number that never needed converting.

Nothing was broken. The clock was locked, the network card was holding 127 nanoseconds, and every component was
correct about its own job. No part of it was positioned to compare the two claims against each other, which is
the same gap this project exists to close.

## Running it

- [SETUP.md](SETUP.md), wiring, the Pi configuration and what is easy to get wrong
- [TEST_PROCEDURE.md](TEST_PROCEDURE.md), how each number above was measured
- `pytest tests -v`, ten tests, no hardware needed

Raspberry Pi 5, a Whadda WPSH456 NEO-6M GPS shield, two ESP32 boards and a gigabit switch. Under CAD 100.
