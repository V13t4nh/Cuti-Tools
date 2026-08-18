# Notion sandbox package

This directory describes the offline hand-off made by
`scripts/Export-NotionSandbox.ps1`.

The default package is source-only and deliberately reports `testReady: false`.
The intended verification command is:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

At the current `HEAD`, verification is blocked by pre-existing import errors:
`streamlit`, `rapidfuzz`, and `plotly` are unavailable, and
`test_storage` imports `cuti.storage.insert_deal_if_new`, which is absent. This
is recorded as a baseline issue, not a packaging failure. A dependency bundle
may be supplied later, but it must be prepared for Linux x64 and declare its
runtime plus AL2023-compatible glibc in `dependency-manifest.json`.

The sandbox is offline. Do not run package installation, network calls, Docker,
database migrations, or database-backed services. The package is intended for
business-logic edits and tests only.

## Export

Run from this repository with a clean worktree and write the archive to the
ignored local `.zip/` folder (direct `.zip` files only):

```powershell
pwsh -NoProfile -File .\scripts\Export-NotionSandbox.ps1 -OutputPath .\.zip\cuti-tools-notion-sandbox.zip
```

`.zip/` is intentionally ignored because generated hand-off archives are local
artifacts. The exporter still rejects `.zip/` in the source archive, even if a
tracked file bypasses this ignore rule.

The archive contains provenance with repository, branch, commit, source archive
SHA-256, exact verification command, and patch instructions. It includes tracked
`HEAD` files only; secrets, `.env` files, build/runtime/cache output, `.git`, and
`node_modules` are rejected. `.env.example` is the only environment-file
exception.

## Return changes

Inside the unpacked sandbox, create a local Git baseline before editing:

```powershell
git init
git add -A
git commit -m "Notion sandbox baseline"
# make the requested edits and run the documented offline checks
git diff --binary > changes.patch
```

Return `changes.patch` and the test output. Do not return secrets or a dependency
bundle unless explicitly requested.
