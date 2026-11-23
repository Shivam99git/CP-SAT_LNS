"""Figure 5: critical-region vs. time-window targeting, before and after
round-count control (2-panel). This is the figure that must NOT retain the
superseded "critical beats time-window after arrivals" framing -- the
corrected, matched-round finding supersedes it (docs/final_icaps/03_critical_vs_timewindow.md).

Panel A (end-to-end / M1, confirmatory, full CI): SR+Crit vs SR+TimeWin, mean
relative PI difference, for the primary mixed-disruption stream population
(U1) and the two disruption-specific confirmatory settings that exist with a
matched SR+TimeWin arm (U6 arrival-only, U7 outage-only). Every point here is
read directly from results/unified_icaps/confirmatory/confirmatory_analysis.json
with full bootstrap CI and Holm-adjusted significance -- nothing hand-typed.

Panel B (matched-round / M2, mechanism-isolation protocol): the overall M2
crit-vs-timewin comparison (confirmatory, full CI, from the same JSON file)
plus the four by-disruption-type breakdowns. Those four points are
EXPLORATORY: they come from a post-hoc re-grouping of U2's existing records by
delta_kind that was never assigned a pre-registered multiplicity correction or
a separately-computed bootstrap CI (docs/final_icaps/03_critical_vs_timewindow.md
S3.5, S"Statistical reporting" table -- the source document is explicit that
"per-delta means not separately archived at full precision" and CIs were "not
separately computed for this post-hoc grouping"). They are transcribed here
verbatim from that already-published, already-verified table (not
re-invented) and are drawn with hollow markers and no error bar, explicitly
labelled "(exploratory, no CI)" in the legend, so a reader cannot mistake them
for confirmatory-grade evidence. An inset shows the companion explanation from
the same source: mean completed rounds under the uncontrolled end-to-end
protocol, critical vs. time-window, by disruption type -- the reason the
end-to-end sign looks reversed.

    .venv/bin/python paper/icaps27_unified_visual/figures/make_figure5_mechanism.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{helvet}\usepackage{sansmath}\sansmath\renewcommand{\familydefault}{\sfdefault}",
    "font.family": "sans-serif", "font.size": 9, "axes.labelsize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8.3,
})
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
conf = json.loads((ROOT / "results/unified_icaps/confirmatory/confirmatory_analysis.json").read_text())

GREEN, GRAY, ORANGE = "#1b9e77", "#999999", "#d95f02"


def pull(setting, key):
    c = conf["settings"][setting]["comparisons"][key]["pi"]
    mean = 100 * c["rel_diff"]
    lo, hi = 100 * c["ci95"][0] / c["mean_b"], 100 * c["ci95"][1] / c["mean_b"]
    sig = (hi < 0 or lo > 0) and c["sign_p_holm"] < 0.05
    return mean, lo, hi, sig, c["n_streams"]


# ---- Panel A: end-to-end (M1), confirmatory, full CI ----
panelA = [
    ("U1: mixed (primary)", pull("U1_primary", "B2_crit vs B3_timewin")),
    ("U6: arrival-only", pull("U6_arrival", "B2_crit vs B3_timewin")),
    ("U7: outage-only", pull("U7_outage", "B2_crit vs B3_timewin")),
]

# ---- Panel B: matched-round (M2) ----
# Overall M2 comparison: confirmatory, full CI, from the same verified JSON.
m2_overall = pull("U2_mechanism", "M2_crit vs M2_timewin")

# By-delta-kind breakdown: EXPLORATORY. Transcribed verbatim from the
# "Statistical reporting" table of docs/final_icaps/03_critical_vs_timewindow.md
# (the source document itself states these per-delta means/CIs were not
# separately archived/computed -- there is no JSON file to read them from).
# rel_diff sign convention matches pull(): negative = SR+Crit better.
m2_by_delta = [
    ("arrival", +8.9, 13, 27, 40),
    ("cancellation", +18.5, 9, 29, 38),
    ("duration_jitter", +13.3, 12, 26, 38),
    ("outage", +9.8, 11, 20, 31),
]

# Mean completed rounds under the uncontrolled end-to-end (M1) protocol, by
# disruption type -- the explanation for the Panel A/B sign difference.
# Same source document, S3.5 "round-count confound" table.
rounds_by_delta = [
    ("arrival", 3.15, 2.02),
    ("cancellation", 2.40, 1.85),
    ("duration_jitter", 2.91, 2.06),
    ("outage", 2.95, 1.88),
]

fig = plt.figure(figsize=(9.8, 2.55))
gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.25, 0.95], wspace=0.55)

# --- Panel A ---
axA = fig.add_subplot(gs[0])
ysA = list(range(len(panelA)))[::-1]
for y, (label, (mean, lo, hi, sig, n)) in zip(ysA, panelA):
    color = GREEN if sig and mean < 0 else (ORANGE if sig and mean > 0 else GRAY)
    marker = "o" if sig else "s"
    axA.plot([lo, hi], [y, y], color=color, lw=1.4, solid_capstyle="round")
    axA.plot([mean], [y], marker=marker, color=color, ms=5, mec="black", mew=0.4, zorder=3)
    tag = "" if sig else " (n.s.)"
    axA.text(hi + 1.2, y, f"{mean:+.1f}\\%{tag}", va="center", fontsize=7.4)
axA.axvline(0, color="black", lw=0.8)
axA.set_yticks(ysA)
axA.set_yticklabels([lbl for lbl, _ in panelA], fontsize=7.6)
axA.set_ylim(-0.7, len(panelA) - 0.3)
axA.set_xlim(-58, 28)
axA.set_xlabel(r"rel.\ PI diff.\ (\%); negative = \textsc{SR+Crit} better", fontsize=7.6)
axA.set_title(r"\textbf{A.} End-to-end protocol", fontsize=8.3, loc="left")
axA.spines[["top", "right"]].set_visible(False)
axA.grid(axis="x", alpha=0.25, linewidth=0.5)

# --- Panel B ---
axB = fig.add_subplot(gs[1])
rows = [("overall (confirmatory)", m2_overall, True)] + \
       [(f"{d}*", (mean, None, None, False, n), False)
        for d, mean, w, l, n in m2_by_delta]
ysB = list(range(len(rows)))[::-1]
for y, (label, vals, is_conf) in zip(ysB, rows):
    mean, lo, hi, sig, n = vals
    if is_conf:
        color = GREEN if sig and mean < 0 else (ORANGE if sig and mean > 0 else GRAY)
        axB.plot([lo, hi], [y, y], color=color, lw=1.4, solid_capstyle="round")
        marker = "o" if sig else "s"
        axB.plot([mean], [y], marker=marker, color=color, ms=5, mec="black", mew=0.4, zorder=3)
        tag = "" if sig else " (n.s.)"
        axB.text((hi or mean) + 1.2, y, f"{mean:+.1f}\\%{tag}", va="center", fontsize=7.4)
    else:
        # exploratory: hollow marker, no whisker, no significance claim
        color = ORANGE if mean > 0 else GRAY
        axB.plot([mean], [y], marker="D", color="white", mec=color, mew=1.3, ms=5.5, zorder=3)
        axB.text(mean + 1.2, y, f"{mean:+.1f}\\%", va="center", fontsize=7.4, style="italic")
axB.axvline(0, color="black", lw=0.8)
axB.set_yticks(ysB)
axB.set_yticklabels([lbl for lbl, _, _ in rows], fontsize=7.6)
axB.set_ylim(-0.7, len(rows) - 0.3)
axB.set_xlim(-25, 33)
axB.set_xlabel(r"rel.\ PI diff.\ (\%); negative = \textsc{SR+Crit} better; * = exploratory, no CI", fontsize=7.3)
axB.set_title(r"\textbf{B.} Matched-round protocol (M2)", fontsize=8.3, loc="left")
axB.spines[["top", "right"]].set_visible(False)
axB.grid(axis="x", alpha=0.25, linewidth=0.5)

# --- Panel C: mean completed rounds under the end-to-end protocol (explanation) ---
axC = fig.add_subplot(gs[2])
xs = list(range(len(rounds_by_delta)))
w = 0.35
axC.bar([x - w / 2 for x in xs], [r[1] for r in rounds_by_delta], width=w, color=GREEN, label="critical-region")
axC.bar([x + w / 2 for x in xs], [r[2] for r in rounds_by_delta], width=w, color=GRAY, label="time-window")
axC.set_xticks(xs)
short = {"arrival": "arrival", "cancellation": "cancel.", "duration_jitter": "dur.jit.", "outage": "outage"}
axC.set_xticklabels([short[r[0]] for r in rounds_by_delta], fontsize=7.0)
axC.set_ylabel("mean completed rounds", fontsize=7.4)
axC.tick_params(axis="y", labelsize=7.2)
axC.legend(fontsize=6.6, frameon=False, loc="upper left", ncol=1, handlelength=1.2, borderaxespad=0.1)
axC.set_title(r"\textbf{C.} Why A/B disagree", fontsize=8.3, loc="left", pad=6)
axC.spines[["top", "right"]].set_visible(False)

fig.subplots_adjust(left=0.135, right=0.985, top=0.85, bottom=0.22)
out = Path(__file__).with_name("mechanism_u2_u1.pdf")
fig.savefig(out)
print("wrote", out)
for label, (mean, lo, hi, sig, n) in panelA:
    print(f"A  {label:32s} mean={mean:+.1f}%  n={n}  sig={sig}")
print(f"B  overall (M2)                    mean={m2_overall[0]:+.1f}%  n={m2_overall[4]}  sig={m2_overall[3]}")
for d, mean, w_, l_, n in m2_by_delta:
    print(f"B  {d:20s} (exploratory)  mean={mean:+.1f}%  W/L={w_}/{l_}  n={n}")
