// stamps the GPS pulse twice on one pin, latched in hardware by the capture peripheral and read by a software interrupt

#include <Arduino.h>
#include "driver/mcpwm.h"

const int ppsPin = 4;
const mcpwm_unit_t captureUnit = MCPWM_UNIT_0;

portMUX_TYPE stampMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t hardwareTicks = 0;
volatile uint32_t hardwareCount = 0;
volatile uint32_t softwareCycles = 0;
volatile uint32_t softwareCount = 0;

bool IRAM_ATTR onCaptureEdge(mcpwm_unit_t unit, mcpwm_capture_channel_id_t channel, const cap_event_data_t* event, void* context){
    portENTER_CRITICAL_ISR(&stampMux);
    hardwareTicks = event->cap_value;
    hardwareCount++;
    portEXIT_CRITICAL_ISR(&stampMux);
    return false;   // no higher priority task to wake
}

void IRAM_ATTR onSoftwareEdge(){
    uint32_t nowCycles = ESP.getCycleCount();
    portENTER_CRITICAL_ISR(&stampMux);
    softwareCycles = nowCycles;
    softwareCount++;
    portEXIT_CRITICAL_ISR(&stampMux);
}

void setup(){
    Serial.begin(115200);
    delay(300);
    Serial.println();

    pinMode(ppsPin, INPUT);
    attachInterrupt(digitalPinToInterrupt(ppsPin), onSoftwareEdge, RISING);

    mcpwm_gpio_init(captureUnit, MCPWM_CAP_0, ppsPin);
    mcpwm_capture_config_t captureConfig;
    captureConfig.cap_edge = MCPWM_POS_EDGE;
    captureConfig.cap_prescale = 1;
    captureConfig.capture_cb = onCaptureEdge;
    captureConfig.user_data = NULL;
    esp_err_t captureStarted = mcpwm_capture_enable_channel(captureUnit, MCPWM_SELECT_CAP0, &captureConfig);

    char line[140];
    snprintf(line, sizeof(line), "board %s ready, pulse on GPIO %d, cpu %lu MHz, capture clock 80 MHz, channel %s",
             BOARD_ID, ppsPin, (unsigned long)getCpuFrequencyMhz(), esp_err_to_name(captureStarted));
    Serial.println(line);
    Serial.println("CAP board pulse hardwareTicks cpuCycles");
}

void loop(){
    static uint32_t reportedCount = 0;
    uint32_t captures;
    uint32_t softwares;
    uint32_t ticks;
    uint32_t cycles;

    portENTER_CRITICAL(&stampMux);
    captures = hardwareCount;
    softwares = softwareCount;
    ticks = hardwareTicks;
    cycles = softwareCycles;
    portEXIT_CRITICAL(&stampMux);

    char line[90];

    if (captures > reportedCount && softwares > reportedCount){   // both paths have stamped the same edge
        reportedCount = captures;
        snprintf(line, sizeof(line), "CAP %s %lu %lu %lu", BOARD_ID,
                 (unsigned long)captures, (unsigned long)ticks, (unsigned long)cycles);
        Serial.println(line);
        if (softwares != captures){
            snprintf(line, sizeof(line), "MISMATCH hardware %lu software %lu",
                     (unsigned long)captures, (unsigned long)softwares);
            Serial.println(line);
        }
    }

    delay(2);
}
