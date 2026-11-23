"""Mechanism figure: critical-region vs. time-window under two protocols.

A  end-to-end protocol M1 (confirmatory; U1, U6, U7): read from
   results/unified_icaps/confirmatory/confirmatory_analysis.json.
B  matched-round protocol M2 (U2): overall (confirmatory) and by disruption
   type (EXPLORATORY: uncorrected, outside the pre-registered family). All
   values, including the CIs of the exploratory points, are recomputed from
   raw run records by scripts/multisolver/reproduce_mechanism.py
   (results/multisolver/audit/mechanism_reproduction.json).
C  completed restricted rounds per instance, and D  restricted-solver seconds
   per instance, under M1 and M2 (same file): M1 equalizes neither; M2
   equalizes rounds but not restricted solver time.
No value is hand-typed.

    .venv/bin/python paper/icaps27_multisolver_final/figures/make_figure5_mechanism.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{helvet}\usepackage{sansmath}\usepackage{textcomp}\sansmath\renewcommand{\familydefault}{\sfdefault}",
    "axes.unicode_minus": False, "font.family": "sans-serif", "font.size": 9, "axes.labelsize": 8.5, "xtick.labelsize": 7.8, "ytick.labelsize": 7.8,
})
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

# math-mode minus is nearly invisible at tick size with sansmath; use a text minus
SIGNED = FuncFormatter(lambda v, _: (r"\textminus " if v < 0 else "") + f"{abs(v):g}")
sgn = lambda v: (r"\textminus " if v < 0 else "+") + f"{abs(v):.1f}"  # typographic minus in text labels

ROOT = Path(__file__).resolve().parents[3]
conf = json.loads((ROOT / "results/unified_icaps/confirmatory/confirmatory_analysis.json").read_text())
mech = json.loads((ROOT / "results/multisolver/audit/mechanism_reproduction.json").read_text())
GREEN, GRAY, ORANGE = "#1b9e77", "#8c8c8c", "#d95f02"


def pull(setting, key):
    c = conf["settings"][setting]["comparisons"][key]["pi"]
    lo, hi = 100 * c["ci95"][0] / c["mean_b"], 100 * c["ci95"][1] / c["mean_b"]
    return 100 * c["rel_diff"], lo, hi, (hi < 0 or lo > 0) and c["sign_p_holm"] < 0.05


def forest(ax, rows, xlim, title):
    ys = list(range(len(rows)))[::-1]
    for y, (label, mean, lo, hi, sig, exploratory) in zip(ys, rows):
        color = (GREEN if mean < 0 else ORANGE) if sig else GRAY
        if exploratory:
            ax.plot([lo, hi], [y, y], color=color, lw=1.1, ls=(0, (2, 1.2)))
            ax.plot([mean], [y], marker="D", color="white", mec=color, mew=1.2, ms=5, zorder=3)
        else:
            ax.plot([lo, hi], [y, y], color=color, lw=1.5, solid_capstyle="round")
            ax.plot([mean], [y], marker="o" if sig else "s", color=color, ms=5, mec="black", mew=0.4, zorder=3)
        ax.text(hi + 1.0, y, f"{sgn(mean)}\\%" + ("" if sig or exploratory else " (n.s.)"), va="center", fontsize=7.2)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.set_xlim(*xlim)
    ax.xaxis.set_major_formatter(SIGNED)
    ax.set_xlabel(r"rel.\ PI diff.\ (\%); $<0$: \textsc{SR+Crit} better")
    ax.set_title(title, fontsize=8.4, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.25, lw=0.5)


rowsA = [(lbl, *pull(s, "B2_crit vs B3_timewin"), False)
         for lbl, s in [("U1 mixed", "U1_primary"), ("U6 arrival", "U6_arrival"), ("U7 outage", "U7_outage")]]
m2c = conf["settings"]["U2_mechanism"]["comparisons"]["M2_crit vs M2_timewin"]["pi"]
lo, hi = 100 * m2c["ci95"][0] / m2c["mean_b"], 100 * m2c["ci95"][1] / m2c["mean_b"]
rowsB = [("overall", 100 * m2c["rel_diff"], lo, hi, m2c["sign_p_holm"] < 0.05 and (lo > 0 or hi < 0), False)]
for kind, lbl in [("arrival", "arrival*"), ("cancellation", "cancellation*"), ("duration_jitter", "duration*"),
                  ("outage", "outage*")]:
    c = mech["M2_crit_vs_timewin_by_delta"][kind]
    lo, hi = c["ci95_rel_pct"]
    rowsB.append((lbl, c["rel_diff_pct"], lo, hi, lo > 0 or hi < 0, True))

fig = plt.figure(figsize=(10.4, 2.45))
gs = fig.add_gridspec(1, 4, width_ratios=[1.05, 1.15, 0.62, 0.62], wspace=0.62)
forest(fig.add_subplot(gs[0]), rowsA, (-40, 22), r"\textbf{A.} M1 end-to-end (confirmatory)")
forest(fig.add_subplot(gs[1]), rowsB, (-12, 40), r"\textbf{B.} M2 matched rounds")

m1, m2 = mech["M1_round_stats_U1"], mech["M2_round_stats_U2"]
for idx, (field, ylabel, letter) in enumerate([("mean_completed_rounds", "completed rounds / instance", "C"),
                                              ("mean_restricted_solver_s_per_instance",
                                               "restricted solver s / instance", "D")]):
    ax = fig.add_subplot(gs[2 + idx])
    vals = [(m1["B2_crit"][field], m1["B3_timewin"][field]), (m2["M2_crit"][field], m2["M2_timewin"][field])]
    w = 0.36
    for j, (c, t) in enumerate(vals):
        ax.bar(j - w / 2, c, w, color=GREEN, label="critical" if j == 0 else None)
        ax.bar(j + w / 2, t, w, color=GRAY, hatch="///", edgecolor="white", lw=0, label="time window" if j == 0 else None)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["M1", "M2"])
    ax.set_ylabel(ylabel, fontsize=7.6)
    ax.set_title(rf"\textbf{{{letter}.}}", fontsize=8.4, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(0, 1.32 * max(max(v) for v in vals))
    if idx == 0:
        ax.legend(fontsize=6.4, frameon=False, loc="upper left", handlelength=1.1, ncol=2, columnspacing=0.6)
fig.subplots_adjust(left=0.075, right=0.99, top=0.86, bottom=0.21)
out = Path(__file__).with_name("mechanism_u2_u1.pdf")
fig.savefig(out)
print("wrote", out)
for r in rowsA + rowsB:
    print(f"  {r[0]:14s} {r[1]:+6.1f}% CI=[{r[2]:+.1f},{r[3]:+.1f}] sig={r[4]} exploratory={r[5]}")
