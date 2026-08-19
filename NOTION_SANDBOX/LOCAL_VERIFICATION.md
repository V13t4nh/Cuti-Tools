# Local verification

- Repository: `cuti-tools`
- Source baseline: `6318564f27ae89e4d3bc5aa35a338c4c9a1bc781`.
- Result: **250 passed, 0 failed, 0 skipped, exit code 0**.
- Required acceptance command: `make verify`
- Network: not required; verification is intended to run offline
- Dependencies: Python 3.11+ standard library for the core path; no package
  installation is part of acceptance

The Windows host used for this handoff did not provide GNU Make. The exact
verification body used by the Make target passed locally with:

```text
PYTHONPATH=src;tests .\.venv\Scripts\python.exe scripts/verify.py
```

Run the literal `make verify` command in a clean environment that provides
GNU Make. If sample data is absent, the target generates it deterministically
from the fixed seed before verification.
