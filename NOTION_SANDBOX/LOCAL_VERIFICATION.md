# Local verification

- Repository: `cuti-tools`
- Source baseline: `8bd58dcb45f0ba546d81573f7127299ae1ca857a`.
- Required acceptance command: `make verify`
- Focused unit suite: **316 passed, 0 failed, 0 skipped, exit code 0**.
- Unit-suite raw log: `NOTION_SANDBOX/evidence/unit-2026-08-24.txt`.
- Latest recorded result: **316 passed, 0 failed, 0 skipped, exit code 1**.
- Failure: `LIQ_SERIES_SAMPLE` is empty because the real sample's quarterly
  groups are below `CUTI_LIQUIDITY_MIN_LOTS=5`.
- Live verification: blocked by Catawiki HTTP 403; no source fixture was
  fabricated.
- Focused supplemental fixture result: **exit code 0**. It validates the
  normalized `synthetic_test_only` fixture across pricing, liquidity, deal
  parsing and verdict paths. Raw log:
  `NOTION_SANDBOX/evidence/logic_coverage_validation.txt`.
- Network: not required for the focused fixture validation.
- Dependencies: Python 3.11+ standard library for the core path.

The supplemental fixture is not market data and must not be mixed into source
truth metrics. The real Catawiki snapshot remains separate and is still not a
drop-in input for `parse_listing` because it is CSV rather than `lot-card` HTML.
