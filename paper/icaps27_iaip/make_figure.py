"""Figure 1 of the revised manuscript: median gap to z* vs. wall-clock time on
the confirmatory stream instances (held-out streams 501-520, steps 1-10,
solver seeds 0-4), from results/research_extension/confirmatory/runs.

z* is shared per physical instance across all ten confirmatory methods and
seeds, as in phase0/analyze_confirmatory.py. Text is typeset through LaTeX so
the PDF embeds Type 1 fonts only (AAAI kit rule); lines differ in style as
well as colour so the figure reads in grayscale.

    .venv/bin/python paper/icaps27_iaip/make_figure.py
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
    "font.size": 9, "axes.labelsize": 9, "legend.fontsize": 7.5,
    "xtick.labelsize": 8, "ytick.labelsize": 8,
})
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "results/research_extension/confirmatory/runs"
STYLE = {  # method: (label, colour, linestyle, width)
    "cold": ("Cold", "#4d4d4d", ":", 1.3),
    "iaip|portfolio=fresh": ("fresh portfolio + Cold", "#d95f02", "--", 1.3),
    "floor": ("Floor", "#7570b3", "-.", 1.3),
    "iaip|portfolio=full|global_mode=hinted": ("portfolio + hinted", "#e7298a", (0, (5, 1, 1, 1)), 1.3),
    "iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted": ("IAIP-SR", "#1b9e77", "-", 2.0),
}

recs = [json.loads(l) for f in sorted(glob.glob(str(RUNS / "*.jsonl"))) for l in open(f)]
zstar = {}
for r in recs:
    if r["objective"] is not None:
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
fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.1))
summary = {}
for ax, size in zip(axes, sizes):
    for method, (label, color, ls, lw) in STYLE.items():
        rows = [r for r in recs if r["method"] == method and r["size"] == size and r["step"] >= 1]
        arr = np.vstack([gap_on_grid(r["events"], zstar[(r["stream"], r["step"])], grid) for r in rows])
        med = np.median(arr, axis=0)
        ax.plot(grid, 100 * med, color=color, linestyle=ls, linewidth=lw, label=label)
        summary[(size, label)] = (len(rows), {t: float(100 * med[np.searchsorted(grid, t)]) for t in (1.0, 4.0, 8.0)})
    ax.set_xlim(0, budget)
    ax.set_ylim(0, 12)
    ax.set_xlabel("wall-clock time (s)")
    ax.set_title(f"{size.replace('x', r'$\times$')} job shop", fontsize=9)
    ax.grid(alpha=0.25, linewidth=0.5)
axes[0].set_ylabel(r"median gap (\%)")
axes[-1].legend(loc="upper right", frameon=False)
fig.tight_layout(pad=0.3)
out = Path(__file__).with_name("figures")
out.mkdir(exist_ok=True)
fig.savefig(out / "anytime.pdf")
res = {f"{s}|{l}": {"curves": n, "median_gap_pct_at": g} for (s, l), (n, g) in summary.items()}
(Path(__file__).with_name("figure_numbers.json")).write_text(json.dumps(res, indent=2))
for k, v in res.items():
    print(k, v)
print(f"wrote {out / 'anytime.pdf'}")
