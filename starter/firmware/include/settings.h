#pragma once
// Offline builds deliberately ignore any local Wi-Fi header.
#if !defined(WORKSHOP_FORCE_DEMO) && __has_include("secrets.h")
#include "secrets.h"
#endif
#ifndef WORKSHOP_LIVE
#define WORKSHOP_LIVE 0
#endif
#ifdef WORKSHOP_FORCE_DEMO
#undef WORKSHOP_LIVE
#define WORKSHOP_LIVE 0
#endif
#ifndef HOME_WIFI_SSID
#define HOME_WIFI_SSID ""
#endif
#ifndef HOME_WIFI_PASSWORD
#define HOME_WIFI_PASSWORD ""
#endif
#ifndef OFFICE_WIFI_SSID
#define OFFICE_WIFI_SSID ""
#endif
#ifndef OFFICE_WIFI_PASSWORD
#define OFFICE_WIFI_PASSWORD ""
#endif
#ifndef WIFI_SSID
#define WIFI_SSID ""
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD ""
#endif
#ifndef OPEN_METEO_API_KEY
#define OPEN_METEO_API_KEY ""
#endif
#ifndef LOCAL_TIMEZONE
#define LOCAL_TIMEZONE "UTC0"
#endif
