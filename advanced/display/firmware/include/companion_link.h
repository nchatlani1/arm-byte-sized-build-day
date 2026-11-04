#pragma once
// Transport and account data only. Firmware owns every display coordinate.
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLE2902.h>
#include <BLESecurity.h>
#include <esp_mac.h>
#include <esp_system.h>
#include <atomic>
#include "companion_lines.h"
#include "frames.h"
#include "integration_data.h"
namespace bridge {
constexpr char kService[]="9d410001-35d6-4eab-9f97-cd074073ab40";
constexpr char kWrite[]="9d410002-35d6-4eab-9f97-cd074073ab40";
constexpr char kNotify[]="9d410003-35d6-4eab-9f97-cd074073ab40";
char deviceName[25]={};
BLEServer* server=nullptr;
BLECharacteristic* notifyCharacteristic=nullptr;
BLESecurity* security=nullptr;
std::atomic<bool> authenticated(false),connected(false),pairing(false),paired(false),restartAdvertising(false);
std::atomic<uint32_t> pairingCode(0);
uint32_t pairingStarted=0;
bool showPairing=false,pairingRequested=false,changed=false;
struct BLEChunk {uint8_t size;char data[180];};
QueueHandle_t bleQueue=nullptr;
meeting::LineBuffer usbLine,bleLine;
integration::Data calendar,music;
void reply(const String& text,unsigned channel) {
    if(channel==0)Serial.println(text);
    else if(authenticated&&connected&&notifyCharacteristic){
        const String payload=text+"\n";
        for(size_t offset=0;offset<payload.length();offset+=20){
            notifyCharacteristic->setValue(reinterpret_cast<uint8_t*>(const_cast<char*>(payload.c_str()+offset)),std::min(size_t(20),payload.length()-offset));
            notifyCharacteristic->notify();delay(8);
        }
    }
}
// Only validated metadata is accepted. Layouts and credentials never arrive over the link.
void command(const char* line,unsigned channel){
    JsonDocument doc;if(deserializeJson(doc,line)||!doc.is<JsonObject>())return;
    const char* op=doc["op"]|"";const uint32_t id=doc["id"]|0u;bool ok=false;
    if(!std::strcmp(op,"hello"))ok=true;
    else if(!std::strcmp(op,"calendar")||!std::strcmp(op,"spotify")){
        const bool enabled = !std::strcmp(op,"calendar") ? WORKSHOP_CALENDAR : WORKSHOP_SPOTIFY;
        if (!enabled) {
            // Older protocol-2 clients send off packets for unused sources.
            ok = !std::strcmp(doc["status"] | "", "off");
        } else {
        auto& target=!std::strcmp(op,"calendar")?calendar:music;
        const auto previous=target;
        ok=target.apply(doc,millis(),!std::strcmp(op,"spotify"));
        if(ok&&!target.equivalent(previous))changed=true;
        }
    }
    JsonDocument ack;ack["op"]=op;ack["id"]=id;ack["ok"]=ok;
    if(!std::strcmp(op,"hello")){ack["protocol"]=2;ack["mode"]="data";
        JsonArray capabilities=ack["capabilities"].to<JsonArray>();
        if(WORKSHOP_CALENDAR)capabilities.add("calendar");
        if(WORKSHOP_SPOTIFY)capabilities.add("spotify");}
    String result;serializeJson(ack,result);reply("CP_ACK "+result,channel);
}
bool bonded(const uint8_t* address) {
    int count=esp_ble_get_bond_device_num();
    if(count<=0||count>32)return false;
    esp_ble_bond_dev_t devices[32];
    if(esp_ble_get_bond_device_list(&count,devices)!=ESP_OK)return false;
    for(int i=0;i<count;++i)if(std::memcmp(devices[i].bd_addr,address,6)==0)return true;
    return false;
}
class ServerCallbacks:public BLEServerCallbacks {
    void onConnect(BLEServer* instance,esp_ble_gatts_cb_param_t* param) override {
        connected=true;authenticated=false;
        if(!pairing&&!bonded(param->connect.remote_bda)){instance->disconnect(param->connect.conn_id);return;}
        esp_ble_set_encryption(param->connect.remote_bda,ESP_BLE_SEC_ENCRYPT_MITM);
    }
    void onDisconnect(BLEServer*) override {connected=false;authenticated=false;restartAdvertising=true;}
};
class SecurityCallbacks:public BLESecurityCallbacks {
    uint32_t onPassKeyRequest() override {return pairingCode.load();}
    void onPassKeyNotify(uint32_t code) override {pairingCode=code;}
    bool onSecurityRequest() override {return connected.load();}
    bool onConfirmPIN(uint32_t) override {return false;}
    void onAuthenticationComplete(esp_ble_auth_cmpl_t result) override {
        authenticated=result.success;
        if(result.success){pairing=false;paired=true;}
        else if(server)server->disconnect(server->getConnId());
    }
};
class WriteCallbacks:public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* characteristic) override {
        if(!authenticated||!bleQueue)return;
        const std::string value=characteristic->getValue();
        if(value.empty()||value.size()>180)return;
        BLEChunk chunk;chunk.size=value.size();std::memcpy(chunk.data,value.data(),value.size());
        // The host waits for the complete-command ACK; a full queue causes a
        // timeout instead of applying a partial or unauthenticated command.
        xQueueSend(bleQueue,&chunk,0);
    }
};
void begin(){
    bleQueue=xQueueCreate(32,sizeof(BLEChunk));
    uint8_t mac[6];esp_read_mac(mac,ESP_MAC_BT);snprintf(deviceName,sizeof(deviceName),"CrowPanel-%02X%02X%02X",mac[3],mac[4],mac[5]);
    BLEDevice::init(deviceName);BLEDevice::setEncryptionLevel(ESP_BLE_SEC_ENCRYPT_MITM);BLEDevice::setSecurityCallbacks(new SecurityCallbacks());
    security=new BLESecurity();security->setAuthenticationMode(ESP_LE_AUTH_REQ_SC_MITM_BOND);security->setCapability(ESP_IO_CAP_OUT);
    security->setInitEncryptionKey(ESP_BLE_ENC_KEY_MASK|ESP_BLE_ID_KEY_MASK);security->setRespEncryptionKey(ESP_BLE_ENC_KEY_MASK|ESP_BLE_ID_KEY_MASK);
    server=BLEDevice::createServer();server->setCallbacks(new ServerCallbacks());
    BLEService* service=server->createService(kService);
    auto* input=service->createCharacteristic(kWrite,BLECharacteristic::PROPERTY_WRITE);
    input->setAccessPermissions(ESP_GATT_PERM_WRITE_ENC_MITM);input->setCallbacks(new WriteCallbacks());
    notifyCharacteristic=service->createCharacteristic(kNotify,BLECharacteristic::PROPERTY_NOTIFY);
    auto* cccd=new BLE2902();cccd->setAccessPermissions(ESP_GATT_PERM_READ_ENC_MITM|ESP_GATT_PERM_WRITE_ENC_MITM);notifyCharacteristic->addDescriptor(cccd);
    service->start();auto* advertising=BLEDevice::getAdvertising();advertising->addServiceUUID(kService);advertising->setScanResponse(true);advertising->start();
    Serial.println("CP_READY: protocol=2 data-only; MENU 2s pair; EXIT 8s forget bonds");
}
// Pump bounded input and pairing gestures; draw only after the e-paper safety interval.
void poll(bool mayDraw){
    for(unsigned i=0;i<512&&Serial.available();++i){const char* line=usbLine.push(Serial.read());if(line)command(line,0);}
    BLEChunk chunk;
    while(bleQueue&&xQueueReceive(bleQueue,&chunk,0)==pdTRUE)for(unsigned i=0;i<chunk.size;++i){const char* line=bleLine.push(chunk.data[i]);if(line)command(line,1);}
    if(restartAdvertising.exchange(false))BLEDevice::startAdvertising();
    static uint32_t menuDown=0,exitDown=0;static bool menuLatched=false,exitLatched=false;
    if(digitalRead(2)==LOW){if(!menuDown)menuDown=millis();if(!menuLatched&&millis()-menuDown>=2000){menuLatched=true;pairingRequested=true;}}
    else{menuDown=0;menuLatched=false;}
    if(digitalRead(1)==LOW){if(!exitDown)exitDown=millis();if(!exitLatched&&millis()-exitDown>=8000){
        exitLatched=true;if(connected)server->disconnect(server->getConnId());
        int count=esp_ble_get_bond_device_num();if(count>0&&count<=32){esp_ble_bond_dev_t devices[32];if(esp_ble_get_bond_device_list(&count,devices)==ESP_OK)for(int i=0;i<count;++i)esp_ble_remove_bond_device(devices[i].bd_addr);}
        pairingRequested=true;
    }}else{exitDown=0;exitLatched=false;}
    if(pairingRequested&&mayDraw){
        pairingRequested=false;pairingCode=100000+(esp_random()%900000);security->setStaticPIN(pairingCode.load());
        security->setAuthenticationMode(ESP_LE_AUTH_REQ_SC_MITM_BOND);security->setCapability(ESP_IO_CAP_OUT);
        pairing=true;showPairing=true;pairingStarted=millis();changed=true;
    }
    if(paired.exchange(false)||(pairing&&millis()-pairingStarted>=120000)){pairing=false;showPairing=false;changed=true;}
    if(calendar.expire(millis()))changed=true;
    if(music.expire(millis()))changed=true;
}
// Customize live account layout here. tools/render.py controls the sample preview.
void apply(uint8_t* frame,uint8_t project){
    if(showPairing){
        std::memset(frame,0xff,4000);panel::centered(frame,"PAIR CROWPANEL",14,16);
        panel::centered(frame,"Enter this code on laptop",42,12);
        char code[8];snprintf(code,sizeof(code),"%06lu",static_cast<unsigned long>(pairingCode.load()));
        panel::centered(frame,code,63,24);panel::footer(frame,String(deviceName)+" / 2 MIN");return;
    }
    using integration::Status;
    if((project==kMorningBriefingScreen||project==kCalendarScreen)&&WORKSHOP_CALENDAR&&calendar.active()){
        const bool usable=!calendar.old&&calendar.status==Status::Ok;
        String title=usable?String(calendar.title):calendar.status==Status::Empty&&!calendar.old?"No upcoming meetings":"Calendar update needed";
        if(project==kMorningBriefingScreen)panel::footer(frame,usable?String(calendar.time)+" "+title:title);
        else{
            panel::clear(frame,10,28,230,71);
            panel::text(frame,usable?"NEXT "+String(calendar.time):"NEXT --",10,30,16,230);
            panel::wrapped(frame,title,10,50,230);
            panel::text(frame,usable?"From your work calendar":"Open companion to reconnect",10,85,12,230);
            panel::status(frame,calendar.old?"OLD":calendar.status==Status::Unavailable?"WAIT":"LIVE");
        }
    }
    if(project==kNowPlayingScreen&&WORKSHOP_SPOTIFY&&music.active()){
        panel::clear(frame,10,29,230,71);
        const bool usable=!music.old&&music.status==Status::Ok;
        const String track=usable?String(music.title):music.status==Status::Empty&&!music.old?"Nothing playing":"Spotify update needed";
        panel::wrapped(frame,track,10,31,230);
        panel::text(frame,usable?String(music.detail):"Open companion",10,72,12,230);
        panel::text(frame,usable?(music.playing?"PLAYING":"PAUSED"):"",10,87,12,230);
        panel::footer(frame,"SPOTIFY");panel::status(frame,music.old?"OLD":music.status==Status::Unavailable?"WAIT":"LIVE");
    }
}
}
