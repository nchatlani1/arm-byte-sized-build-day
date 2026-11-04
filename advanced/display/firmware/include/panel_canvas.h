#pragma once
#include <Arduino.h>
#include <cstring>
#include "EPDfont.h"
namespace panel {
inline void pixel(uint8_t* frame,int x,int y,bool black=true) {
    if(x<0||x>=250||y<0||y>=122)return;
    uint8_t mask=0x80>>(y%8);
    if(black)frame[x*16+y/8]&=~mask;else frame[x*16+y/8]|=mask;
}
inline void clear(uint8_t* frame,int x,int y,int w,int h) {
    for(int row=y;row<y+h;++row)for(int col=x;col<x+w;++col)pixel(frame,col,row,false);
}
inline String ascii(String text) {
    String result;
    for(size_t i=0;i<text.length();++i) {
        const uint8_t ch=text[i];
        if(ch>=32&&ch<=126)result+=char(ch);
        else if((ch&0xc0)!=0x80)result+='?';
    }
    return result;
}
inline void text(uint8_t* frame,String value,int x,int y,int height=16,int maxWidth=230) {
    value=ascii(value);int width=height/2,limit=maxWidth/width;
    if(value.length()>limit)value=value.substring(0,limit-3)+"...";
    for(size_t i=0;i<value.length();++i) {
        const int index=value[i]-32;
        const uint8_t* glyph=height==24?ascii_2412[index]:height==16?ascii_1608[index]:ascii_1206[index];
        for(int row=0;row<height;++row)for(int col=0;col<width;++col)
            if(glyph[row*((width+7)/8)+col/8]&(1<<(col%8)))pixel(frame,x+i*width+col,y+row);
    }
}
inline void centered(uint8_t* frame,String value,int y,int height=12) {
    int limit=230/(height/2);value=ascii(value);
    if(value.length()>limit)value=value.substring(0,limit-3)+"...";
    text(frame,value,(250-value.length()*(height/2))/2,y,height);
}
inline void wrapped(uint8_t* frame,String value,int x,int y,int width) {
    value=ascii(value);const int limit=width/8;
    if(value.length()<=limit){text(frame,value,x,y,16,width);return;}
    int split=value.lastIndexOf(' ',limit);
    if(split<1)split=limit;
    text(frame,value.substring(0,split),x,y,16,width);
    String rest=value.substring(split);rest.trim();
    text(frame,rest,x,y+18,16,width);
}
inline void status(uint8_t* frame,const char* label) {
    clear(frame,208,7,36,12);text(frame,label,208,7,12,36);
}
inline void footer(uint8_t* frame,String value) {
    clear(frame,10,104,230,17);centered(frame,value,106);
}
}
