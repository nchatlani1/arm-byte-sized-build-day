#include <cassert>
#include <string>
#include "integration_data.h"
#include "companion_lines.h"
int main(){
    meeting::LineBuffer input;
    for (int i=0;i<384;++i) assert(!input.push('x'));
    assert(!input.push('\n'));
    assert(!input.push('o'));assert(!input.push('k'));
    assert(std::string(input.push('\n'))=="ok");
    assert(!input.push('a'));assert(!input.push('\0'));assert(!input.push('b'));
    assert(!input.push('\n'));

    integration::Data calendar;
    JsonDocument doc;
    assert(!deserializeJson(doc,R"({"status":"ok","title":"Design review","time":"Fri 10:30 AM","lease":180})"));
    assert(calendar.apply(doc,1000,false));
    assert(calendar.status==integration::Status::Ok&&!calendar.old);
    const auto accepted=calendar;
    doc["title"]=std::string(121,'x');
    assert(!calendar.apply(doc,2000,false));assert(calendar.equivalent(accepted));
    doc["title"]="bad\nline";assert(!calendar.apply(doc,2000,false));
    doc["title"]="good";doc["lease"]=181;assert(!calendar.apply(doc,2000,false));
    doc["lease"]=-1;assert(!calendar.apply(doc,2000,false));
    assert(!calendar.expire(180999));assert(calendar.expire(181000));assert(calendar.old);
    doc["lease"]=30;assert(calendar.apply(doc,181001,false));assert(!calendar.old);
    doc.clear();doc["status"]="off";doc["lease"]=180;
    assert(calendar.apply(doc,0,false));assert(!calendar.active());assert(!calendar.expire(1000000));
    doc["status"]="empty";doc["lease"]=1;
    assert(calendar.apply(doc,UINT32_MAX-500,false));assert(!calendar.expire(400));assert(calendar.expire(500));
    integration::Data music;
    assert(!deserializeJson(doc,R"({"status":"ok","track":"Track","artist":"Artist","playing":true,"lease":180})"));
    assert(music.apply(doc,0,true)&&music.playing);
    doc["playing"]="true";assert(!music.apply(doc,1,true));
    doc["playing"]=false;doc["artist"]=std::string(65,'a');assert(!music.apply(doc,1,true));
    doc["artist"]="Artist";assert(music.apply(doc,1,true)&&!music.playing);
    doc["status"]="invented";assert(!music.apply(doc,2,true));
}
