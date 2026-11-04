# Starter: Morning Briefing

One screen: **ARM stock + San Diego weather, ZIP 92128**. This folder contains
only that application. The board fetches live stock/weather directly over Wi-Fi.

## Edit these first

| Entry point | Change |
| --- | --- |
| [`device.json`](device.json) | `stock_symbol`, `weather.zip_code`, C/F, title and footer |
| [`.env`](.env) | Already configured for `Guest-AccessNG`; edit here for another network |
| [`firmware/src/main.cpp`](firmware/src/main.cpp) | Read the commented application flow; later customize C++ behavior |

`templates/morning_briefing/content.json` is the single offline sample. Leave it
alone for the first exercise: the build applies your device.json values to it.
There is no calendar receiver, Spotify screen, Bluetooth code or carousel here.

## Build and upload

1. Open this folder or `CrowPanel-Starter.code-workspace` in VS Code. Open the
   [PlatformIO IDE extension](https://marketplace.visualstudio.com/items?itemName=platformio.platformio-ide), click **Install**,
   allow it to open VS Code, and finish installing there. Wait for toolchain setup
   to complete before building; stable PlatformIO Core **6.2.0 or newer** is required.
   The starter pins Arduino 3.3.12 / ESP-IDF 5.5.5;
   the older ESP-IDF 4.4.7 stack timed out while joining Guest-AccessNG on a
   registered workshop board, while the newer stack connected successfully.
2. Save Casey’s browser work and disconnect its USB access. C++ upload replaces
   the MicroPython firmware. Use a USB data cable and the supported DIE01021S /
   JD79661 board. Find its port under **PlatformIO → Devices**.
3. Run **Tasks: Run Task → Build offline starter**, then **Upload offline starter**.
   Enter the board’s port. Check SUCCESS and the physical Morning Briefing screen.
4. Change your ticker and ZIP in `device.json`, save, then upload again. Samples
   say **DEMO**. Changing the ticker hides ARM’s unrelated sample price. Keep ZIPs
   as quoted five-digit strings. Default 92128 builds offline; a new ZIP needs one
   internet lookup on the computer, then uses a local coordinate cache.
5. For live data, `.env` is already supplied with `Guest-AccessNG` and a blank
   password. No copy or edit is needed on that approved open guest network.
   For another approved 2.4 GHz network, edit `.env` directly and leave unused
   networks blank. Run
   **Build live stock and weather**, then **Upload live stock and weather**.
   Allow about a minute for valid data to replace DEMO with **LIVE**.

Office passwords are supported. An approved open network can have a blank
password. Captive portals and enterprise login are unsupported. The supplied
`.env` is tracked and contains public defaults; personal edits appear in Git.
Keep personal settings out of commits and shared ZIPs. Generated secrets.h and
configured firmware stay private. The offline task always
forces Wi-Fi off, regardless of local settings.

## Optional preview and further work

`python3 -B tools/render.py` (Windows: `python -B tools/render.py`) writes PNGs to
`.generated/preview/`. The renderer previews samples/settings; C++ draws live data.
JSON supplies field values, while drawing code determines the layout.

[How this firmware works](docs/WORKSHOP.md). For calendar/Spotify, move to the
separate **[advanced/display project](../advanced/display/)** and its
**[companion apps](../advanced/companion-apps/)**. Enabling an account in an app
cannot add receiver code to this starter: the advanced firmware needs an upload.
