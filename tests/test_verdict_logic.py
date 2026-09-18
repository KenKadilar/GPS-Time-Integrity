"""the decision logic, fed source tables taken from real runs on 2026-09-17"""

import verdict_service


def sourceRow(mode, state, name, reach, lastRx, offset, error=0.0000005):
    return {"mode": mode, "state": state, "name": name, "reach": reach, "lastRx": lastRx, "offset": offset, "error": error}


def healthyServers():
    return [
        sourceRow("^", "-", "archer.fsck.ca", 377, 19, -0.004794),
        sourceRow("^", "-", "ntp.netlinkify.com", 377, 22, -0.002303),
        sourceRow("^", "-", "tangent.muug.ca", 377, 15, -0.003495),
    ]


def trackingSample():
    return {"refName": "PPS", "stratum": 1, "systemTimeOffset": -1.7e-08, "frequencyPpm": 7.657, "residualPpm": 0.036}


def testLockedWhenPulseIsFreshAndServersAgree():
    sources = [sourceRow("#", "*", "PPS", 377, 3, -0.00000016)] + healthyServers()
    state, detail = verdict_service.decideState(trackingSample(), sources, {"mode": 3, "satellitesUsed": 8}, None)
    assert state == "LOCKED"
    assert detail["comparedAgainst"] == "PPS"
    assert detail["satelliteVersusServersWorst"] < 0.01


def testSpoofedReceiverIsUntrusted():
    # the real numbers from the 120 second spoof, chrony reported the pulse itself carrying the lie
    sources = [sourceRow("#", "*", "PPS", 377, 4, -120.000)] + healthyServers()
    state, detail = verdict_service.decideState(trackingSample(), sources, {"mode": 3, "satellitesUsed": 9}, None)
    assert state == "UNTRUSTED"
    assert detail["satelliteVersusServersWorst"] > 119.0


def testNormalNetworkNoiseStaysLocked():
    # 12.6 ms was the worst healthy disagreement measured, well inside the 50 ms limit
    sources = [sourceRow("#", "*", "PPS", 377, 3, 0.0000004)] + [sourceRow("^", "-", "noisy.example", 377, 30, -0.0126)]
    state, detail = verdict_service.decideState(trackingSample(), sources, {"mode": 3, "satellitesUsed": 6}, None)
    assert state == "LOCKED"
    assert detail["satelliteVersusServersWorst"] < verdict_service.disagreementLimitSeconds


def testStalePulseReadsHoldoverEvenWhileChronyStillShowsTheStar():
    # chrony leaves the star on its last reference, so the star alone means most recently trusted
    sources = [sourceRow("#", "*", "PPS", 0, 3790, 0.000000563)] + healthyServers()
    state, detail = verdict_service.decideState(trackingSample(), sources, {"mode": 3, "satellitesUsed": 0}, None)
    assert state == "HOLDOVER"
    assert detail["pulseMissingWithFix"] is True


def testHoldoverPredictsItsOwnError():
    sources = [sourceRow("#", "?", "PPS", 0, 900, 0.0)] + healthyServers()
    startedSecondsAgo = 840
    state, detail = verdict_service.decideState(
        trackingSample(), sources, {"mode": 3, "satellitesUsed": 0}, __import__("time").time() - startedSecondsAgo
    )
    assert state == "HOLDOVER"
    assert detail["holdoverSeconds"] > 800
    assert detail["predictedErrorMicros"] > 10


def testWarmingBeforeTheFirstFix():
    sources = [sourceRow("#", "?", "PPS", 0, 0, 0.0)]
    state, detail = verdict_service.decideState(trackingSample(), sources, {"mode": 1, "satellitesUsed": 0}, None)
    assert state == "WARMING"
