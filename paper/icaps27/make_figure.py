"""Figure 1 of the ICAPS-27 manuscript: median relative gap vs. wall-clock
time on stream instances, from the held-out trajectory capture
(results/icaps/figures/trajectories.pkl; seeds 201-206, which are disjoint
from every campaign's seeds).

AAAI forbids Type 3 fonts anywhere in the PDF (matplotlib's default) and also
CID/Identity-H fonts (what matplotlib's TrueType mode emits), so all text is
typeset through LaTeX to embed Type 1 Helvetica; the caller verifies this. Lines differ in
style as well as colour so the figure reads in grayscale.

    .venv/bin/python paper/icaps27/make_figure.py
"""

import pickle
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams.update({
    # Text is typeset by LaTeX so the PDF embeds Type 1 Helvetica (the AAAI
    # kit's recommended face for figure call-outs) -- matplotlib's own
    # TrueType embedding uses CID/Identity-H fonts, which the kit forbids.
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{helvet}\usepackage{sansmath}\sansmath\renewcommand{\familydefault}{\sfdefault}",
    "font.family": "sans-serif",
    "font.size": 9, "axes.labelsize": 9, "legend.fontsize": 8,
    "xtick.labelsize": 8, "ytick.labelsize": 8,
})
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from phase0.make_paper_figures import _gap_on_grid  # noqa: E402

STYLE = {  # method: (label, colour, linestyle)
    "cpsat_cold": ("cold (no reuse)", "#4d4d4d", "-"),
    "cpsat_warm": ("hint", "#d95f02", "--"),
    "boot_warm": ("floor + hint", "#7570b3", "-."),
    "boot_cold": ("floor (ours)", "#1b9e77", "-"),
}

rows = pickle.load(open(ROOT / "results/icaps/figures/trajectories.pkl", "rb"))
df = pd.DataFrame(rows)
df["objective"] = pd.to_numeric(df["objective"], errors="coerce")
bk = df[df.objective.notna()].groupby(["size", "seed", "stream_step"]).objective.min()

sizes = sorted(df["size"].unique())
fig, axes = plt.subplots(1, len(sizes), figsize=(6.6, 2.1), sharey=False)
summary = {}
for ax, size in zip(axes, sizes):
    sub = df[(df["size"] == size) & (df.stream_step >= 1)]
    budget = float(sub.budget.iloc[0])
    grid = np.linspace(0, budget, 400)
    for method, (label, color, ls) in STYLE.items():
        m = sub[sub.method == method]
        curves = [_gap_on_grid(r.trajectory, bk.loc[(r["size"], r.seed, r.stream_step)], grid)
                  for _, r in m.iterrows()]
        arr = np.vstack(curves)
        med = np.median(arr, axis=0)
        ax.plot(grid, 100 * med, color=color, linestyle=ls,
                linewidth=2.0 if method == "boot_cold" else 1.3, label=label.replace("%", r"\%"))
        summary[(size, method)] = (len(curves), float(med[np.searchsorted(grid, 1.0)]))
    ax.set_xlim(0, budget)
    ax.set_ylim(0, 12)
    ax.set_xlabel("wall-clock time (s)")
    ax.set_title(f"{size} job shop", fontsize=9)
    ax.grid(alpha=0.25, linewidth=0.5)
axes[0].set_ylabel(r"median gap (\%)")
axes[-1].legend(loc="upper right", frameon=False)
fig.tight_layout(pad=0.3)

out = Path(__file__).with_name("figures")
out.mkdir(exist_ok=True)
fig.savefig(out / "anytime.pdf")
for (size, method), (n, g1) in sorted(summary.items()):
    print(f"{size} {method:11s} curves={n} median_gap_at_1s={100 * g1:.2f}%")
print(f"wrote {out / 'anytime.pdf'}")
