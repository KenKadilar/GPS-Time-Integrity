// stamps a shared event in this board's own time base, counted from the GPS pulse

#include <Arduino.h>

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

void setup(){
    Serial.begin(115200);
    delay(300);
    pinMode(ppsPin, INPUT);
    pinMode(eventPin, INPUT);
    attachInterrupt(digitalPinToInterrupt(ppsPin), onPpsEdge, RISING);
    attachInterrupt(digitalPinToInterrupt(eventPin), onEventEdge, RISING);
    Serial.println();
    Serial.printf("board %s ready, pulse on GPIO %d, event on GPIO %d\n", BOARD_ID, ppsPin, eventPin);
    Serial.println("PULSE board pulse interval_us error_us");
    Serial.println("EVENT board pulse offset_us");
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

    if (events > reportedEvent){
        reportedEvent = events;
        Serial.printf("EVENT %s %lu %lu\n", BOARD_ID, stampPulse, stampMicros);
    }

    if (pulses > reportedPulse){
        reportedPulse = pulses;
        if (pulses > 1){
            int32_t errorMicros = (int32_t)(interval - nominalInterval);
            Serial.printf("PULSE %s %lu %lu %+ld\n", BOARD_ID, pulses, interval, errorMicros);
        }
    }

    delay(2);
}
