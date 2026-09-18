"""the chain and the signatures, including a forgery that rebuilds every fingerprint correctly"""

import hashlib
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import verdict_service
import verify_log


def buildLog(directory, entryCount=3):
    privateKey = Ed25519PrivateKey.generate()
    privatePath = directory / "device_key.pem"
    publicPath = directory / "device_key.pub"
    privatePath.write_bytes(privateKey.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    publicPath.write_bytes(privateKey.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))

    logPath = directory / "verdict_log.jsonl"
    verdict_service.logPath = str(logPath)

    previousHash = "0" * 64
    index = 0
    while index < entryCount:
        index += 1
        previousHash = verdict_service.appendEntry(
            privateKey, index, previousHash, "LOCKED", "state change", {"satelliteVersusServersWorst": 0.004}
        )
    return str(logPath), str(publicPath)


def testAGenuineLogPasses(tmp_path):
    logPath, publicPath = buildLog(tmp_path)
    result = verify_log.verifyLog(logPath, publicPath)
    assert result["checked"] == 3
    assert result["chainBrokenAt"] == 0
    assert result["signatureBrokenAt"] == 0


def testAnEditedEntryBreaksTheChain(tmp_path):
    logPath, publicPath = buildLog(tmp_path)
    rows = open(logPath, encoding="utf-8").read().splitlines()
    entry = json.loads(rows[0])
    entry["state"] = "UNTRUSTED"
    rows[0] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    open(logPath, "w", encoding="utf-8").write("\n".join(rows) + "\n")

    result = verify_log.verifyLog(logPath, publicPath)
    assert result["chainBrokenAt"] == 1


def testARebuiltChainStillFailsTheSignature(tmp_path):
    # the attacker holds the source, edits a verdict and recomputes every fingerprint
    logPath, publicPath = buildLog(tmp_path)
    entries = [json.loads(row) for row in open(logPath, encoding="utf-8") if row.strip()]
    entries[0]["state"] = "LOCKED"
    entries[0]["detail"]["satelliteVersusServersWorst"] = 0.000001

    previous = "0" * 64
    rebuilt = []
    for entry in entries:
        entry.pop("hash")
        signature = entry.pop("sig")
        entry["prevHash"] = previous
        body = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        entry["hash"] = hashlib.sha256((previous + body).encode("utf-8")).hexdigest()
        entry["sig"] = signature
        previous = entry["hash"]
        rebuilt.append(json.dumps(entry, sort_keys=True, separators=(",", ":")))
    open(logPath, "w", encoding="utf-8").write("\n".join(rebuilt) + "\n")

    result = verify_log.verifyLog(logPath, publicPath)
    assert result["chainBrokenAt"] == 0
    assert result["signatureBrokenAt"] == 1


def testALogSignedByAnotherDeviceFails(tmp_path):
    logPath, _ = buildLog(tmp_path)
    otherKey = Ed25519PrivateKey.generate()
    otherPublic = tmp_path / "other_device.pub"
    otherPublic.write_bytes(otherKey.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))

    result = verify_log.verifyLog(logPath, str(otherPublic))
    assert result["chainBrokenAt"] == 0
    assert result["signatureBrokenAt"] == 1
