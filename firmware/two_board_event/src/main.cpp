// stamps a shared event in this board's own time base, counted from the GPS pulse, and reports over serial and UDP

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "secrets.h"

const char* listenerAddress = "10.0.0.30";
const uint16_t listenerPort = 5005;
WiFiUDP udp;

const int ppsPin = 4;
const int eventPin = 18;
const uint32_t nominalInterval = 1000000;
const uint32_t eventHoldoffMicros = 200000;

portMUX_TYPE edgeMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t lastEdgeMicros = 0;
volatile uint32_t edgeInterval = 0;
volatile uint32_t pulseCount = 0;

volatile uint32_t eventMicros = 0;
volatile uint32_t eventPulse = 0;
volatile uint32_t eventCount = 0;
volatile uint32_t lastEventMicros = 0;

void IRAM_ATTR onPpsEdge(){
    uint32_t nowMicros = micros();
    portENTER_CRITICAL_ISR(&edgeMux);
    edgeInterval = nowMicros - lastEdgeMicros;
    lastEdgeMicros = nowMicros;
    pulseCount++;
    portEXIT_CRITICAL_ISR(&edgeMux);
}

void IRAM_ATTR onEventEdge(){
    uint32_t nowMicros = micros();
    portENTER_CRITICAL_ISR(&edgeMux);
    if (nowMicros - lastEventMicros > eventHoldoffMicros){   // one report per event, contact bounce lands inside this
        lastEventMicros = nowMicros;
        eventMicros = nowMicros - lastEdgeMicros;
        eventPulse = pulseCount;
        eventCount++;
    }
    portEXIT_CRITICAL_ISR(&edgeMux);
}

void report(const char* text){
    Serial.println(text);
    if (WiFi.status() == WL_CONNECTED){
        udp.beginPacket(listenerAddress, listenerPort);
        udp.print(text);
        udp.endPacket();
    }
}

void setup(){
    Serial.begin(115200);
    delay(300);
    pinMode(ppsPin, INPUT);
    pinMode(eventPin, INPUT);
    attachInterrupt(digitalPinToInterrupt(ppsPin), onPpsEdge, RISING);
    attachInterrupt(digitalPinToInterrupt(eventPin), onEventEdge, RISING);

    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    uint32_t started = millis();
    while (millis() - started < 15000){
        if (WiFi.status() == WL_CONNECTED){break;}
        delay(250);
    }

    const char* wifiState = "down";
    if (WiFi.status() == WL_CONNECTED){wifiState = "up";}

    char line[120];
    Serial.println();
    snprintf(line, sizeof(line), "board %s ready, pulse on GPIO %d, event on GPIO %d, wifi %s %s",
             BOARD_ID, ppsPin, eventPin, wifiState, WiFi.localIP().toString().c_str());
    report(line);
}

void loop(){
    static uint32_t reportedPulse = 0;
    static uint32_t reportedEvent = 0;
    uint32_t interval;
    uint32_t pulses;
    uint32_t events;
    uint32_t stampMicros;
    uint32_t stampPulse;

    portENTER_CRITICAL(&edgeMux);
    interval = edgeInterval;
    pulses = pulseCount;
    events = eventCount;
    stampMicros = eventMicros;
    stampPulse = eventPulse;
    portEXIT_CRITICAL(&edgeMux);

    char line[80];

    if (events > reportedEvent){
        reportedEvent = events;
        snprintf(line, sizeof(line), "EVENT %s %lu %lu", BOARD_ID, stampPulse, stampMicros);
        report(line);
    }

    if (pulses > reportedPulse){
        reportedPulse = pulses;
        if (pulses > 1){
            int32_t errorMicros = (int32_t)(interval - nominalInterval);
            snprintf(line, sizeof(line), "PULSE %s %lu %lu %+ld", BOARD_ID, pulses, interval, errorMicros);
            report(line);
        }
    }

    delay(2);
}
