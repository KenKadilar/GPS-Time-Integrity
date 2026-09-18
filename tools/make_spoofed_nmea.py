"""shifts the time in a recorded NMEA log and fixes each checksum, for a replayed spoofing test"""

import sys

sourcePath = sys.argv[1]
targetPath = sys.argv[2]
shiftSeconds = int(sys.argv[3])

timeFieldBySentence = {"RMC": 1, "GGA": 1, "GLL": 5, "ZDA": 1, "GST": 1}


def shiftedStamp(stamp, shift):
    if len(stamp) < 6:
        return stamp
    hours = int(stamp[0:2])
    minutes = int(stamp[2:4])
    seconds = float(stamp[4:])
    total = hours * 3600 + minutes * 60 + seconds + shift
    total = total % 86400
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    seconds = total % 60
    return "%02d%02d%05.2f" % (hours, minutes, seconds)


def checksum(body):
    value = 0
    for character in body:
        value ^= ord(character)
    return "%02X" % value


written = 0
with open(sourcePath, "r", encoding="ascii", errors="ignore") as source:
    with open(targetPath, "w", encoding="ascii") as target:
        for row in source:
            row = row.strip()
            if row.startswith("$") is False:
                continue
            body = row[1:].split("*")[0]
            fields = body.split(",")
            sentence = fields[0][2:]
            if sentence in timeFieldBySentence:
                index = timeFieldBySentence[sentence]
                if index < len(fields) and len(fields[index]) >= 6:
                    fields[index] = shiftedStamp(fields[index], shiftSeconds)
            body = ",".join(fields)
            target.write("$" + body + "*" + checksum(body) + "\r\n")
            written += 1

print("wrote %d sentences shifted by %d seconds to %s" % (written, shiftSeconds, targetPath))
