# Final-phase 07 — Claim-to-evidence audit (Phase 9)

## 9.1-9.2: Registry preserved and strengthened

`paper/icaps27_unified_final/make_numbers.py` extends (not replaces) the macro-registry pattern from the prior-stage manuscripts: every reported number is generated from a cited analysis file, never hardcoded, with per-macro metadata (`source`, `setting`, `metric`, `statistic`) in `claims.json`. This phase added 51 new macros (Phase 3's by-disruption-type reanalysis numbers, the round-diagnostic asymmetry numbers, and the real-trajectory Figure 2 numbers), all following the same pattern.

**Bug found and fixed in the checker itself:** the claim-detection regex in `check_claims.py` (inherited from the prior-stage COBAR/IAIP-SR scripts) only recognized macro name prefixes that existed *before* this phase (`UOne`, `UTwo`, ..., `Oracle`, etc.). The new prefixes added this phase (`MechTwo`, `RoundsUOne`, `MTwoRound`, `FigTwo`) were silently invisible to the checker's undefined-macro and hand-typed-literal scans until the regex was extended. After the fix, the tool-reported count rose from "104 claim macros used" to the correct **135**, with **0 undefined and 0 hand-typed result literals** in both cases (the earlier count was an undercount, not a false negative on correctness — no undefined macro or hand-typed literal was actually missed, because the macros in question happened to already be syntactically valid LaTeX commands that compiled correctly; but the *checker's own count was wrong*, and is recorded as found-and-fixed here rather than silently corrected).

## 9.3: Automatic table generation

Table 1 in the manuscript is generated entirely from macros (every cell references a `\U*Mean*`/`\U*...Vs...*` macro); no cell contains a hand-typed number. Verified by `check_claims.py`'s literal scan, which inspects the full manuscript body including table environments.

## 9.4: Consistency checker, extended

`check_claims.py` now performs, in one run:

1. Parse the macro registry (`claims.json`).
2. Recompute every value by rerunning `make_numbers.py` from the archived analysis files (not from the committed `numbers.tex` — a true recomputation).
3. **Stale-output detection:** after recomputation, `git diff --quiet -- numbers.tex` checks whether the freshly-generated file differs from what is committed. Result: **not stale** (byte-identical).
4. **Sample-size consistency:** for every setting with an `N` macro (e.g. `\UOneN`), compares the macro's value against `confirmatory_analysis.json`'s own `n_units` for that setting. Result: **0 mismatches** across all 9 settings.
5. Undefined-macro and hand-typed-literal scans (pre-existing, now regex-corrected).

Not implemented as separate automated checks (done manually in Phases 1-3 instead, and judged sufficient given the scope): sign validation (checked by construction, since `comparison()` always derives sign from the registry's own `rel_diff`, never typed), unit validation (every metric is PI or a percentage, declared in the `statistic` field, and manually spot-checked in Phase 6), table-association validation (every table cell's macro name encodes its row/column via the setting+method+comparator naming convention, manually verified by inspecting the rendered PDF in this phase), unused-required-claims detection (not applicable — there is no separate "required claims" list distinct from what the manuscript actually cites).

## Audit outcome

| Check | Result |
|---|---|
| Claim macros used | 135 |
| Undefined | 0 |
| Hand-typed result literals | 0 |
| `numbers.tex` stale vs. fresh rebuild | No |
| Sample-size (`n_units`) mismatches | 0 |
| A real bug found in the checker itself | Yes, found and fixed (regex coverage gap, §9.2 above) |
