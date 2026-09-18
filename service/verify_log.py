"""checks the verdict log two ways: the chain of fingerprints, and the device's signature on each entry"""

import hashlib
import json
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

logPath = "/home/pi/gps_timing/verdict_log.jsonl"
publicKeyPath = "/home/pi/gps_timing/keys/device_key.pub"
if len(sys.argv) > 1:
    logPath = sys.argv[1]
if len(sys.argv) > 2:
    publicKeyPath = sys.argv[2]

with open(publicKeyPath, "rb") as handle:
    publicKey = serialization.load_pem_public_key(handle.read())

previousHash = "0" * 64
checked = 0
chainBroken = 0
signatureBroken = 0

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
        checked += 1

        if entry["prevHash"] != previousHash and chainBroken == 0:
            chainBroken = entry["seq"]
            print("entry %d points at a previous fingerprint that does not match" % entry["seq"])
        if expected != stored and chainBroken == 0:
            chainBroken = entry["seq"]
            print("entry %d was altered, its own fingerprint does not match its contents" % entry["seq"])

        try:
            publicKey.verify(bytes.fromhex(signature), stored.encode("utf-8"))
        except (InvalidSignature, ValueError):
            if signatureBroken == 0:
                signatureBroken = entry["seq"]
                print("entry %d carries no valid signature from this device" % entry["seq"])

        previousHash = stored

print("%d entries read" % checked)
if chainBroken > 0:
    print("CHAIN BROKEN from entry %d" % chainBroken)
if signatureBroken > 0:
    print("SIGNATURE INVALID from entry %d" % signatureBroken)
if chainBroken > 0 or signatureBroken > 0:
    sys.exit(1)

print("chain intact and every entry signed by this device")
