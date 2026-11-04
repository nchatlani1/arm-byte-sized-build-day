# Advanced projects

Finish Morning Briefing in `../starter/` first. Then open **[display/](display/)**
as its own PlatformIO project for calendar and Spotify. **[companion-apps/](companion-apps/)**
holds the computer apps and connection/account setup.

| Folder | Purpose |
| --- | --- |
| [display/](display/) | Morning Briefing plus calendar/meeting footer and Spotify Now Playing firmware |
| [companion-apps/](companion-apps/) | Mac menu-bar / Windows tray source, downloads, setup and app build tools |

The display and computer app are separate programs. Upload the advanced firmware
to the board, then run the companion on the laptop. An awake nearby laptop supplies
calendar/Spotify metadata over USB or Bluetooth. Stock/weather still uses the
board’s own Wi-Fi. Credentials/tokens never belong in shared source or prompts.
