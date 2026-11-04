# Advanced display code and extensions

## One screen, two builds

| Build/task | Behavior |
| --- | --- |
| `workshop_demo` / Build or Upload offline starter | Compiled sample, Wi-Fi forced off; local `.env` and headers ignored |
| `workshop` / Build or Upload live stock and weather | Same screen; direct board HTTPS when `.env` enables it; otherwise samples |
| Serial monitor | Selected board port, 115200 baud; close before uploading |

Use a supported DIE01021S / JD79661 board. Preserve vendor driver, waveform,
PSRAM, pin and board settings. A USB port needs a working data cable/driver;
upload success and a physical display update are separate checkpoints.

## Personalize

`device.json` contains only your ticker, US ZIP, C/F, title and footer. The build
resolves the ZIP to an approximate location, stores coordinates in firmware and
renders the sample. ZIP `92128` has bundled San Diego coordinates. Other ZIPs use
one HTTPS lookup at `https://api.zippopotam.us/us/<ZIP>` and an ignored
`.generated/zip-<ZIP>.json` cache. Deleting `.generated` requires resolving custom
ZIPs again; an unavailable lookup stops the build instead of using the wrong city.
PlatformIO uses its installed certifi roots for the lookup, with TLS verification
enabled. The board never needs the ZIP service at runtime.

The weather comes from Open-Meteo, the USD stock quote from Yahoo's chart endpoint.
No personal account is used for these feeds. Initial samples are illustrative;
changing the ticker hides the old sample price. Provider availability, terms and
network access need an event pilot. Automatic stock/weather polls are 15 minutes;
the stock timestamp is UTC and can describe the last trading session.
Live failure retains earlier successful data with OLD, or keeps DEMO before the
first success. Office Wi-Fi failure does not block the offline exercise.

The build creates `.generated/frames.h` using `tools/render.py`, the sample JSON
and bundled vendor font. Only Python's standard library is used by that renderer;
the TLS-bundle tool uses certifi already installed with PlatformIO. JSON supplies
values for existing fields; drawing code determines layout and visible fields.
Optional previews: `python3 -B tools/render.py` writes `.generated/preview/`.

| Edit | File |
| --- | --- |
| Optional C++ footer, application flow and 15-minute poll interval | `firmware/src/main.cpp` |
| Offline drawing and registered screens | `tools/render.py` |
| Sample stock/weather values | `templates/morning_briefing/content.json` |
| Live stock/weather drawing and provider checks | `firmware/include/direct_data.h` |
| Pixel/text primitives | `firmware/include/panel_canvas.h` |
| Wheel debounce and manual display timing | `firmware/include/carousel.h` |

## Add a second screen later

Morning Briefing and both account screens are active by default here. Disabled entries have no empty carousel pages. To add a static
screen, create `templates/my_status/content.json`, for example `{"message":"Hello"}`.
In `tools/render.py`, above `RENDERERS`, add:

```python
def draw_my_status(canvas, data):
    canvas.header('My status', 'demo')
    canvas.wrapped(data.get('message', 'Hello'), 10, 40, 230)
    canvas.footer('MY SECOND SCREEN')
```

Add `'my_status': draw_my_status` to `RENDERERS`; keep Morning Briefing first.
The calendar and Spotify entries are opt-in and appear only when enabled.
Build/upload normally. The packer generates names, frames and screen count.
Keep `morning_briefing` first; one to eight registered screens are supported.
Wheel navigation and persisted selection activate with multiple screens. Existing
debounce samples through blocking e-paper refreshes; one press needs a release
before the next. `kManualRefreshMs` controls the minimum between manual screen
changes; `kMinimumRefreshMs` limits automatic changes. With one screen the wheel
has no second page to select. Adding a runtime data source also needs C++ fetching
and drawing; registering a sample alone does not add an online integration.

## Optional companion projects

This advanced project contains calendar and Spotify receivers.
Both are enabled by default here; the separate starter has neither. Add `"extensions": {"calendar": true, "spotify": true}`
to `device.json`, keeping the existing settings. Build/upload with the same tasks.
Use either flag on its own if you want only one extension.
The build generates named screen IDs, so adding a static screen does not change
which account data reaches which screen. Morning Briefing stays first.

| Project | Runtime requirements |
| --- | --- |
| Morning Briefing stock/weather | Board power + Wi-Fi for live feeds; no companion |
| Static screens | Board power only |
| Calendar extension | Nearby awake laptop running the companion, permitted Apple Calendar/classic Outlook, USB/BLE |
| Spotify extension | Nearby awake laptop running the companion, eligible Spotify authorization, USB/BLE |

[Companion downloads, setup and Codex prompts](COMPANION.md).
Use this advanced/display project; starter firmware has no account receiver. The app sends account metadata; C++ owns
layout, display timing and controls. Offline builds keep Wi-Fi off, but explicitly
enabled companion extensions still accept USB/Bluetooth account data.
An autonomous Microsoft Graph or direct Spotify integration is possible as a
future project, with separate OAuth/tenant provisioning; it is not this extension path.

## 120-minute sequence

For 65 people at 13 tables, five facilitators each cover two or three tables.

| Minutes | Activity/checkpoint |
| --- | --- |
| 0–10 | Welcome, board/controller and USB orientation |
| 10–30 | Casey Hillers' browser introduction and Snake |
| 30–40 | Save Python; stop/disconnect browser serial; open VS Code/PlatformIO |
| 40–55 | Offline build/upload; confirm sample display |
| 55–90 | Personalize ticker/ZIP; rebuild/upload; optional units/layout changes |
| 90–110 | Direct stock/weather Wi-Fi or offline layout/second-screen exercise |
| 110–120 | Demos and next projects |

Preflight: install dependencies, confirm board/port, resolve any custom ZIP and
rehearse one offline upload. Save Python before replacing MicroPython; facilitators
own restoration through the existing approved process. Close every competing
serial connection before PlatformIO upload. Do not change laptop VPN/network
settings or register boards without the organizer's authorization.

Check live stages separately: upload/display; Wi-Fi association and DHCP IP; DNS,
NTP clock and TLS; valid weather and stock responses; physical LIVE display.
Markers include WIFI_EVENT: got_ip, LIVE_FETCH_OK and DISPLAY_READY. A compiler
pass cannot validate these stages, and Arduino does not guarantee a Wi-Fi fix.
Fast finishers add a second static screen or extend C++ drawing. If network or ZIP
lookup is unavailable, use ZIP 92128 and workshop_demo; no account setup is needed.

## Maintainer checks

```sh
python3 -B -m unittest discover -s tests -v
c++ -std=c++11 -Ifirmware/include tests/carousel_test.cpp -o /tmp/crowpanel-carousel-test
/tmp/crowpanel-carousel-test
c++ -std=c++11 -Ifirmware/include tests/live_poll_test.cpp -o /tmp/crowpanel-live-poll-test
/tmp/crowpanel-live-poll-test
```

In a PlatformIO IDE terminal, `pio run -e workshop_demo` builds offline.
After creating `.env`, `pio run -e workshop` builds the direct live branch.
Supply your own board port with `--target upload --upload-port YOUR_PORT`.
Physical display/buttons, live board data, Windows and on-site networking remain
manual checks. Keep private headers, ZIP caches, `.pio` and credential-bearing
compiled firmware out of shared source archives.
