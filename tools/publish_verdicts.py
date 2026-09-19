# publishes verdict log entries to AWS IoT Core over mutual TLS, adding the device name that the table keys on

import argparse
import glob
import json
import os
import ssl
import sys
import time

import paho.mqtt.client as mqtt

endpoint = "as09x8wzwzx1x-ats.iot.ca-central-1.amazonaws.com"
endpointPort = 8883
deviceName = "gps-verdict-node"
publishTopic = "gps/verdict"
certificateDir = "/home/pi/gps_timing/certs"
verdictLogPath = "/home/pi/gps_timing/verdict_log.jsonl"


def makeClient():
    rootAuthority = os.path.join(certificateDir, "AmazonRootCA1.pem")
    certificatePath = glob.glob(os.path.join(certificateDir, "*-certificate.pem.crt"))[0]
    privateKeyPath = glob.glob(os.path.join(certificateDir, "*-private.pem.key"))[0]
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=deviceName)
    client.tls_set(ca_certs=rootAuthority, certfile=certificatePath, keyfile=privateKeyPath,
                   tls_version=ssl.PROTOCOL_TLSv1_2)
    client.connect(endpoint, endpointPort, keepalive=60)
    client.loop_start()
    return client


def readEntries(path):
    entries = []
    with open(path, "r", encoding="utf-8") as handle:
        for row in handle:
            row = row.strip()
            if row:
                entries.append(json.loads(row))
    return entries


def publishOne(client, entry):
    entry["device"] = deviceName   # the table's partition key, absent from the log's own format
    result = client.publish(publishTopic, json.dumps(entry), qos=1)
    result.wait_for_publish(timeout=10)
    return result.is_published()


def main():
    parser = argparse.ArgumentParser(description="send verdict entries to AWS IoT Core")
    parser.add_argument("--limit", type=int, default=5, help="how many of the newest entries to send")
    parser.add_argument("--all", action="store_true", help="send every entry in the log")
    parser.add_argument("--follow", action="store_true", help="keep running and send each new entry as it lands")
    arguments = parser.parse_args()

    entries = readEntries(verdictLogPath)
    print(f"log holds {len(entries)} entries, seq {entries[0]['seq']} to {entries[-1]['seq']}")

    chosen = entries
    if arguments.all is False:
        chosen = entries[-arguments.limit:]

    client = makeClient()
    print(f"connected to {endpoint} as {deviceName}")

    sent = 0
    for entry in chosen:
        if publishOne(client, entry):
            sent += 1
            print(f"sent seq {entry['seq']} {entry['state']} {entry['time']}")
        else:
            print(f"FAILED seq {entry['seq']}")

    print(f"{sent} of {len(chosen)} published to {publishTopic}")

    if arguments.follow:
        lastSeq = entries[-1]["seq"]
        print("following the log, ctrl-c to stop")
        while True:
            time.sleep(5)
            fresh = readEntries(verdictLogPath)
            for entry in fresh:
                if entry["seq"] > lastSeq:
                    lastSeq = entry["seq"]
                    if publishOne(client, entry):
                        print(f"sent seq {entry['seq']} {entry['state']} {entry['time']}")

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
