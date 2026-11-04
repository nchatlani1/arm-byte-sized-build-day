# Companion: calendar and Spotify projects

## Downloads

Mac and Windows applications belong in the **CrowPanel-Workshop GitHub Releases**
assets. The repository README and the presentation link to these versioned
assets in this repository. [Source ZIP](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/download/workshop-v0.1.1/CrowPanel-Workshop-Source.zip) · [Mac Apple Silicon 0.3.2 pilot](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/download/workshop-v0.1.0/CrowPanel-Companion-macOS-arm64-0.3.2.zip) · [Windows x64 0.3.2 pilot](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/download/workshop-v0.1.0/CrowPanel-Companion-Windows-x64-0.3.2.zip) · [Source release notes and checksums](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/tag/workshop-v0.1.1) · [Companion release notes and checksums](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/tag/workshop-v0.1.0).

| Platform | Current status |
| --- | --- |
| Mac Apple Silicon, macOS 14+ | 0.3.2 pilot; ad-hoc signed, not notarized; physical pairing/account/startup/energy pilot pending |
| Windows x64 | [0.3.2 pilot](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/download/workshop-v0.1.0/CrowPanel-Companion-Windows-x64-0.3.2.zip); unsigned; [Windows CI build and smoke passed](https://github.com/nchatlani1/arm-byte-sized-build-day/actions/runs/41778484952); physical acceptance pending |
| Intel Mac | Download pending: compatible target build required |

Participants use a packaged app; no participant Python installation is needed.
Do not rename a source ZIP or a Mac package to offer a Windows download.

## 1. Enable a project and upload to the display

Open **advanced/display** as your PlatformIO project. Both account extensions are
already enabled in its `device.json`. Keep your ticker/ZIP settings there, or edit
the flags to enable only one source:

```json
"extensions": {
  "calendar": true,
  "spotify": true
}
```

The supplied `.env` in this project already uses `Guest-AccessNG` with a blank
password. No copy step is needed for that guest network. Edit `.env` directly for
another network; personal edits appear in Git and must stay out of commits and
shared ZIPs.

The starter folder has no receiver; upload advanced/display firmware first. Enable
just one flag if preferred. Calendar adds a meeting screen and Morning Briefing
footer; Spotify adds Now Playing. Build/upload with the existing offline or live
tasks. Offline forces Wi-Fi off, while enabled account extensions still work.
The wheel selects enabled screens. Changing configuration requires another upload.

## 2. Open the app and connect

Mac: move CrowPanel Companion.app to Applications before enabling startup.
Windows: extract the whole portable folder to
`%LOCALAPPDATA%\Programs\CrowPanel Companion` and keep its resources together.
Windows requires WebView2; local calendar access requires classic Outlook.

Use **USB → Find USB devices → select your board → Connect** during development.
Close PlatformIO’s serial monitor first. Before uploading again, use **Pause for
PlatformIO**; after uploading, close the monitor and resume the connection.

For Bluetooth, hold **MENU for two seconds** on the display. Scan in the app,
select the CrowPanel name shown on your screen and enter its code in the OS
pairing prompt. Windows may require initial pairing in Bluetooth Settings.
After pairing you can power the display from a wall USB adapter. The nearby
laptop must stay awake for calendar/Spotify updates. Hold EXIT for eight seconds
to forget bonds. Bluetooth/USB connection does not configure the board’s Wi-Fi.

## 3. Connect your calendar

Mac: first confirm permitted work meetings appear in **Apple Calendar**. Enable
Work calendar in the companion, save, approve Calendar access and select your
work calendar. Outlook alone on Mac is not the calendar store this reader uses.
Windows: use **classic Outlook** with your synced work calendar. New Outlook
alone does not provide the local interface used here.

The app reads your next future non-free appointment; Teams meetings are ordinary
calendar appointments in this flow. It never creates/edits events. Only bounded
title/time metadata goes to the board, without passwords or meeting join URLs.
No meetings shows “No upcoming meetings”; expired data shows “update needed”.
A fresh read of a calendar store cannot detect that Exchange sync itself is stale.

## 4. Connect Spotify

Create an eligible app at https://developer.spotify.com/dashboard and register
exactly `http://127.0.0.1:8766/callback`. Paste the public Client ID into the
companion, enable Spotify, save, then **Sign in to Spotify** in the official
browser flow. Never enter a client secret. Play music on that signed-in account;
playback can be on a phone, browser or desktop. No playback shows “Nothing playing”.

Spotify uses PKCE; tokens stay in the OS credential store and are never sent to
Codex or the board. Sign out removes the local token. Development apps currently
require a Premium owner and allow five authorized users, so one development app
cannot serve the whole workshop. Eligible personal setup is optional prework.
[Spotify quota rules](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)

## 5. Background use

Closing settings leaves the Mac menu-bar / Windows tray app running. Use its menu
for Open, Pause/Resume, Start at sign-in, or Quit. Enable startup once after moving
the app to its permanent location; startup occurs after user sign-in.
When disconnected there are no new account reads; short saved-device retries
back off to five minutes. Pause disables retries. Actual OS/radio overhead remains;
zero battery use is not promised. Real platform/energy acceptance is pending.

## Develop with Codex

Spotify prompt: “Read advanced/display in this repository. Use its Spotify
Now Playing screen and make the track and artist easy to read. Keep Morning
Briefing, the panel configuration, and refresh limits. Use the existing companion
protocol. Tell me how to build and check the result on my display.”

Calendar prompt: “Use advanced/display and its calendar extension to show my next meeting
on Morning Briefing and a calendar screen. Customize the layout for readability.
Keep hardware settings and refresh limits. Explain the account/connection setup
and how to verify it on the display. Keep credentials out of source.”

You can still use `tools/render.py` to preview saved sample/layout changes.
Runtime account drawing is in `firmware/include/companion_link.h`; the Python
preview and C++ live layout must both be updated for a matching visual change.
Build, upload and an observed physical display are separate checkpoints.

## Troubleshooting

No compatible firmware: open advanced/display, enable an extension in its device.json, build/upload, close
serial monitors and reconnect. A missing extension is reported by the companion.
No account data: check app source status, OS permission, calendar sync or Spotify
sign-in. “OLD” means the data lease expired; reconnect rather than treating it as
live. Keep stock/weather network checks separate from companion connection checks.
