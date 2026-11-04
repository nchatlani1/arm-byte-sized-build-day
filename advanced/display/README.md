# Advanced display: calendar and Spotify

This is a separate PlatformIO project from `../../starter/`. It adds the account
receiver, Bluetooth pairing, calendar screen/meeting footer and Spotify Now Playing.
Both extensions are enabled in this folder’s device.json. Set a flag false to omit
that integration and its screen. With both false, Bluetooth is excluded entirely.

1. Open this folder or `CrowPanel-Advanced.code-workspace` in VS Code.
2. Copy your chosen ticker/ZIP/title/footer values into this `device.json`, keeping
   its `extensions` settings. The supplied `.env` already uses `Guest-AccessNG`
   with a blank password for live stock/weather. Edit it directly for another
   approved 2.4 GHz network. Settings in starter do not affect this build.
   Personal `.env` edits appear in Git; keep them out of commits and shared ZIPs.
3. Pause any companion connection and close serial monitors. Use the same Build /
   Upload offline starter or live stock/weather tasks. These are alternate builds
   of this advanced project. Offline disables Wi-Fi; account USB/Bluetooth remains.
4. Follow [companion setup](../companion-apps/guides/COMPANION-SETUP.md) to install,
   connect and authorize accounts. Use the wheel to select enabled screens.

`firmware/src/main.cpp` coordinates drawing, controls, polling and account overlays.
`firmware/include/companion_link.h` owns protocol-2 receiver/pairing/live drawing;
`integration_data.h` validates bounded account metadata and expires stale data.
Named screen IDs bind data to the right screen. `tools/render.py` previews samples;
live account layout is C++ and must be changed too for matching visual changes.
Preserve the vendor panel settings and automatic/manual refresh limits.

[Code and extension guide](docs/WORKSHOP.md) · [Companion apps](../companion-apps/)
