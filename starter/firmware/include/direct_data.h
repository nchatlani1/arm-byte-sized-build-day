#pragma once
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <algorithm>
#include <ctime>
#include <cmath>
#include "settings.h"
#include "frames.h"
#include "panel_canvas.h"
extern const uint8_t caBundle[] asm("_binary__generated_x509_crt_bundle_bin_start");
extern const uint8_t caBundleEnd[] asm("_binary__generated_x509_crt_bundle_bin_end");
namespace direct {
static time_t retryAt = 0;
inline uint32_t retryDelayMs() {
    const time_t now = time(nullptr);
    if (now >= retryAt) return 0;
    return static_cast<uint32_t>(std::min<uint64_t>(
        static_cast<uint64_t>(retryAt - now) * 1000, UINT32_MAX / 2));
}
inline String encode(const String& input) {
    String result;const char* hex="0123456789ABCDEF";
    for(size_t i=0;i<input.length();++i){const uint8_t c=input[i];
        if(isalnum(c)||c=='-'||c=='_'||c=='.'||c=='~')result+=char(c);
        else{result+='%';result+=hex[c>>4];result+=hex[c&15];}}
    return result;
}
class Body:public Stream {
public:
    String value;
    size_t write(uint8_t c)override{if(value.length()>=65536)return 0;value+=char(c);return 1;}
    size_t write(const uint8_t* data,size_t length)override {
        if(value.length()+length>65536)return 0;
        return value.concat(reinterpret_cast<const char*>(data),length)?length:0;
    }
    int available()override{return 0;}int read()override{return -1;}int peek()override{return -1;}void flush()override{}
};

inline int request(const String& url, JsonDocument& json) {
    if (time(nullptr) < retryAt) return -2;
    if (!url.startsWith("https://")) return -3;
    WiFiClientSecure client;
    client.setCACertBundle(caBundle, caBundleEnd - caBundle);
    HTTPClient http;
    http.setConnectTimeout(10000);
    http.setTimeout(12000);
    http.begin(client, url);
    const char* keys[] = {"Retry-After"};
    http.collectHeaders(keys, 1);
    http.setUserAgent("CrowPanelWorkshop/1.0");
    int code = http.GET();
    if (code == 429) retryAt = time(nullptr) + std::max(60L, http.header("Retry-After").toInt());
    if (code == 200) {
        Body buffer;
        if (http.writeToStream(&buffer) < 0 || deserializeJson(json, buffer.value)) code = -4;
    }
    if (code != 200) Serial.printf("API_UNAVAILABLE: status %d (credentials omitted)\n", code);
    http.end();
    return code;
}
inline bool clockReady() {
    configTzTime(LOCAL_TIMEZONE,"pool.ntp.org","time.nist.gov");
    const uint32_t started=millis();
    while(time(nullptr)<1700000000&&millis()-started<10000)delay(100);
    if(time(nullptr)<1700000000){Serial.println("NTP_UNAVAILABLE: time is needed to validate HTTPS certificates");return false;}
    return true;
}
inline String weather(int code) {
    if(code==0)return "Sunny";if(code==1||code==2)return "Partly cloudy";if(code==3)return "Cloudy";
    if(code==45||code==48)return "Fog";if(code==71||code==73||code==75||code==77||code==85||code==86)return "Snow";if(code>=95)return "Thunderstorm";return "Rain";
}
inline bool morning(uint8_t* frame) {
    JsonDocument forecast,quote;
    String host=OPEN_METEO_API_KEY[0]?"customer-api.open-meteo.com":"api.open-meteo.com";
    String url="https://"+host+"/v1/forecast?latitude="+String(kWeatherLatitude)+"&longitude="+kWeatherLongitude+"&current=temperature_2m,weather_code&temperature_unit="+(kWeatherUnit[0]=='C'?"celsius":"fahrenheit");
    if(OPEN_METEO_API_KEY[0])url+="&apikey="+encode(OPEN_METEO_API_KEY);
    String quoteUrl="https://query1.finance.yahoo.com/v8/finance/chart/"+encode(kStockSymbol)+"?range=1d&interval=1d";
    const int weatherStatus=request(url,forecast);
    if(weatherStatus!=200){Serial.printf("WEATHER_UNAVAILABLE: request status %d\n",weatherStatus);return false;}
    const int stockStatus=request(quoteUrl,quote);
    if(stockStatus!=200){Serial.printf("STOCK_UNAVAILABLE: request status %d\n",stockStatus);return false;}
    JsonVariant meta=quote["chart"]["result"][0]["meta"];
    // Reject provider errors, wrong tickers and non-USD quotes before drawing a dollar price.
    if(!quote["chart"]["error"].isNull()){Serial.println("STOCK_UNAVAILABLE: provider_error");return false;}
    if(meta["symbol"].as<String>()!=kStockSymbol){Serial.println("STOCK_UNAVAILABLE: symbol_mismatch");return false;}
    if(meta["currency"].as<String>()!="USD"){Serial.println("STOCK_UNAVAILABLE: currency_mismatch");return false;}
    if(!meta["regularMarketPrice"].is<double>()){Serial.println("STOCK_UNAVAILABLE: invalid_price_type");return false;}
    if(!meta["regularMarketTime"].is<long>()){Serial.println("STOCK_UNAVAILABLE: invalid_time_type");return false;}
    double price=meta["regularMarketPrice"].as<double>(),temperature=forecast["current"]["temperature_2m"]|NAN;
    time_t stamp=meta["regularMarketTime"].as<long>();
    if(price<=0||!std::isfinite(price)){Serial.println("STOCK_UNAVAILABLE: invalid_price");return false;}
    if(stamp<=0){Serial.println("STOCK_UNAVAILABLE: invalid_time");return false;}
    if(!std::isfinite(temperature)){Serial.println("WEATHER_UNAVAILABLE: invalid_temperature");return false;}
    panel::clear(frame,54,29,96,40);panel::clear(frame,160,51,82,40);
    panel::text(frame,String(lround(temperature))+" "+kWeatherUnit,54,29,24,96);
    panel::text(frame,weather(forecast["current"]["weather_code"]|0),54,56,12,96);
    panel::text(frame,"$"+String(price,2),160,51,16,82);
    char date[20];tm when;gmtime_r(&stamp,&when);strftime(date,sizeof(date),"%m/%d %H:%M",&when);
    panel::text(frame,date,160,76,12,80);panel::status(frame,"LIVE");return true;
}

inline bool fetch(uint8_t* frame) {
    // Morning Briefing fetches weather and the selected stock quote as one valid update.
    if (!clockReady()) return false;
    return morning(frame);
}
}
