#pragma once
#include <WiFi.h>
#include "settings.h"
// Only join explicitly configured SSIDs. Prefer home when both are visible.
inline bool connectWorkshopWiFi() {
    // Register once from the network task, before starting Wi-Fi. The event task
    // only logs fixed markers; it does not share mutable connection state.
    static const wifi_event_id_t diagnostics=WiFi.onEvent([](WiFiEvent_t event,WiFiEventInfo_t info) {
        if(event==ARDUINO_EVENT_WIFI_STA_DISCONNECTED)
            Serial.printf("WIFI_EVENT: disconnected reason %u\n",static_cast<unsigned>(info.wifi_sta_disconnected.reason));
        else if(event==ARDUINO_EVENT_WIFI_STA_CONNECTED)
            Serial.printf("WIFI_EVENT: associated\n");
        else if(event==ARDUINO_EVENT_WIFI_STA_GOT_IP)
            Serial.printf("WIFI_EVENT: got_ip\n");
    });
    (void)diagnostics;
    if(WiFi.status()==WL_CONNECTED)return true;
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    struct Profile{const char* ssid;const char* password;};
    const Profile profiles[]={{HOME_WIFI_SSID,HOME_WIFI_PASSWORD},{OFFICE_WIFI_SSID,OFFICE_WIFI_PASSWORD},{WIFI_SSID,WIFI_PASSWORD}};
    const int count=WiFi.scanNetworks();
    if(count>=0)Serial.printf("WIFI_SCAN: %d network(s) visible\n",count);
    bool attempted=false;
    unsigned profileIndex=0; // 0=home, 1=office, 2=fallback; diagnostics omit network identifiers.
    for(const auto& profile:profiles) {
        const unsigned index=profileIndex++;
        if(!profile.ssid[0])continue;
        bool found=false;
        for(int i=0;i<count;++i)if(WiFi.SSID(i)==profile.ssid){
            found=true;
            Serial.printf("WIFI_PROFILE_MATCH: profile %u rssi %ld channel %ld auth %u\n",index,
                static_cast<long>(WiFi.RSSI(i)),static_cast<long>(WiFi.channel(i)),
                static_cast<unsigned>(WiFi.encryptionType(i)));
            break;
        }
        if(!found){
            if(count>=0)Serial.printf("WIFI_PROFILE_UNAVAILABLE: profile %u not_visible\n",index);
            continue;
        }
        attempted=true;
        WiFi.disconnect();
        if(profile.password[0])WiFi.begin(profile.ssid,profile.password);else WiFi.begin(profile.ssid);
        const uint32_t started=millis();
        while(WiFi.status()!=WL_CONNECTED&&millis()-started<15000)delay(100);
        if(WiFi.status()==WL_CONNECTED) {
            WiFi.scanDelete();
            Serial.printf("Wi-Fi connected: %s | IP: %s\n",profile.ssid,WiFi.localIP().toString().c_str());
            return true;
        }
        Serial.printf("WIFI_PROFILE_UNAVAILABLE: profile %u join_failed status %d\n",index,static_cast<int>(WiFi.status()));
    }
    WiFi.scanDelete();
    if(count<0)Serial.printf("WIFI_DIAGNOSTIC: scan_failed status %d\n",count);
    else if(!attempted)Serial.println("WIFI_DIAGNOSTIC: no_configured_profile_visible");
    Serial.println("WIFI_UNAVAILABLE: configured home/office SSIDs not connected");
    return false;
}
