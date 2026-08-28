# CloakBrowser availability check (read-only)

Checked 2026-08-28 on Windows x86_64. The repository and current environment
contain no `cloakbrowser`, `playwright`, or `puppeteer` executable, and no matching
package under `frontend/node_modules`; see
`baseline-browser-availability.log` lines 4–8. No package installation or binary
download was attempted.

The official CloakHQ README documents Python installation with `pip install
cloakbrowser`, JavaScript installation with `npm install cloakbrowser` plus
`playwright-core` (or `puppeteer-core`), and an automatic first-run Chromium
download of approximately 200 MB. It lists Windows x86_64 as supported. It also
documents `CLOAKBROWSER_BINARY_PATH` for an already available local binary and
`CLOAKBROWSER_CACHE_DIR` for the cache location.

Sources consulted:

- https://github.com/CloakHQ/CloakBrowser/blob/main/README.md (install, first-run
  download, supported platforms, and local binary options)

QA implication: CloakBrowser cannot be used in this environment until an
explicitly authorized external QA environment provides the dependency and its
binary. If enabled later, use one isolated profile for the local CUTI app only;
do not add it to the application runtime manifest and do not use it to bypass
the Catawiki access block.

