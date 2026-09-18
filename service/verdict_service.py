"""decides whether the clock can be trusted and appends each verdict to a hash chained log"""

import hashlib
import json
import os
import subprocess
import time

from cryptography.hazmat.primitives import serialization

logPath = "/home/pi/gps_timing/verdict_log.jsonl"
privateKeyPath = "/home/pi/gps_timing/keys/device_key.pem"
espPort = "/dev/ttyUSB0"
pollSeconds = 5
heartbeatSeconds = 300
disagreementLimitSeconds = 0.050
holdoverMicrosPerMinute = 0.86


def readChronyTracking():
    result = subprocess.run(["chronyc", "-c", "tracking"], capture_output=True, timeout=5)
    fields = result.stdout.decode("ascii", "ignore").strip().split(",")
    if len(fields) < 14:
        return {}
    return {
        "refName": fields[1],
        "stratum": int(fields[2]),
        "systemTimeOffset": float(fields[4]),
        "rmsOffset": float(fields[6]),
        "frequencyPpm": float(fields[7]),
        "residualPpm": float(fields[8]),
        "skewPpm": float(fields[9]),
    }


def readChronySources():
    result = subprocess.run(["chronyc", "-c", "sources"], capture_output=True, timeout=5)
    sources = []
    for row in result.stdout.decode("ascii", "ignore").strip().splitlines():
        fields = row.split(",")
        if len(fields) < 10:
            continue
        sources.append({
            "mode": fields[0],
            "state": fields[1],
            "name": fields[2],
            "reach": int(fields[5]),
            "lastRx": int(fields[6]),
            "offset": float(fields[8]),
            "error": float(fields[9]),
        })
    return sources


def readBoardTemperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r", encoding="utf-8") as handle:
            return round(int(handle.read().strip()) / 1000.0, 2)
    except Exception:
        return None


def readGpsFix():
    try:
        result = subprocess.run(["gpspipe", "-w", "-n", "12"], capture_output=True, timeout=8)
    except subprocess.TimeoutExpired:
        return {"mode": 0, "satellitesUsed": 0}
    mode = 0
    satellitesUsed = 0
    for row in result.stdout.decode("ascii", "ignore").splitlines():
        try:
            message = json.loads(row)
        except ValueError:
            continue
        if message.get("class") == "TPV":
            mode = message.get("mode", 0)
        if message.get("class") == "SKY":
            satellitesUsed = len([one for one in message.get("satellites", []) if one.get("used")])
    return {"mode": mode, "satellitesUsed": satellitesUsed}


def readEspCrystal(espSerial):
    if espSerial is None:
        return None
    reading = None
    while espSerial.in_waiting > 0:
        raw = espSerial.readline().decode("ascii", "ignore").strip()
        parts = raw.split()
        if len(parts) == 5:
            try:
                interval = float(parts[1])
                mean = float(parts[3])
            except ValueError:
                continue
            if abs(interval - 1000000.0) < 1000.0:   # keeps boot chatter and missed edges out
                reading = mean
    return reading


def decideState(tracking, sources, gps, holdoverStarted):
    ppsRows = [one for one in sources if one["name"] == "PPS"]
    serverRows = [one for one in sources if one["mode"] == "^" and one["reach"] > 0]
    worstDisagreement = 0.0
    for row in serverRows:
        if abs(row["offset"]) > worstDisagreement:
            worstDisagreement = abs(row["offset"])

    pps = None
    if len(ppsRows) > 0:
        pps = ppsRows[0]

    # every offset is measured against the system clock, so subtracting two of them cancels the clock out
    satelliteRow = None
    for row in sources:
        if row["name"] == "PPS" and row["reach"] > 0:
            satelliteRow = row
    if satelliteRow is None:
        for row in sources:
            if row["name"] == "NMEA" and row["reach"] > 0:
                satelliteRow = row

    satelliteVersusServers = 0.0
    if satelliteRow is not None:
        for row in serverRows:
            gap = abs(satelliteRow["offset"] - row["offset"])
            if gap > satelliteVersusServers:
                satelliteVersusServers = gap

    detail = {
        "satelliteVersusServersWorst": round(satelliteVersusServers, 6),
        "comparedAgainst": None if satelliteRow is None else satelliteRow["name"],
        "worstServerDisagreement": round(worstDisagreement, 6),
        "serversCompared": len(serverRows),
        "gpsMode": gps["mode"],
        "satellitesUsed": gps["satellitesUsed"],
        "systemTimeOffset": tracking.get("systemTimeOffset"),
        "frequencyPpm": tracking.get("frequencyPpm"),
        "residualPpm": tracking.get("residualPpm"),
    }

    if pps is not None:
        detail["ppsReach"] = pps["reach"]
        detail["ppsLastRx"] = pps["lastRx"]
        detail["ppsOffset"] = pps["offset"]
        detail["ppsError"] = pps["error"]

    # chrony keeps the star on the last reference it used, so a sample has to have arrived recently too
    pulseAlive = pps is not None and pps["reach"] > 0 and pps["lastRx"] < 60
    pulseSelected = pulseAlive and pps["state"] == "*"
    detail["pulseMissingWithFix"] = gps["mode"] > 1 and pulseAlive is False   # a fix but no pulse means the wiring

    if satelliteRow is not None and len(serverRows) > 0 and satelliteVersusServers > disagreementLimitSeconds:
        return "UNTRUSTED", detail
    if pulseSelected:
        return "LOCKED", detail
    if pulseAlive:
        return "UNTRUSTED", detail
    if holdoverStarted is None and gps["mode"] < 2:
        return "WARMING", detail

    blindSeconds = 0
    if holdoverStarted is not None:
        blindSeconds = time.time() - holdoverStarted
    detail["holdoverSeconds"] = round(blindSeconds, 1)
    detail["predictedErrorMicros"] = round(blindSeconds / 60.0 * holdoverMicrosPerMinute, 1)
    return "HOLDOVER", detail


def lastChainState():
    if os.path.exists(logPath) is False:
        return "0" * 64, 0
    previous = "0" * 64
    sequence = 0
    with open(logPath, "r", encoding="utf-8") as handle:
        for row in handle:
            row = row.strip()
            if len(row) > 0:
                entry = json.loads(row)
                previous = entry["hash"]
                sequence = entry["seq"]
    return previous, sequence


def loadSigningKey():
    with open(privateKeyPath, "rb") as handle:
        return serialization.load_pem_private_key(handle.read(), password=None)


def appendEntry(signingKey, sequence, previousHash, state, reason, detail):
    entry = {
        "seq": sequence,
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "state": state,
        "reason": reason,
        "detail": detail,
        "prevHash": previousHash,
    }
    body = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    entry["hash"] = hashlib.sha256((previousHash + body).encode("utf-8")).hexdigest()
    entry["sig"] = signingKey.sign(entry["hash"].encode("utf-8")).hex()
    with open(logPath, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
    return entry["hash"]


def main():
    espSerial = None
    try:
        import serial
        espSerial = serial.Serial(espPort, 115200, timeout=0.2, rtscts=False, dsrdtr=False)
        espSerial.dtr = False
        espSerial.rts = False
    except Exception:
        espSerial = None

    signingKey = loadSigningKey()
    previousHash, sequence = lastChainState()   # the count carries on across a restart
    lastState = None
    lastWrite = 0.0
    holdoverStarted = None

    while True:
        tracking = readChronyTracking()
        sources = readChronySources()
        gps = readGpsFix()
        state, detail = decideState(tracking, sources, gps, holdoverStarted)

        crystal = readEspCrystal(espSerial)
        if crystal is not None:
            detail["espCrystalErrorMicros"] = crystal

        temperature = readBoardTemperature()
        if temperature is not None:
            detail["boardTemperatureC"] = temperature

        if state == "HOLDOVER" and holdoverStarted is None:
            holdoverStarted = time.time()
        if state == "LOCKED":
            holdoverStarted = None

        changed = state != lastState
        due = time.time() - lastWrite > heartbeatSeconds
        if changed or due:
            reason = "state change"
            if changed is False:
                reason = "heartbeat"
            sequence += 1
            previousHash = appendEntry(signingKey, sequence, previousHash, state, reason, detail)
            lastState = state
            lastWrite = time.time()

        time.sleep(pollSeconds)


if __name__ == "__main__":
    main()
