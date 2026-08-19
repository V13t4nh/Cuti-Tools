# Notion handoff declaration

Handoff source baseline: `cuti-tools` through `9e50e90`; the annotated
`handoff/*` tag identifies the final documentation and exporter metadata commit.

Acceptance command: `make verify` on a clean machine, with no network and only
Python 3.11+ standard library available. The project core is stdlib-only;
Streamlit, Plotly, and RapidFuzz are optional UI dependencies and are not
required on the core import path.

Verification result: 227 tests passed, 0 failed, exit code 0. The exact target
body passed locally with `PYTHONPATH=src;tests python scripts/verify.py`.
Literal GNU Make was unavailable on the Windows host, so Notion should run the
acceptance command in an environment that provides `make`.

Completed commits:

- `b84644a` — P0 stdlib-only imports, API alignment, import guard, provenance
- `8b06ae5` — P1.5 pipeline split
- `e3f27d1` — P1.6 storage schema/migration split
- `0e36a6c` — P1.7 declarative config table
- `9e50e90` — P1.8 deterministic on-demand sample generation

Samples are generated on demand from a fixed seed; `make verify` generates them
when absent. The verification posture is offline: no network access or package
installation is part of acceptance.
