"""Figure 2: median gap to z* vs wall-clock time, from the ACTUAL archived
U1 confirmatory trajectories (held-out streams, seeds 1101-1120, solver
seeds 0-4, results/unified_icaps/confirmatory/U1_primary/runs). Every
curve is a real measurement, never illustrative. z* is shared per physical
instance across all seven U1 methods and five solver seeds, matching
phase0/analyze_unified_confirmatory.py's own reference convention.

Text is typeset through LaTeX so the PDF embeds Type 1 fonts only (AAAI kit
rule); line styles differ (not just colour) for grayscale legibility.

    .venv/bin/python paper/icaps27_unified_final/figures/make_figure2_trajectories.py
"""
import glob
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{helvet}\usepackage{sansmath}\sansmath\renewcommand{\familydefault}{\sfdefault}",
    "font.family": "sans-serif",
    "font.size": 9, "axes.labelsize": 9, "legend.fontsize": 6.3,
    "xtick.labelsize": 8, "ytick.labelsize": 8,
})
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "results/unified_icaps/confirmatory/U1_primary/runs"
STYLE = {  # method config string: (label, colour, linestyle, width)
    "cobar|neighbourhood=none|use_certificate=0|global_certificate=0|policy=fixed|global_params=interleave":
        ("Port+Hint-ILS (native 1w)", "#999999", ":", 1.1),
    "iaip|portfolio=full|global_mode=hinted": ("Port+Hint", "#d95f02", "--", 1.1),
    "iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted": ("SR (IAIP-SR)", "#7570b3", "-.", 1.3),
    "crgar|strategy=random_matched": ("SR+Rand", "#e7298a", (0, (3, 1, 1, 1)), 1.1),
    "crgar|strategy=precedence": ("SR+Prec", "#66a61e", (0, (1, 1)), 1.1),
    "crgar|strategy=time_window": ("SR+TimeWin", "#1b9e77", "-", 1.8),
    "crgar|strategy=crit_expand": ("SR+Crit", "#e6ab02", (0, (5, 1)), 1.6),
}

recs = [json.loads(l) for f in sorted(glob.glob(str(RUNS / "*.jsonl"))) for l in open(f)]
zstar = {}
for r in recs:
    if r["objective"] is not None and r["step"] >= 1:
        k = (r["stream"], r["step"])
        zstar[k] = min(zstar.get(k, float("inf")), r["objective"])


def gap_on_grid(events, z, grid):
    g = np.ones_like(grid)
    for t, obj, _src in sorted(events, key=lambda e: e[0]):
        if t <= grid[-1]:
            g[grid >= t] = np.minimum(g[grid >= t], (obj - z) / z)
    return g


budget = 8.0
grid = np.linspace(0, budget, 401)
sizes = ["15x15", "20x20"]
fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.3))
summary = {}
for ax, size in zip(axes, sizes):
    for method, (label, color, ls, lw) in STYLE.items():
        rows = [r for r in recs if r["method"] == method and r["size"] == size and r["step"] >= 1]
        assert rows, f"no rows for {method} / {size}"
        arr = np.vstack([gap_on_grid(r["events"], zstar[(r["stream"], r["step"])], grid) for r in rows])
        med = np.median(arr, axis=0)
        ax.plot(grid, 100 * med, color=color, linestyle=ls, linewidth=lw, label=label)
        summary[(size, label)] = (len(rows), {t: float(100 * med[np.searchsorted(grid, t)]) for t in (1.0, 4.0, 8.0)})
    ax.set_xlim(0, budget)
    ax.set_ylim(0, 14)
    ax.set_xlabel("wall-clock time (s)")
    ax.set_title(f"{size.replace('x', r'$\times$')} job shop", fontsize=9)
    ax.grid(alpha=0.25, linewidth=0.5)
axes[0].set_ylabel(r"median gap to $z^*$ (\%)")
axes[-1].legend(loc="upper right", frameon=False, ncol=1)
fig.tight_layout(pad=0.3)
out = Path(__file__).parent
fig.savefig(out / "trajectories.pdf")
for k, v in sorted(summary.items()):
    print(k, v)
(Path(__file__).with_name("figure2_numbers.json")).write_text(
    json.dumps({f"{s}|{l}": {"n": n, "median_gap_pct": g} for (s, l), (n, g) in summary.items()}, indent=1))
print("wrote", out / "trajectories.pdf")
