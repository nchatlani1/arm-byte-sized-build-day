# Morning Briefing code guide

The first customization is `device.json`: your ticker and ZIP. Wi-Fi lives in
private `.env`, copied from `.env.example`. Both files are in the starter folder.

## Firmware flow

Arduino runs `firmware/src/main.cpp`’s `setup()` once, then calls `loop()` repeatedly.
`setup()` powers the display and draws the compiled DEMO sample. The live build
starts a separate network task. It joins a configured home/office network, gets an
NTP clock for HTTPS certificate validation, fetches weather/stock and validates
both responses. `loop()` receives the result and draws only changed pixels after
the minimum interval. Failures retain the last good screen marked OLD, or DEMO
before the first success. There is one screen and no wheel navigation.

| File | Responsibility |
| --- | --- |
| `firmware/src/main.cpp` | Startup, network task, cached frame, display timing |
| `firmware/include/direct_data.h` | Open-Meteo weather, Yahoo USD quote, response checks and live drawing |
| `firmware/include/wifi_profiles.h` | Home first, then office fallback, connection diagnostics |
| `firmware/include/panel_canvas.h` | Text/pixel primitives |
| `firmware/include/live_poll.h` | Poll deadlines and bounded retry delays |
| `tools/render.py` | Single Morning Briefing sample/layout preview |
| `tools/pack_frames.py` | Generated frame and public ticker/location values |
| `tools/device_config.py` | Public JSON checks and build-time ZIP lookup/cache |
| `tools/export_config.py` | Private `.env` to ignored secrets.h; no account settings |
| `firmware/lib/ElecrowEPD/` | Retained panel driver/font and provenance |

Stock/weather poll every 15 minutes. Automatic physical redraws are at least
30 seconds apart. The vendor clear/update/draw/update sequence visibly flashes;
preserve that sequence and the supported panel/PSRAM/pin settings.

ZIP 92128 has bundled coordinates 33.0067, -117.069. Custom ZIPs resolve once via
Zippopotam.us at build time with TLS checks, then use `.generated/zip-<ZIP>.json`.
The board contacts only the live providers at runtime. Default builds need no ZIP
lookup. A successful build does not establish upload, Wi-Fi or physical results.

Use Serial monitor at 115200 baud and check upload/display, Wi-Fi association/IP,
NTP/TLS, valid provider responses and physical LIVE pixels separately. Close the
monitor before another upload or opening the advanced companion USB connection.
Provider availability and real board/network behavior require a physical pilot.

Calendar, Spotify, Bluetooth and multiple-screen code live in `advanced/display`,
with app source under `advanced/companion-apps`. This starter stays independent.
