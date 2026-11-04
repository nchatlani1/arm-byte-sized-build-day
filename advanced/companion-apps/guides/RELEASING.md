# One repository and versioned release assets

Repository: [https://github.com/nchatlani1/arm-byte-sized-build-day](https://github.com/nchatlani1/arm-byte-sized-build-day).
Publish this unified root with starter/ and advanced/, including companion-apps.
No second support repository is required. The HTML slides and reference guide live under docs/ at the repository root.

The explicit repository source manifest is release/repository-files.txt relative to
this companion-apps folder. From the repository root, package with:

```sh
python3 advanced/companion-apps/release/package_workshop.py --source . --output /external/release --release workshop-v0.1.0
```

Build apps from advanced/companion-apps with tools/build_companion.py. Mac Apple
Silicon is a local ad-hoc 0.3.2 pilot, not notarized. Use the root GitHub Actions
Windows companion pilot workflow to build on Windows. It uses this
nested source folder and uploads an Actions pilot artifact, without publishing a
Release. The 0.3.2 Windows x64 CI build and packaged smoke checks passed; its
unsigned pilot is available, with physical platform acceptance still pending.
Publish only actual target builds and label their acceptance limits.

Attach the unified source ZIP and actual versioned Mac/Windows packages to one
GitHub Release. Link the app assets from this folder's README, root README and
presentation guide. Never invent URLs or relabel a Mac/source ZIP as Windows.
Keep generated builds, credentials and account state out of source archives.

## Slides

Publish `main` → `/docs` in GitHub Pages. The deck is `docs/slides/CROWPANEL-INTRO.html`, with the setup guide beside it. Keep app/source downloads linked to the actual tagged Release assets. Update the explicit source manifest whenever adding documentation files.
