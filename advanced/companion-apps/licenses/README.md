# Exact-version license fallbacks

Some installed wheels omit a standalone license file. The companion builder
uses these original upstream texts only for the matching package version.
It fails if a distribution has no collected notice. Preserve the texts unchanged.

- [pyserial-3.5-LICENSE.txt](pyserial-3.5-LICENSE.txt) — https://raw.githubusercontent.com/pyserial/pyserial/v3.5/LICENSE.txt (SHA-256 `f91cb9813de6a5b142b8f7f2dede630b5134160aedaeaf55f4d6a7e2593ca3f3`).
- [pyobjc-core-11.1-License.txt](pyobjc-core-11.1-License.txt) — https://raw.githubusercontent.com/ronaldoussoren/pyobjc/v11.1/pyobjc-core/License.txt (SHA-256 `0ca04b07928d4872b9d9bb22187ca0426dd8bfab08f26eada0999a71dc81aaff`).
- [pyobjc-libdispatch-11.1-License.txt](pyobjc-libdispatch-11.1-License.txt) — https://raw.githubusercontent.com/ronaldoussoren/pyobjc/v11.1/pyobjc-framework-libdispatch/License.txt (SHA-256 `0ca04b07928d4872b9d9bb22187ca0426dd8bfab08f26eada0999a71dc81aaff`).

- [proxy_tools-0.1.0-LICENSE.txt](proxy_tools-0.1.0-LICENSE.txt) — https://raw.githubusercontent.com/jtushman/proxy_tools/db43f1e35d4f90a65c5a4d56d9e9af88212ec6e6/LICENSE.txt (SHA-256 `a428fb8a2e762af3eb0a6edbbb88e9b42ccfee80fd9b423958bcacf9b9abbfe4`). The package metadata says MIT, but this upstream notice contains BSD terms; the original text is preserved.
