# Build companion apps

Run app commands from `advanced/companion-apps`. Participants use packaged apps;
only maintainers need Python and development tools. Existing requirements are pinned.

## Mac Apple Silicon pilot

Use a framework-enabled Python 3.12 and installed Xcode Command Line Tools:

```sh
python3.12 -m venv .venv-companion
.venv-companion/bin/python -m pip install -r companion/desktop_requirements.txt
.venv-companion/bin/python -B -m unittest discover -s tests -v
.venv-companion/bin/python tools/build_companion.py
```

Outputs go to `dist/companion/`. The app targets macOS 14+ and the build host's
architecture. Build/test Intel separately on a compatible target. The local Mac
0.3.2 pilot is ad-hoc signed, not notarized; a rebuild can reset OS consent.
Developer ID signing/notarization and real account/Bluetooth/startup/energy checks
remain separate acceptance. Do not enable startup merely to test a build.

## Windows

Use `Build Companion Windows.cmd` on a Windows x64 target. The root repository's
manual **Windows companion pilot** GitHub Actions workflow also builds from this
folder. It uploads an Actions pilot artifact without publishing a Release.
The [0.3.2 Windows x64 CI build and packaged smoke checks passed](https://github.com/nchatlani1/arm-byte-sized-build-day/actions/runs/41778484952).
The downloadable pilot is unsigned. A physical pilot must
check WebView2, tray/clean Quit, USB/Bluetooth, classic Outlook, Spotify, sign-in
startup, sleep/wake and disconnected energy. No substitute Windows ZIP is offered.

## Firmware and source release

Upload `advanced/display` firmware for account data; starter has no receiver.
The app supplies metadata over protocol 2 and does not edit layouts or firmware.
A nearby awake laptop remains necessary for account updates.

From this folder, package the entire unified repository using:

```sh
python3 release/package_workshop.py --source ../.. --output /external/artifacts --release workshop-v0.1.0
```

`release/repository-files.txt` explicitly lists source from the unified root.
The packager rejects unknown files, credentials and symlinks; generated build
folders are excluded. [Release process](RELEASING.md).
