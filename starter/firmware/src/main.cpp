// MORNING BRIEFING STARTER — one stock/weather screen, no companion or Bluetooth.
// 1. Change stock_symbol and weather.zip_code in device.json.
// 2. Copy .env.example to .env for your private home/office Wi-Fi settings.
// 3. Build/upload: offline shows DEMO; live fetches directly from the board.
#include <Arduino.h>
#include <cstring>
#include <esp_mac.h>
#include "EPD.h"
#include "frames.h"           // Generated sample pixels and public device.json values.
#include "settings.h"         // Local Wi-Fi header; ignored by the offline build.
#include "panel_canvas.h"     // Small text/pixel drawing helpers for this panel.
#include "live_poll.h"        // Poll deadlines and bounded retries.
#if WORKSHOP_LIVE
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include "wifi_profiles.h"
#include "direct_data.h"      // Stock/weather provider validation and live drawing.
#endif

namespace {
// Keep the panel dimensions, driver sequence and refresh limits unchanged.
constexpr size_t kFrameBytes = 4000; // 250 columns, 128 padded rows; 122 are visible.
constexpr uint32_t kMinimumRefreshMs = 30000;
constexpr uint32_t kPollMs = 15*60*1000;
uint8_t currentFrame[kFrameBytes];   // Last displayed pixels: skip identical updates.
uint8_t nextFrame[kFrameBytes];      // Pixels being prepared for the next refresh.
bool displayed = false;
bool contentDirty = false;
uint32_t lastRefresh = 0;

#if WORKSHOP_LIVE
// Networking runs separately because HTTPS can block. Only the main loop draws.
struct FetchResult { bool success; uint32_t providerDelayMs; uint8_t frame[kFrameBytes]; };
QueueHandle_t requestQueue = nullptr;
QueueHandle_t resultQueue = nullptr;
uint8_t cachedFrame[kFrameBytes];
bool hasLiveData = false;
bool stale = false;
bool fetchPending = false;
live_poll::Schedule pollSchedule;
FetchResult receivedResult;

bool fetchFrame(uint8_t* frame) {
    if (!connectWorkshopWiFi()) return false;
    memcpy_P(frame, kMorningBriefingFrame, kFrameBytes);
    if (!direct::fetch(frame)) return false;
    Serial.println("LIVE_FETCH_OK: morning_briefing direct from provider");
    return true;
}
void networkTask(void*) {
    FetchResult result;
    bool request;
    while (true) {
        if (xQueueReceive(requestQueue, &request, portMAX_DELAY) == pdTRUE) {
            result.success = fetchFrame(result.frame);
            result.providerDelayMs = direct::retryDelayMs();
            xQueueOverwrite(resultQueue, &result);
        }
    }
}
void collectNetworkResult() {
    if (!resultQueue || xQueueReceive(resultQueue, &receivedResult, 0) != pdTRUE) return;
    fetchPending = false;
    const uint32_t nextPollMs = pollSchedule.complete(
        millis(), receivedResult.success, kPollMs, receivedResult.providerDelayMs);
    if (receivedResult.success) {
        std::memcpy(cachedFrame, receivedResult.frame, kFrameBytes);
        hasLiveData = true;
        stale = false;
    } else {
        Serial.printf("LIVE_RETRY: morning_briefing in %lu ms\n", static_cast<unsigned long>(nextPollMs));
        // Preserve good pixels after a failure, but clearly label their data OLD.
        if (hasLiveData) stale = true;
    }
    if (hasLiveData) contentDirty = true;
}
#endif

void drawFrame(const uint8_t* frame) {
    if (displayed && std::memcmp(currentFrame, frame, kFrameBytes) == 0) return;
    // This vendor sequence blocks and visibly flashes. Wait for both updates.
    EPD_Init();
    EPD_Clear();
    EPD_Update();
    EPD_DisplayImage(frame);
    EPD_Update();
    EPD_Sleep();
    std::memcpy(currentFrame, frame, kFrameBytes);
    displayed = true;
    lastRefresh = millis();
    Serial.println("DISPLAY_READY: morning_briefing");
}
void showMorningBriefing() {
    // The compiled sample is the safe fallback before the first successful fetch.
    memcpy_P(nextFrame, kMorningBriefingFrame, kFrameBytes);
#if WORKSHOP_LIVE
    if (hasLiveData) {
        std::memcpy(nextFrame, cachedFrame, kFrameBytes);
        if (stale) panel::status(nextFrame, "OLD");
    }
#endif
    drawFrame(nextFrame);
    contentDirty = false;
}
}

// Arduino calls setup once at power-on, then loop repeatedly. No custom main is needed.
void setup() {
    Serial.begin(115200);
    delay(1000);
    uint8_t mac[6];
    if (esp_read_mac(mac, ESP_MAC_WIFI_STA) == ESP_OK)
        Serial.printf("Wi-Fi station MAC: %02X:%02X:%02X:%02X:%02X:%02X\n", mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
    pinMode(7, OUTPUT); // Preserve the board's display power/control pin.
    digitalWrite(7, HIGH);
    delay(100);
    Serial.printf("MORNING_BRIEFING: %s\n", WORKSHOP_LIVE ? "live" : "demo/offline");
    showMorningBriefing();
#if WORKSHOP_LIVE
    // Let the initial e-paper refresh settle before the first network update.
    pollSchedule.start(millis(), kMinimumRefreshMs);
    requestQueue = xQueueCreate(1, sizeof(bool));
    resultQueue = xQueueCreate(1, sizeof(FetchResult));
    if (!requestQueue || !resultQueue || xTaskCreatePinnedToCore(networkTask, "live-data", 24576, nullptr, 1, nullptr, 0) != pdPASS) {
        if (requestQueue) vQueueDelete(requestQueue);
        if (resultQueue) vQueueDelete(resultQueue);
        requestQueue = nullptr;
        resultQueue = nullptr;
        Serial.println("LIVE_UNAVAILABLE: could not allocate network task; sample remains visible");
    }
#endif
}

void loop() {
    delay(10);
#if WORKSHOP_LIVE
    collectNetworkResult();
    if (contentDirty && millis()-lastRefresh >= kMinimumRefreshMs) showMorningBriefing();
    if (requestQueue && !fetchPending && pollSchedule.due(millis())) {
        const bool request = true;
        if (xQueueSend(requestQueue, &request, 0) == pdTRUE) fetchPending = true;
    }
#endif
}
