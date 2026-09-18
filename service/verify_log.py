"""checks the verdict log two ways: the chain of fingerprints, and the device's signature on each entry"""

import hashlib
import json
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

defaultLogPath = "/home/pi/gps_timing/verdict_log.jsonl"
defaultKeyPath = "/home/pi/gps_timing/keys/device_key.pub"


def verifyLog(logPath, publicKeyPath):
    with open(publicKeyPath, "rb") as handle:
        publicKey = serialization.load_pem_public_key(handle.read())

    previousHash = "0" * 64
    result = {"checked": 0, "chainBrokenAt": 0, "signatureBrokenAt": 0, "messages": []}

    with open(logPath, "r", encoding="utf-8") as handle:
        for row in handle:
            row = row.strip()
            if len(row) == 0:
                continue
            entry = json.loads(row)
            stored = entry.pop("hash")
            signature = entry.pop("sig", "")
            body = json.dumps(entry, sort_keys=True, separators=(",", ":"))
            expected = hashlib.sha256((previousHash + body).encode("utf-8")).hexdigest()
            result["checked"] += 1

            if entry["prevHash"] != previousHash and result["chainBrokenAt"] == 0:
                result["chainBrokenAt"] = entry["seq"]
                result["messages"].append("entry %d points at a previous fingerprint that does not match" % entry["seq"])
            if expected != stored and result["chainBrokenAt"] == 0:
                result["chainBrokenAt"] = entry["seq"]
                result["messages"].append("entry %d was altered, its own fingerprint does not match its contents" % entry["seq"])

            try:
                publicKey.verify(bytes.fromhex(signature), stored.encode("utf-8"))
            except (InvalidSignature, ValueError):
                if result["signatureBrokenAt"] == 0:
                    result["signatureBrokenAt"] = entry["seq"]
                    result["messages"].append("entry %d carries no valid signature from this device" % entry["seq"])

            previousHash = stored

    return result


def main():
    logPath = defaultLogPath
    publicKeyPath = defaultKeyPath
    if len(sys.argv) > 1:
        logPath = sys.argv[1]
    if len(sys.argv) > 2:
        publicKeyPath = sys.argv[2]

    result = verifyLog(logPath, publicKeyPath)
    for message in result["messages"]:
        print(message)
    print("%d entries read" % result["checked"])

    if result["chainBrokenAt"] > 0:
        print("CHAIN BROKEN from entry %d" % result["chainBrokenAt"])
    if result["signatureBrokenAt"] > 0:
        print("SIGNATURE INVALID from entry %d" % result["signatureBrokenAt"])
    if result["chainBrokenAt"] > 0 or result["signatureBrokenAt"] > 0:
        return 1

    print("chain intact and every entry signed by this device")
    return 0


if __name__ == "__main__":
    sys.exit(main())
