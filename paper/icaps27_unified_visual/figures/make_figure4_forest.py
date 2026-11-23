"""Figure 4: horizontal forest plot of the U1 primary confirmatory comparisons
(SR+Crit vs each of 6 comparators). Built directly from
results/unified_icaps/confirmatory/confirmatory_analysis.json (the same
archived, independently-re-verified numbers used throughout this project;
no value is hand-typed). Mean relative PI difference + stream-clustered 95%
bootstrap CI; a comparison is marked significant only if its Holm-adjusted
p < 0.05 AND its CI excludes zero (both conditions, matching the manuscript's
own criteria C1-C6).

    .venv/bin/python paper/icaps27_unified_visual/figures/make_figure4_forest.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{helvet}\usepackage{sansmath}\sansmath\renewcommand{\familydefault}{\sfdefault}",
    "font.family": "sans-serif", "font.size": 9, "axes.labelsize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8.5,
})
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
conf = json.loads((ROOT / "results/unified_icaps/confirmatory/confirmatory_analysis.json").read_text())
u1 = conf["settings"]["U1_primary"]["comparisons"]

# (comparison key, display label), in the order the task's priority list implies
ORDER = [
    ("B2_crit vs B0_iaip", r"vs.\ \textsc{SR} (IAIP-SR)"),
    ("B2_crit vs B1_random", r"vs.\ \textsc{SR+Rand}"),
    ("B2_crit vs B4_prec", r"vs.\ \textsc{SR+Prec}"),
    ("B2_crit vs B3_timewin", r"vs.\ \textsc{SR+TimeWin}"),
    ("B2_crit vs B5_native1w", r"vs.\ \textsc{Port+Hint-ILS} (native, 1w)"),
    ("B2_crit vs B6_port_hint", r"vs.\ \textsc{Port+Hint}"),
]

fig, ax = plt.subplots(figsize=(4.4, 2.3))
ys = list(range(len(ORDER)))[::-1]
for y, (key, label) in zip(ys, ORDER):
    c = u1[key]["pi"]
    mean = 100 * c["rel_diff"]
    # ci95 is the bootstrap CI of the ABSOLUTE mean difference (raw PI units);
    # rel_diff = mean_diff / mean_b. Convert the CI to the same relative-%
    # scale as the point estimate using the same denominator, or the bar
    # would not even contain its own point estimate.
    lo, hi = 100 * c["ci95"][0] / c["mean_b"], 100 * c["ci95"][1] / c["mean_b"]
    holm = c["sign_p_holm"]
    sig = (hi < 0 or lo > 0) and holm < 0.05
    color = "#1b9e77" if sig and mean < 0 else ("#d95f02" if sig and mean > 0 else "#999999")
    marker = "o" if sig else "s"
    ax.plot([lo, hi], [y, y], color=color, lw=1.4, solid_capstyle="round")
    ax.plot([mean], [y], marker=marker, color=color, ms=5, mec="black", mew=0.4, zorder=3)
    tag = "" if sig else " (n.s.)"
    ax.text(hi + 1.0, y, f"{mean:+.1f}\\%{tag}", va="center", fontsize=7.6)

ax.axvline(0, color="black", lw=0.8, ls="-", zorder=0)
ax.set_yticks(ys)
ax.set_yticklabels([lbl for _, lbl in ORDER])
ax.set_xlabel(r"relative PI difference (\%); negative = \textsc{SR+Crit} better")
ax.set_xlim(-58, 25)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", alpha=0.25, linewidth=0.5)
fig.tight_layout(pad=0.3)
out = Path(__file__).with_name("forest_u1.pdf")
fig.savefig(out)
print("wrote", out)
for key, label in ORDER:
    c = u1[key]["pi"]
    lo, hi = 100 * c["ci95"][0] / c["mean_b"], 100 * c["ci95"][1] / c["mean_b"]
    print(f"{label:45s} mean={100*c['rel_diff']:+.1f}%  CI(rel)=[{lo:+.1f},{hi:+.1f}]  holm={c['sign_p_holm']:.2g}")
