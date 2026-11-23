"""Figure 6: robustness heatmap across all confirmatory settings (budgets,
worker counts, disruption types, published-benchmark bases). Consolidates the
U3-U9 secondary-setting prose (one paragraph each in the prior manuscript)
plus U1 into a single grid: rows = comparator (SR = IAIP-SR, Port = Port+Hint),
columns = confirmatory setting. Cell colour = mean relative PI difference
(SR+Crit vs. comparator; negative/green = SR+Crit better); a cell is annotated
"n.s." and outlined (not filled) when it fails the manuscript's own
significance criterion (Holm-adjusted p < 0.05 AND bootstrap CI excludes
zero). Every value is read directly from
results/unified_icaps/confirmatory/confirmatory_analysis.json -- no value is
hand-typed.

    .venv/bin/python paper/icaps27_unified_visual/figures/make_figure6_heatmap.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{helvet}\usepackage{sansmath}\sansmath\renewcommand{\familydefault}{\sfdefault}",
    "font.family": "sans-serif", "font.size": 9, "axes.labelsize": 9,
})
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
conf = json.loads((ROOT / "results/unified_icaps/confirmatory/confirmatory_analysis.json").read_text())

COLS = [
    ("U4_b2", "2s\n(budget)"),
    ("U1_primary", "8s\n(primary)"),
    ("U5_b30", "30s\n(budget)"),
    ("U3_workers4", "4 workers\n(parallel)"),
    ("U6_arrival", "arrival\n(disrupt.)"),
    ("U7_outage", "outage\n(disrupt.)"),
    ("U8_high", "high sev.\n(disrupt.)"),
    ("U9_benchmarks", "34 published\nbases"),
]
ROWS = [
    ("B2_crit vs B0_iaip", r"vs.\ \textsc{SR}"),
    ("B2_crit vs B6_port_hint", r"vs.\ \textsc{Port+Hint}"),
]


def pull(setting, key):
    c = conf["settings"][setting]["comparisons"][key]["pi"]
    mean = 100 * c["rel_diff"]
    lo, hi = 100 * c["ci95"][0] / c["mean_b"], 100 * c["ci95"][1] / c["mean_b"]
    sig = (hi < 0 or lo > 0) and c["sign_p_holm"] < 0.05
    return mean, sig, conf["settings"][setting]["n_units"]


grid = np.zeros((len(ROWS), len(COLS)))
sig_grid = np.zeros_like(grid, dtype=bool)
n_grid = np.zeros_like(grid, dtype=int)
for i, (rkey, _) in enumerate(ROWS):
    for j, (setting, _) in enumerate(COLS):
        mean, sig, n = pull(setting, rkey)
        grid[i, j] = mean
        sig_grid[i, j] = sig
        n_grid[i, j] = n

fig, ax = plt.subplots(figsize=(7.2, 2.3))
vmax = np.abs(grid).max()
im = ax.imshow(grid, cmap="RdYlGn_r", vmin=-vmax, vmax=vmax, aspect="auto")

for i in range(len(ROWS)):
    for j in range(len(COLS)):
        val = grid[i, j]
        sig = sig_grid[i, j]
        txt = f"{val:+.1f}" + ("" if sig else "\n(n.s.)")
        color = "white" if abs(val) > vmax * 0.55 else "black"
        if not sig:
            ax.add_patch(plt.Rectangle((j - 0.42, i - 0.42), 0.84, 0.84, fill=False, edgecolor="black",
                                        linewidth=1.5, linestyle=(0, (2, 1)), zorder=5))
            color = "black"
        ax.text(j, i, txt, ha="center", va="center", fontsize=7.2, color=color)

ax.set_xticks(range(len(COLS)))
ax.set_xticklabels([c[1] for c in COLS], fontsize=7.4)
ax.set_yticks(range(len(ROWS)))
ax.set_yticklabels([r[1] for r in ROWS], fontsize=8.2)
ax.set_xticks(np.arange(-0.5, len(COLS), 1), minor=True)
ax.set_yticks(np.arange(-0.5, len(ROWS), 1), minor=True)
ax.grid(which="minor", color="white", linewidth=1.5)
ax.tick_params(which="minor", length=0)
ax.set_title(
    r"relative PI difference (\%): \textsc{SR+Crit} vs.\ comparator (negative/green = \textsc{SR+Crit} better); "
    r"dashed box = not significant",
    fontsize=7.6, loc="left", pad=8)
cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
cbar.ax.tick_params(labelsize=6.8)
cbar.set_label("rel.\\ PI diff.\\ (\\%)", fontsize=7.2)

fig.subplots_adjust(left=0.14, right=0.93, top=0.78, bottom=0.18)
out = Path(__file__).with_name("robustness_heatmap.pdf")
fig.savefig(out)
print("wrote", out)
for i, (rkey, rlabel) in enumerate(ROWS):
    for j, (setting, clabel) in enumerate(COLS):
        print(f"{rlabel:20s} {clabel.replace(chr(10),' '):20s} mean={grid[i,j]:+.1f}%  sig={sig_grid[i,j]}  n={n_grid[i,j]}")
