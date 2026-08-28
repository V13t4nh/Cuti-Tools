# Lean result review — formula configuration

## Outcome

**No material simplification proposed.** The two source follow-ups from the
initial review are now implemented. Independent core/HTTP QA passes; browser
acceptance and permanent regression tests remain open, so this review does not
mark the feature unconditional ship.

The formula evaluator, unit checker, bounded affine analysis, profile store, and
API layer are each consumed by the current pricing path. The split into
`config_pricing.py`, `config_pricing_math.py`, `config_pricing_units.py`, and
`config_pricing_store.py` is justified by separate validation, inverse, unit,
and persistence responsibilities. No new dependency, database table, generic
solver, or unused compatibility layer is justified by this feature.

## Source follow-ups resolved

1. **Snapshot provenance is now checked.** `src/cuti/api.py:204-212` requires a
   complete `pricing_profile`, reconstructs it, and verifies its revision is the
   canonical hash of that snapshot's content. It deliberately does not compare
   against the active revision, so a result evaluated before a config change
   remains saveable; existing rows are untouched. This is provenance validation,
   not cryptographic signing.

2. **Inverse domain guard is now present.** `src/cuti/config_pricing.py:147-158`
   rejects non-finite or negative results with a typed `invalid_result` error,
   while allowing zero. The strict `a > 0, b < 0` affine requirements remain.

Focused read-only probes:

```text
$env:PYTHONPATH='src'; python -c "from cuti.config_pricing import PricingProfile, profile_from_values, PricingParameter; p=profile_from_values({}); params=p.parameters+(PricingParameter('bonus_eur',10,'eur',True,True),); q=PricingProfile(params,p.helpers,(('net_proceeds','hammer_eur - cost_eur + bonus_eur'),('profit_threshold','min_profit_eur')),source='file'); q.validate(); print('zero',q.inverse_break_even(0,10))"
zero 0.0
$env:PYTHONPATH='src'; python -c "from cuti.config_pricing import PricingProfile, profile_from_values, PricingParameter; p=profile_from_values({}); params=p.parameters+(PricingParameter('bonus_eur',10,'eur',True,True),); q=PricingProfile(params,p.helpers,(('net_proceeds','hammer_eur - cost_eur + bonus_eur'),('profit_threshold','min_profit_eur')),source='file'); q.validate(); q.inverse_break_even(0,0)"
FormulaError: break-even result must be finite and nonnegative
$env:PYTHONPATH='src'; python -c "from cuti.config_pricing import profile_from_values; from cuti.config_pricing_store import profile_from_payload; p=profile_from_values({}); body=p.public(); imported=profile_from_payload(body); print('self_revision',body['revision']==imported.revision)"
self_revision True
```

## Protected behavior

- AST whitelist and depth/node/branch caps remain necessary for no-code
  execution and bounded resource use (`config_pricing_math.py:26-52`).
- Unit compatibility and the strict affine/monotone restrictions are required
  for a sound break-even and max-buy inverse; do not replace them with a
  generic numeric solver (`config_pricing.py:159-172`).
- Threshold validation must cover the full nonnegative cost domain, including
  `profit_threshold(0) >= net_proceeds` constant and nonnegative output; do not
  weaken this to a one-sample check.
- Canonical revision, expected-revision conflict, process-local locking, and
  atomic replacement remain required store safeguards (`config_pricing_store.py:89-109`).
- Per-run pricing snapshots are already included in quote assumptions; new deal
  input now enforces the same completeness rule for the future replay promise.

## Verification follow-up

No new tests were written. Independent `final-full-verify-02.log` passes 361
tests; `final-http-pricing-03.log` passes strict JSON NaN rejection, preview/apply,
revision conflict, Origin and PUT preflight checks. The negative-result and zero
cases pass in `final-direct-negative-result-01.log`. Backend historical snapshot
smoke passes in `backend-final-contracts-02.log`; retain its direct-save cases in
the eventual permanent regression suite, along with Infinity/overflow and DAG
resource bounds. Browser `/settings` smoke/fixture acceptance remains open;
existing unit/build green logs do not replace those browser checks.
