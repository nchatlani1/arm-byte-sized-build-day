# Source and dependency notice obligations

Preserve all inherited file headers and the Elecrow provenance notice. The
source baseline has no top-level project license grant. Ask the project owner
to confirm redistribution rights and the appropriate notice/license before
hosting downloads; this task does not invent permission or remove provenance.
The optional preview uses a mirrored vendor font with the same notice.

Binary distribution must retain licenses shipped in the Python runtime,
PyInstaller (including its bootloader exception), pyserial, bleak, keyring,
PyObjC, and all transitive installed distributions. Windows adds pywin32,
pywebview and WebView2 runtime terms; the optional legacy kit adds Pillow,
MSAL and tzdata. Generate notices from the actual build environment, not only
this list. Include Apple/SDK redistribution terms where applicable. The local
Mac artifact includes a third-party distribution inventory and copied license
files; it is a pilot build, not approval to publish.

The core's PlatformIO-downloaded ArduinoJson/JPEGDEC/framework dependencies stay
under their original licenses. Their pins are unchanged and their installed
notices remain in the PlatformIO toolchain/library packages; this source-only
archive does not bundle those packages. The CA bundle is generated from certifi
(MPL-2.0) in the build environment and is not shipped as a source asset.
