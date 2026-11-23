"""Post-hoc EXPLORATORY comparisons (not in the frozen plan; chosen after
seeing held-out results; uncorrected; reported only as exploratory).

Motivated by Figure S5: at paper scale, does any engine's full pipeline (S4)
match CP-SAT's S4? Same statistic as analyze_results.compare.

    .venv_ms/bin/python scripts/multisolver/posthoc_comparisons.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_results import ROOT, compare, load, summarize  # noqa: E402

# 15x15 is covered by the frozen family C_M15 (same pairs); 20x20 had no frozen Experiment C family
PAIRS = [(("AB", "M20", s, "S4", 8, 1), ("AB", "M20", "cpsat", "S4", 8, 1))
         for s in ("gecode", "chuffed", "scip", "highs", "cbc", "glpk")]


def main():
    streams = {p.stem for p in (ROOT / "results/multisolver/instances/heldout").rglob("*.json")}
    rows, _ = summarize(load(ROOT / "results/multisolver/runs", streams))
    out = {"post_hoc_exploratory": True, "correction": "none",
           "comparisons": [c for c in (compare(rows, a, b) for a, b in PAIRS) if c is not None]}
    p = ROOT / "results/multisolver/analysis/posthoc.json"
    p.write_text(json.dumps(out, indent=1))
    for c in out["comparisons"]:
        print(f"{c['a']:28s} vs {c['b']:24s} {c['rel_diff_pct']:+7.1f}%  {c['wins_a']}/{c['losses_a']}  "
              f"p={c['sign_p']:.3g}  CI={[round(x, 1) for x in c['ci95_rel_pct']]}")
    print("->", p)


if __name__ == "__main__":
    main()
