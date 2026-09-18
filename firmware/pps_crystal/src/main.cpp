// measures this board's crystal against the GPS pulse on GPIO 4

#include <Arduino.h>

const int ppsPin = 4;
const uint32_t nominalInterval = 1000000;
const int averageWindow = 60;

portMUX_TYPE edgeMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t lastEdgeMicros = 0;
volatile uint32_t edgeInterval = 0;
volatile uint32_t edgeCount = 0;

void IRAM_ATTR onPpsEdge(){
    uint32_t nowMicros = micros();
    portENTER_CRITICAL_ISR(&edgeMux);
    edgeInterval = nowMicros - lastEdgeMicros;
    lastEdgeMicros = nowMicros;
    edgeCount++;
    portEXIT_CRITICAL_ISR(&edgeMux);
}

void setup(){
    Serial.begin(115200);
    delay(300);
    pinMode(ppsPin, INPUT);
    attachInterrupt(digitalPinToInterrupt(ppsPin), onPpsEdge, RISING);
    Serial.println();
    Serial.println("edge  interval_us  error_us  mean_error_us  seconds_averaged");
}

void loop(){
    static uint32_t reportedCount = 0;
    static int64_t errorSum = 0;
    static int32_t errorsAveraged = 0;
    uint32_t interval;
    uint32_t count;

    portENTER_CRITICAL(&edgeMux);
    interval = edgeInterval;
    count = edgeCount;
    portEXIT_CRITICAL(&edgeMux);

    if (count > reportedCount){
        reportedCount = count;
        if (count > 1){
            int32_t errorMicros = (int32_t)(interval - nominalInterval);
            errorSum += errorMicros;
            errorsAveraged++;
            if (errorsAveraged > averageWindow){   // keeps the mean recent rather than lifetime
                errorSum = errorMicros;
                errorsAveraged = 1;
            }
            float meanError = (float)errorSum / (float)errorsAveraged;
            Serial.printf("%lu  %lu  %+ld  %+.2f  %ld\n", count, interval, errorMicros, meanError, errorsAveraged);
        }
    }
    delay(2);
}
