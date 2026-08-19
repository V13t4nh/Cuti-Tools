# Local verification

- Repository: `cuti-tools`
- Source baseline: `9e50e90`; use the exported provenance and `handoff/*` tag
  for the final handoff commit.
- Result: **227 passed, 0 failed, exit code 0**
- Required acceptance command: `make verify`
- Network: not required; verification is intended to run offline
- Dependencies: Python 3.11+ standard library for the core path; no package
  installation is part of acceptance

The Windows host used for this handoff did not provide GNU Make. The exact
verification body used by the Make target passed locally with:

```text
PYTHONPATH=src;tests python scripts/verify.py
```

Run the literal `make verify` command in a clean environment that provides
GNU Make. If sample data is absent, the target generates it deterministically
from the fixed seed before verification.
