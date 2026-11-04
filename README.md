# Arm Byte Sized Build Day — CrowPanel Workshop

After Casey’s browser starter, open **[starter/](starter/)** for Morning Briefing.
The default screen shows **ARM stock and weather for ZIP 92128**. Start by editing
your ticker and ZIP. The supplied `.env` already selects the office guest Wi-Fi
for live data; no file-copy step is needed.

| Folder | What it contains |
| --- | --- |
| [starter/](starter/) | One Morning Briefing template and its C++ firmware. Start here. |
| [advanced/display/](advanced/display/) | Separate display firmware for calendar, Spotify and multiple screens. |
| [advanced/companion-apps/](advanced/companion-apps/) | Mac/Windows companion app source, download status and build tools. |
| [Slides and reference](docs/) | HTML presentation, setup guide and USB driver links. |

Open `CrowPanel-Workshop.code-workspace` to see only the starter in VS Code.
Alternatively use **File → Open Folder → starter**. Do not create a new PlatformIO
project or open both display projects as one PlatformIO project.

## Install PlatformIO

Open the [PlatformIO IDE extension](https://marketplace.visualstudio.com/items?itemName=platformio.platformio-ide), click **Install**,
allow it to open VS Code, and finish installing there. Wait for its toolchain setup
to complete before building. PlatformIO Core is included.

The shipped `.env` files contain public guest-network defaults. Personal Wi-Fi edits
appear in Git: keep those edits out of commits, shared firmware and release ZIPs.

## Starter entry points

- **[`starter/device.json`](starter/device.json)** — ticker, US ZIP, units, title and footer.
- **[`starter/.env`](starter/.env)** — ready-to-use `Guest-AccessNG` settings; edit here for another network.
- **[`starter/firmware/src/main.cpp`](starter/firmware/src/main.cpp)** — commented Morning Briefing application, with Arduino `setup()` and `loop()`.

[Starter instructions](starter/README.md) · [Advanced projects](advanced/README.md) ·
[Companion downloads and setup](advanced/companion-apps/guides/COMPANION-SETUP.md#downloads)

This is one repository. Versioned companion binaries belong in this repository’s
GitHub Releases and are linked from the companion-apps folder.
Mac Apple Silicon and Windows x64 apps are pilots; physical device and account
acceptance remains pending. [Source ZIP](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/download/workshop-v0.1.1/CrowPanel-Workshop-Source.zip) · [Mac Apple Silicon 0.3.2 pilot](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/download/workshop-v0.1.0/CrowPanel-Companion-macOS-arm64-0.3.2.zip) · [Windows x64 0.3.2 pilot](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/download/workshop-v0.1.0/CrowPanel-Companion-Windows-x64-0.3.2.zip) · [Source release notes and checksums](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/tag/workshop-v0.1.1) · [Companion release notes and checksums](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/tag/workshop-v0.1.0).

## Slides and downloads

[View the slides](https://nchatlani1.github.io/arm-byte-sized-build-day/slides/CROWPANEL-INTRO.html) · [Reference page](https://nchatlani1.github.io/arm-byte-sized-build-day/) · [Companion setup](https://nchatlani1.github.io/arm-byte-sized-build-day/slides/CROWPANEL-COMPANION-SETUP.html).

The presentation HTML is included under `docs/slides/`. GitHub Pages serves `main` → `/docs`. Companion binaries are GitHub Release assets; their source is under `advanced/companion-apps/`.

## Licensing

A project-level reuse license has not yet been selected. Retain all inherited notices and consult [source and dependency notices](advanced/companion-apps/guides/LICENSES.md) before redistribution. Bundled dependency license texts accompany the companion pilot.
