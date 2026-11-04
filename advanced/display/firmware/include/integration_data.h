#pragma once
#include <ArduinoJson.h>
#include <cstdint>
#include <cstring>

namespace integration {
enum class Status { Off, Ok, Empty, Unavailable };
inline bool text(JsonVariantConst value, char* out, size_t size) {
    if(!value.is<const char*>())return false;
    const JsonString input=value.as<JsonString>();
    if(input.size()>=size)return false;
    for(size_t i=0;i<input.size();++i)if(input.c_str()[i]<32||input.c_str()[i]>126)return false;
    std::memset(out,0,size);std::memcpy(out,input.c_str(),input.size());return true;
}
struct Data {
    Status status=Status::Off;
    char title[121]={},detail[65]={},time[25]={};
    bool playing=false,old=false;
    uint32_t received=0,lease=0;
    bool active()const{return status!=Status::Off;}
    bool expire(uint32_t now){if(!active()||old||now-received<lease)return false;old=true;return true;}
    bool apply(JsonDocument& doc,uint32_t now,bool music) {
        Data next;
        const char* state=doc["status"]|"";
        if(!std::strcmp(state,"off"))next.status=Status::Off;
        else if(!std::strcmp(state,"ok"))next.status=Status::Ok;
        else if(!std::strcmp(state,"empty"))next.status=Status::Empty;
        else if(!std::strcmp(state,"unavailable"))next.status=Status::Unavailable;
        else return false;
        if(!doc["lease"].is<uint32_t>())return false;
        const uint32_t seconds=doc["lease"];
        if(seconds<1||seconds>180)return false;
        if(next.status==Status::Ok){
            if(!text(doc[music?"track":"title"],next.title,sizeof(next.title)))return false;
            if(music){if(!text(doc["artist"],next.detail,sizeof(next.detail))||!doc["playing"].is<bool>())return false;next.playing=doc["playing"];}
            else if(!text(doc["time"],next.time,sizeof(next.time)))return false;
        }
        next.received=now;next.lease=seconds*1000;
        *this=next;return true;
    }
    bool equivalent(const Data& other)const{return status==other.status&&old==other.old&&playing==other.playing&&!std::strcmp(title,other.title)&&!std::strcmp(detail,other.detail)&&!std::strcmp(time,other.time);}
};
}
