# Formula configuration acceptance matrix (planning only)

This file records the read-only QA coverage to apply after implementation. It does
not add or alter tests and is not an implementation approval.

| Area | Focused acceptance cases | Evidence expected |
|---|---|---|
| Default parity | No `config/pricing.json` (env-derived profile); default `net_proceeds` and `profit_threshold` match the current pricing functions for representative, zero-profit, and thin-comparable inputs. | Exact backend/CLI values and unchanged verdict/break-even/max-buy behavior. |
| Parser whitelist | Accept finite decimals, snake_case names, `+ - * /`, unary signs, parentheses, and `min`/`max` with at least two arguments. Reject Python/import/attribute/index/string/comparison/conditional/exponent/modulo and unknown calls. | Preview returns `valid: false` with typed field/code/message; apply maps the same validation to HTTP 422; no active profile mutation. |
| Symbols and graph | Reject unknown variables, duplicate names, duplicate helper/output names, missing units, and helper cycles. Forward references to another declared helper are valid; verify output names are exactly `net_proceeds` and `profit_threshold`. | Error points to the offending field; candidate is not written. |
| Finite arithmetic | Reject non-finite parameter values, division by zero, and non-finite results. Check negative/zero constraints required by each input contract. | Typed errors; no `NaN`, infinity, or guessed zero in API/UI. |
| Units | Require `eur`, `rate`, or `vnd_per_eur` units; allow only valid add/subtract and multiply/divide combinations. Add a EUR extra cost and confirm it is used only when explicitly referenced by `net_proceeds`; reject deleting a referenced parameter. | Normalized candidate and unit-specific validation errors. |
| Inverse capability | Accept affine `net_proceeds = a*hammer_eur + b*cost_eur + c` only when `a > 0` and `b < 0`; permit helper paths only when the checker proves the same. Reject non-affine/min-max wrapping that prevents proof. Accept monotone non-decreasing `profit_threshold` without `hammer_eur`; reject non-monotone forms. | `unsupported_inverse` on preview/apply; valid candidate returns correct break-even and binary-search max-buy values. |
| Preview/apply state | GET reports state/source/revision/parameters/helpers/formulas/input variables/capabilities. Preview does not write or increment revision. Apply requires `expected_revision`, atomically replaces only a fully valid candidate, rejects stale revision with 409, and preserves active file on replace failure. | Before/after file bytes, revisions, and HTTP status/body logs. |
| Request consistency | One immutable profile is loaded at request start and reused through preview/evaluation/response; concurrent apply cannot produce mixed revision results. | Response revision/hash and calculation values agree. |
| History | When quote/deal persistence is exercised, snapshots include revision, canonical hash, parameters, helpers, and expressions; later profile changes do not recalculate old results. | Read-back JSON assertions from an isolated temporary DB. |
| UI contract | `/settings` exposes a draft separate from active profile, shows units/revision/source, sends Preview and Apply to backend, renders backend values/errors verbatim, and does not expose `min_comparables` as an editable UI field per Lead decision. Existing `/assessment`, `/tracking`, and `/market` remain usable. | Frontend typecheck/build plus browser render text fixture and backend/UI value parity. |
| Regression | Existing pricing/config/evaluation suites, full `make verify`, and frontend typecheck/build remain green with no network and no source DB writes. | Raw logs with command, environment/dependency names, and exit codes. |

## Exact command set

These commands are intended for the post-implementation QA run. They use the
project's existing dependency state and must not install packages or touch the
default DB/config. Replace `<isolated-home>` with a fresh temporary directory
that contains only the sample fixtures and a copied rules/catalog profile.

```powershell
$env:PYTHONPATH = 'src;tests'
.venv\Scripts\python.exe -m unittest discover -s tests -v
make verify
npm --prefix frontend run typecheck
npm --prefix frontend run build
.venv\Scripts\python.exe -m unittest tests.daily_process_integration_t2 -v
```

`daily_process_integration_t2` is an existing isolated Windows-spawn check. It
uses a temporary DB/home, a loopback-only Telegram server, a fake Catawiki API,
and `loopback_network_guard`; it must be run separately because `make verify`
does not discover this file. It is a regression check for Settings/profile
serialization and must not be reported as a real-source/live test.

For HTTP cases, start the API against an isolated home and DB, then capture
the exact request/response bytes and status in a raw log. The route sequence is:

```text
GET  /api/pricing-config
POST /api/pricing-config/preview
PUT  /api/pricing-config
GET  /api/pricing-config
```

The following payload fragments are the adversarial expressions/values to put
inside the final candidate envelope. The contract uses the parameter array and
helper array shapes returned by `GET /api/pricing-config`.

| Case | Candidate fragment | Expected result |
|---|---|---|
| Default valid | `net_proceeds = hammer_eur - hammer_eur * commission_rate * (1 + vat_on_commission_rate) - shipping_eur - cost_eur`; `profit_threshold = max(cost_eur * min_margin_rate, min_profit_eur)` | Preview valid; values equal current pricing output. |
| Valid helper chain | `fee_rate = commission_rate * (1 + vat_on_commission_rate)`; net uses `hammer_eur * fee_rate` | Preview/apply valid if unit checker and affine proof pass. |
| Unknown symbol | `net_proceeds = hammer_eur - unknown_fee - cost_eur` | 422 typed missing/unknown variable; active file unchanged. |
| Python execution | `net_proceeds = __import__("os").system("echo bad")` | 422 syntax/unsupported token; no process execution. |
| Attribute/index/string | `net_proceeds = hammer_eur.__class__`; `net_proceeds = values[0]`; `net_proceeds = "bad"` | 422; no fallback. |
| Disallowed operators | `hammer_eur ** 2`; `hammer_eur % 2`; `hammer_eur > cost_eur`; `1 if cost_eur else 0` | 422 unsupported syntax. |
| Built-in arity/call | `max(cost_eur)`; `min(cost_eur, 1, 2)` is valid only if units are valid; `round(cost_eur, 2)` | One-argument/unknown function rejected; only `min/max` with at least two args. |
| Non-finite value | Parameter value `NaN`, `Infinity`, `-Infinity`, or JSON `1e309` | Malformed/non-standard JSON is HTTP 400; a parsed but non-finite profile is a typed validation error (HTTP 422 on apply); no file write. |
| Divide by zero | `net_proceeds = hammer_eur / (cost_eur - cost_eur)` | 422 division-by-zero. |
| Unit mismatch | `net_proceeds = hammer_eur + commission_rate`; `net_proceeds = shipping_eur * shipping_eur` | 422 unit error. |
| Missing/duplicate graph node | Duplicate helper name; helper references a missing name; helper cycle `a=b+1`, `b=a+1` | 422 graph error. A forward reference to a declared helper is valid. |
| Repeated dependency DAG | Helpers `h1=shipping_eur+shipping_eur`, then `hN=hN-1+hN-1` through a bounded depth, with `net_proceeds` referencing `hN` | Typed rejection or bounded completion; no exponential CPU/memory traversal. |
| Strict inverse coefficient | `net_proceeds = hammer_eur - shipping_eur` (cost coefficient 0); `net_proceeds = hammer_eur + cost_eur` (positive cost coefficient) | 422 `unsupported_inverse` because cost coefficient must be strictly negative. |
| Non-affine inverse | `net_proceeds = hammer_eur * (1 + cost_eur / (shipping_eur + cost_eur))` (dimensionally valid but non-affine) | 422 `unsupported_inverse`. |
| Min/max around input | `net_proceeds = max(hammer_eur, cost_eur) - shipping_eur` | 422 `unsupported_inverse` unless checker can prove required affine form. |
| Threshold monotonicity | `profit_threshold = -cost_eur`; `profit_threshold = min_profit_eur - cost_eur` | 422 `unsupported_inverse` because threshold is not monotone non-decreasing. |
| Missing required output | Candidate omits `net_proceeds` or `profit_threshold`, or renames either | 422 required-output error. |
| Preview immutability | Valid candidate with changed shipping; hash/revision/file bytes read before and after | 200 preview; revision and file bytes unchanged. |
| Apply conflict | Valid candidate with stale `expected_revision` | 409 `stale_revision`; current profile remains byte-identical. |
| Atomic failure | Inject `os.replace`/write fault after candidate validation | 5xx/typed storage error; previous valid profile remains loadable. |
| Malformed active profile | Corrupt `config/pricing.json` while env values are present | Startup/API fails typed; must not derive fallback from env. |
| Browser preflight | `OPTIONS /api/pricing-config` before the JSON `PUT` apply request | 204 and `Access-Control-Allow-Methods` includes `PUT`; otherwise the `/settings` apply flow cannot run in a browser. |

## Required isolation checks

For every API case, assert the default `config/pricing.json` and `var/auctions.db`
timestamps/hashes are unchanged. For apply success, use only the isolated profile
copy. For history, use a fresh temporary DB and assert the saved snapshot contains
revision, canonical hash, parameters, helpers, and expressions after a later
profile change.
