# Feature: one-command daily crawl and image recovery

Status: implemented and verified, 2026-08-27. Tier 1: 361 tests; isolated T2: 4 tests.
Evidence and live-verification limits are recorded in `notion.md`.

## Outcome

Run `python scripts/run_daily.py` from the repository root using the local venv.
Keep the existing configured database. One command owns crawling, missing-cover
reconciliation, one concurrent image worker, final reporting, and clean shutdown.
No database reset, date argument, second terminal, or manual upload pass is required.

## Contract

1. Use the existing scheduled watch-live/settlement flow and freshness guard.
   A skipped fresh crawl must not skip image reconciliation or queue recovery.
2. Keep crawling and Telegram uploads independent and concurrent. At most one
   uploader may run against the same DB, including the standalone worker. Reject
   a competing run explicitly; never silently start an additional uploader.
3. Reconcile unique lot IDs from both `live_watch` and `lots` without a cover row
   at `idx=0`, including older lots no longer present in search results.
4. Read a real cover URL from the configured source for that exact lot. Never
   construct/guess an image URL, substitute another lot/model, or create fake data.
   Missing image, unavailable source, malformed payload, and unsupported source
   remain explicit unresolved outcomes. Retry source requests only within existing
   configured request/retry limits; no busy-loop reconciliation in one run.
5. Use the existing durable `lot_images` queue, one immutable cover per lot.
   Preserve ready rows and Telegram metadata; do not re-upload them. Conflicting
   cover URLs must remain typed errors, not an overwrite or silent fallback.
6. Commit newly tracked/refreshed lots and their discovered image queue entries
   atomically so interruption cannot create the known split-commit gap.
7. Resume queued jobs, due retryable jobs and expired uploading leases. Never
   reclaim a live lease or reset a permanent failure automatically. Preserve
   retry limits, delays, ownership checks and per-image success commits.
8. Idle is not terminal. Do not finish while the producer can enqueue more work
   or while queued/uploading/retryable jobs remain (including future retry/lease
   times). Use bounded polling, not increased concurrency or faster rate limits.
9. Report crawl outcome, reconciliation counts, image state counts and unresolved
   failures. Exit 0 only when the producer succeeded or legitimately skipped and
   all required images are ready. Missing/permanent failures or child crashes
   produce a nonzero exit, with DB state retained for diagnosis/recovery.
10. Ctrl+C and producer/worker failure must clean up owned work without leaving an
    unmanaged worker. Locks release on exit/crash. An interrupted run is not success.
11. Telegram downloads the source URL through sendPhoto; local code does not
    download original image files for upload. Never expose credentials in commands,
    logs, exceptions or public URLs.
12. Delivery remains at-least-once: Telegram accepting a photo before the DB commit
    can lead to a duplicate Telegram message after recovery. Do not claim exactly-once.

## Minimal implementation plan

- Reuse scheduled crawler, queue functions, source parsers and stdlib process/lock
  facilities. Introduce one small daily entrypoint and only directly needed helpers.
- Share the existing OS-lock pattern for crawler and uploader exclusivity.
- Add targeted missing-cover querying/reconciliation; do not add schema, dependency,
  service, scheduler, gallery, generic job framework or cleanup API.
- Add crash/recovery regression coverage before changing the transaction/lifecycle
  paths; preserve existing contract tests and unrelated worktree changes.
- Keep legacy crawler and worker commands usable. Document the new daily command
  as the normal user entrypoint once verification passes.

## Verification and safety

- Offline tests use temporary databases, fake source/Telegram transports, fixed
  clocks and no real secrets; never send synthetic fixtures to the real channel.
- Cover restart at each persistence boundary, live/expired leases, retry due times
  and exhaustion, ready idempotency, immutable conflicts, DB-only missing lots,
  malformed/empty/404/timeout/429/5xx responses, competing runs, Ctrl+C and child death.
- Run full `scripts/verify.py` and frontend typecheck/lint/build, plus a bounded
  isolated launcher integration test. Keep original raw output and exit codes.
- If any true live smoke is performed, isolate its DB and record the exact created
  Telegram message IDs; remove only those test messages when API permissions/time
  limits allow. Never guess IDs or delete actual auction images. A bulk channel
  cleanup feature is out of scope.
- Do not alter the production DB, existing channel messages, `.env`, GitHub workflow
  state or rate-limit settings during implementation/verification.

## Tasks

- [x] Runtime implementation and source-resolution contract.
- [x] Deterministic failure/recovery tests and isolated integration.
- [x] Full verification, lean-result review and evidence in notion.md.
- [x] README daily-use instructions and final handoff.
