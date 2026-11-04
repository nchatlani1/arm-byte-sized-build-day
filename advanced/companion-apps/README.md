# Companion apps

Mac menu-bar and Windows tray apps for **[../display/](../display/)**. App code
lives in `companion/`, native Mac shell in `companion/native/Companion.swift` and
build commands in `tools/`. The wide dot-matrix smiley icon is drawn in native code.

[Downloads and setup](guides/COMPANION-SETUP.md#downloads) ·
[Maintainer build instructions](guides/BUILD.md) · [Release process](guides/RELEASING.md)

| Platform | Download status |
| --- | --- |
| Apple Silicon Mac, macOS 14+ | [Download 0.3.2 pilot](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/download/workshop-v0.1.0/CrowPanel-Companion-macOS-arm64-0.3.2.zip); ad-hoc signed, not notarized |
| Windows x64 | Pending a real Windows build and target validation |
| Intel Mac | Pending a compatible target build |

Versioned binaries belong in this same repository’s GitHub Releases, linked here
after publication. Source and build files live in this folder; avoid committing
.app folders, executable packages or private account state to Git. [Release assets](https://github.com/nchatlani1/arm-byte-sized-build-day/releases/tag/workshop-v0.1.0) are versioned independently of the source.

The account app requires advanced display firmware; starter firmware intentionally
has no receiver. Pause before PlatformIO uploads; the app supplies data, while
C++ owns the display layout. [Project overview](../../README.md).
