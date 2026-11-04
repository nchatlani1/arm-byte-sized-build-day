// ADVANCED DISPLAY: Morning Briefing plus optional calendar and Spotify.
// For the single-project introduction, use ../../starter instead.
// device.json controls screens; the supplied .env uses Guest-AccessNG. Keep personal Wi-Fi edits out of Git.
#include <Arduino.h>
#include <cstring>
#include <Preferences.h>
#include <esp_mac.h>
#include <esp_timer.h>
#include "EPD.h"
#include "frames.h"
#include "settings.h"
#include "carousel.h"
#include "panel_canvas.h"
#include "live_poll.h"
#if WORKSHOP_DATA_BRIDGE
#include "companion_link.h"
#endif
#if WORKSHOP_LIVE
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include "wifi_profiles.h"
#include "direct_data.h"
#endif

namespace {
// Optional C++ customization: a short ASCII footer (38 chars max).
// Start with stock_symbol and weather.zip_code in device.json.
// This footer survives direct stock/weather updates on the starter.
constexpr const char* kParticipantMessage = "";
// The JD79661 has 122 visible rows but 128 padded rows: 250 * 16 = 4000 bytes.
constexpr size_t kFrameBytes = 4000;
constexpr uint32_t kMinimumRefreshMs = 30000;
constexpr uint32_t kPollMs = 15*60*1000; // Stock/weather refresh interval.
constexpr uint8_t kWheelUp = 6;    // Elecrow PRV_KEY: physical up means NEXT in this carousel.
constexpr uint8_t kWheelDown = 4;  // Elecrow NEXT_KEY: physical down means PREVIOUS.
uint8_t currentFrame[kFrameBytes];
uint8_t nextFrame[kFrameBytes];
bool displayed = false;
uint32_t lastRefresh = 0;
uint32_t lastNavigation = 0;
uint8_t activeProject = 0;
bool manualDirty = false;
bool contentDirty = false;
Preferences carouselPrefs;

// Capture wheel pulses even while a physical e-paper refresh or request is running.
portMUX_TYPE wheelLock = portMUX_INITIALIZER_UNLOCKED;
volatile int pendingSteps = 0;
// A separate task samples through blocking e-paper refreshes. Edge interrupts
// cannot distinguish a new press from contact bounce without a release latch.
void wheelTask(void*) {
    carousel::WheelInput input;
    TickType_t wake = xTaskGetTickCount();
    while (true) {
        const int step = input.sample(digitalRead(kWheelUp) == LOW,
                                      digitalRead(kWheelDown) == LOW, millis());
        if (step) {
            portENTER_CRITICAL(&wheelLock);
            if (step > 0 && pendingSteps < 64) ++pendingSteps;
            if (step < 0 && pendingSteps > -64) --pendingSteps;
            portEXIT_CRITICAL(&wheelLock);
        }
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(5));
    }
}

int takeWheelSteps() {
    portENTER_CRITICAL(&wheelLock);
    int steps = pendingSteps;
    pendingSteps = 0;
    portEXIT_CRITICAL(&wheelLock);
    return steps;
}

#if WORKSHOP_LIVE
struct FetchResult { uint8_t project; bool success; uint32_t providerDelayMs; uint8_t frame[kFrameBytes]; };
QueueHandle_t requestQueue = nullptr;
QueueHandle_t resultQueue = nullptr;
uint8_t cachedFrames[kScreenCount][kFrameBytes];
bool hasLiveData[kScreenCount] = {};
bool stale[kScreenCount] = {};
live_poll::Schedule pollSchedule[kScreenCount];
bool fetchPending = false;
FetchResult receivedResult;

// Only the network task touches providers/authentication. Display operations stay on the UI task.
bool fetchFrame(uint8_t project, uint8_t* frame) {
    if (!connectWorkshopWiFi()) return false;
    memcpy_P(frame, kFrames[project], kFrameBytes);
    if (!direct::fetch(frame, project)) return false;
    Serial.printf("LIVE_FETCH_OK: %s direct from provider\n", kNames[project]);
    return true;
}
void networkTask(void*) {
    FetchResult result;
    while (true) {
        uint8_t project;
        if (xQueueReceive(requestQueue, &project, portMAX_DELAY) == pdTRUE) {
            result.project = project;
            result.success = fetchFrame(project, result.frame);
            result.providerDelayMs = direct::retryDelayMs(project);
            xQueueOverwrite(resultQueue, &result);
        }
    }
}
void collectNetworkResult() {
    if (!resultQueue || xQueueReceive(resultQueue, &receivedResult, 0) != pdTRUE) return;
    fetchPending = false;
    const uint8_t project = receivedResult.project;
    if (project >= kScreenCount) return;
    const uint32_t nextPollMs = pollSchedule[project].complete(
        millis(), receivedResult.success, kPollMs, receivedResult.providerDelayMs);
    if (!receivedResult.success)
        Serial.printf("LIVE_RETRY: %s in %lu ms\n", kNames[project], static_cast<unsigned long>(nextPollMs));
    if (receivedResult.success) {
        std::memcpy(cachedFrames[project], receivedResult.frame, kFrameBytes);
        hasLiveData[project] = true;
        stale[project] = false;
    } else if (hasLiveData[project]) {
        stale[project] = true;
        Serial.printf("STALE: %s data unavailable; last screen marked OLD\n", kNames[project]);
    }
    // A response for the previous project can update its cache, never replace the selected screen.
    if (project == activeProject && hasLiveData[project]) contentDirty = true;
}
#endif

void drawFrame(const uint8_t* frame) {
    // E-paper refresh blocks and visibly flashes; retain this vendor sequence.
    // Drawing identical pixels is skipped to avoid unnecessary physical refreshes.
    if (displayed && std::memcmp(currentFrame, frame, kFrameBytes) == 0) return;
    EPD_Init();
    EPD_Clear();
    EPD_Update();
    EPD_DisplayImage(frame);
    EPD_Update();
    EPD_Sleep();
    std::memcpy(currentFrame, frame, kFrameBytes);
    displayed = true;
    lastRefresh = millis();
    Serial.printf("DISPLAY_READY: %s | screen %u/%u\n", kNames[activeProject], activeProject+1, kScreenCount);
}
void showActive() {
    const size_t index = activeProject;
    memcpy_P(nextFrame, kFrames[index], kFrameBytes);
#if WORKSHOP_LIVE
    if (activeProject < kScreenCount && hasLiveData[activeProject]) {
        std::memcpy(nextFrame, cachedFrames[activeProject], kFrameBytes);
        if (stale[activeProject]) panel::status(nextFrame, "OLD");
    }
#endif
    // Build-time samples -> live/cache content -> footer -> optional account overlay.
    if (kScreenCount > 1) panel::text(nextFrame, String(activeProject+1)+"/"+String(kScreenCount), 180, 7, 12, 24);
    if (kParticipantMessage[0]) panel::footer(nextFrame, kParticipantMessage);
#if WORKSHOP_DATA_BRIDGE
    // Account metadata changes the pixels here; credentials stay on the laptop.
    bridge::apply(nextFrame, activeProject);
#endif
    drawFrame(nextFrame);
    manualDirty = false;
    contentDirty = false;
    if (kScreenCount > 1 && carouselPrefs.getUInt("project", 255) != activeProject)
        carouselPrefs.putUInt("project", activeProject);
}
}

void setup() {
    Serial.setRxBufferSize(2048);
    Serial.begin(115200);
    delay(1000);
    uint8_t mac[6];
    if (esp_read_mac(mac, ESP_MAC_WIFI_STA) == ESP_OK)
        Serial.printf("Wi-Fi station MAC: %02X:%02X:%02X:%02X:%02X:%02X\n", mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
    pinMode(7, OUTPUT);
    digitalWrite(7, HIGH);
    delay(100);
    // With one registered screen, always boot to stock/weather. Additional screens
    // reuse the existing persisted selection and wheel sampler, including refresh-time input.
    if (kScreenCount > 1) {
        carouselPrefs.begin("carousel", false);
        activeProject = carouselPrefs.getUInt("project", 0) % kScreenCount;
        pinMode(kWheelUp, INPUT_PULLUP);
        pinMode(kWheelDown, INPUT_PULLUP);
        if (xTaskCreatePinnedToCore(wheelTask, "wheel-input", 2048, nullptr, 2, nullptr, 1) == pdPASS) {
            Serial.printf("CAROUSEL_READY: UP=next (GPIO6), DOWN=previous (GPIO4), %u screens; one step per press, release to re-arm\n", kScreenCount);
        } else {
            Serial.println("CAROUSEL_INPUT_UNAVAILABLE: could not start wheel sampling task");
        }
    }
    Serial.printf("TEMPLATE: %s | mode: %s\n", kNames[activeProject], WORKSHOP_LIVE ? "live" : "demo/offline");
#if WORKSHOP_DATA_BRIDGE
    pinMode(2, INPUT_PULLUP); // MENU: hold two seconds to pair.
    pinMode(1, INPUT_PULLUP); // EXIT: hold eight seconds to forget bonds.
    bridge::begin();
#endif
    showActive();
    lastNavigation = millis();
#if WORKSHOP_LIVE
    // Allow the initial demo refresh to settle before drawing live content.
    for (uint8_t i=0; i<kScreenCount; ++i) pollSchedule[i].start(millis(), kMinimumRefreshMs);
    requestQueue = xQueueCreate(1, sizeof(uint8_t));
    resultQueue = xQueueCreate(1, sizeof(FetchResult));
    if (!requestQueue || !resultQueue || xTaskCreatePinnedToCore(networkTask, "live-data", 24576, nullptr, 1, nullptr, 0) != pdPASS) {
        if (requestQueue) vQueueDelete(requestQueue);
        if (resultQueue) vQueueDelete(resultQueue);
        requestQueue = nullptr;
        resultQueue = nullptr;
        Serial.println("LIVE_UNAVAILABLE: could not allocate network task; demo navigation still available");
    }
#endif
}

void loop() {
    delay(10);
#if WORKSHOP_DATA_BRIDGE
    bridge::poll(!displayed || millis()-lastRefresh >= kMinimumRefreshMs);
    if (bridge::changed) { contentDirty = true; bridge::changed = false; }
#endif
    const int steps = takeWheelSteps();
    if (steps) {
        Serial.printf("WHEEL_INPUT: accepted %d step(s) since last UI update\n", steps);
        const uint8_t selected = carousel::step(activeProject, steps, kScreenCount);
        if (selected != activeProject) {
            activeProject = selected;
            lastNavigation = millis();
            manualDirty = true;
            Serial.printf("CAROUSEL_SELECT: %s | %u/%u\n", kNames[activeProject], activeProject+1, kScreenCount);
        }
    }
#if WORKSHOP_LIVE
    collectNetworkResult();
#endif
    if (manualDirty && carousel::ready(millis(), lastNavigation, lastRefresh)) showActive();
    else if (!manualDirty && contentDirty && millis()-lastRefresh >= kMinimumRefreshMs) showActive();
#if WORKSHOP_LIVE
    if (
        activeProject == kMorningBriefingScreen &&
        requestQueue && !fetchPending && !manualDirty && activeProject < kScreenCount && millis()-lastNavigation >= 1000 && pollSchedule[activeProject].due(millis())) {
        const uint8_t project = activeProject;
        if (xQueueSend(requestQueue, &project, 0) == pdTRUE) {
            fetchPending = true;
        }
    }
#endif
}

