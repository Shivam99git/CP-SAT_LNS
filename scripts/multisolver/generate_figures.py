"""Multisolver figures S1-S6 and LaTeX tables S1-S4 (Task 10), generated from
raw run records via analyze_results (same z*, same PI, same deadline rule).
No value is hand-typed.

    .venv_ms/bin/python scripts/multisolver/generate_figures.py --phase heldout --outdir paper/icaps27_multisolver_final/figures/ms
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{helvet}\usepackage{sansmath}\usepackage{textcomp}\sansmath\renewcommand{\familydefault}{\sfdefault}",
    "axes.unicode_minus": False, "font.family": "sans-serif", "font.size": 8.5, "axes.labelsize": 8.2,
    "xtick.labelsize": 7.6, "ytick.labelsize": 7.8, "legend.fontsize": 6.8,
})
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, NullFormatter  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_results import ROOT, load, summarize  # noqa: E402

SIGNED = FuncFormatter(lambda v, _: (r"\textminus " if v < 0 else "") + f"{abs(v):g}")
# log/symlog exponents lose their minus under sansmath: label ticks in plain decimals instead
PLAIN = FuncFormatter(lambda v, _: "0" if v == 0 else (f"{v:.10f}".rstrip("0").rstrip(".") if v < 1 else f"{v:g}"))
NAMES = {"cpsat": "CP-SAT", "cpoptimizer": "CP Optimizer", "gecode": "Gecode", "chuffed": "Chuffed",
         "gurobi": "Gurobi", "cplex": "CPLEX", "scip": "SCIP", "highs": "HiGHS", "cbc": "CBC", "glpk": "GLPK"}
TECH = {"cpsat": "CP", "cpoptimizer": "CP", "gecode": "CP", "chuffed": "CP", "gurobi": "MIP", "cplex": "MIP",
        "scip": "MIP", "highs": "MIP", "cbc": "MIP", "glpk": "MIP"}
FINAL_ONLY = {"cbc", "glpk"}
ORDER = ["cpsat", "cpoptimizer", "gecode", "chuffed", "gurobi", "cplex", "scip", "highs", "cbc", "glpk"]
MCOL = {"S0": "#4d4d4d", "S1": "#e7298a", "S2": "#7570b3", "S3": "#d95f02", "S4": "#1b9e77", "S5": "#66a61e"}
MMARK = {"S0": "o", "S1": "v", "S2": "s", "S3": "D", "S4": "^", "S5": "P"}
MLAB = {"S0": "S0 cold", "S1": "S1 warm start", "S2": "S2 retained incumbent", "S3": "S3 portfolio",
        "S4": "S4 portfolio + rounds", "S5": "S5 native LNS"}
TIERLAB = {"S": r"8$\times$6 (licence tier)", "M15": r"15$\times$15", "M20": r"20$\times$20"}


def stream_means(rows, key, field="pi"):
    acc = defaultdict(list)
    for r in rows:
        if r["key"] == key:
            acc[r["stream"]].append(r[field])
    return [sum(v) / len(v) for v in acc.values()]


def boot(xs, reps=4000, seed=3):
    if not xs:
        return None, None, None
    rng = random.Random(seed)
    n = len(xs)
    ms = sorted(sum(rng.choice(xs) for _ in range(n)) / n for _ in range(reps))
    return sum(xs) / n, ms[int(0.025 * reps)], ms[int(0.975 * reps) - 1]


def licence_limited(rows, key):
    rs = [r for r in rows if r["key"] == key]
    return bool(rs) and all(r["licence_limited"] for r in rs)


def save(fig, outdir, name):
    p = outdir / f"{name}.pdf"
    fig.savefig(p)
    plt.close(fig)
    print("wrote", p)


def fig_s1(rows, outdir, exp="AB"):
    tiers = ["S", "M15", "M20"]
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.5), sharey=True)
    ys = list(range(len(ORDER)))[::-1]
    for ax, t in zip(axes, tiers):
        for y, s in zip(ys, ORDER):
            key = (exp, t, s, "S0", 8, 1)
            m, lo, hi = boot(stream_means(rows, key))
            if m is None or licence_limited(rows, key):
                ax.text(0.5, y, "not executed (licence)" if m is not None or s in ("cpoptimizer", "gurobi", "cplex")
                        else "not run", va="center", ha="center", fontsize=6.4, color="#777777",
                        transform=ax.get_yaxis_transform())
                continue
            feas = sum(r["feasible"] for r in rows if r["key"] == key) / max(1, sum(r["key"] == key for r in rows))
            c = "#1b9e77" if TECH[s] == "CP" else "#7570b3"
            ax.plot([lo, hi], [y, y], color=c, lw=1.4)
            ax.plot([m], [y], marker="o" if TECH[s] == "CP" else "s", color=c, ms=4.5, mec="black", mew=0.4)
            lab = f"{100 * feas:.0f}\\%"
            ax.text(1.02, y, lab, va="center", fontsize=6.2, transform=ax.get_yaxis_transform())
        ax.set_xscale("symlog", linthresh=1e-3)
        ax.set_xlim(0, 1.05)
        ax.set_xticks([0, 1e-3, 1e-2, 1e-1, 1])
        ax.xaxis.set_major_formatter(PLAIN)
        ax.set_title(TIERLAB[t], fontsize=8.2)
        ax.set_xlabel("mean PI (bounded gap)")
        ax.grid(axis="x", alpha=0.25, lw=0.5)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_yticks(ys)
    axes[0].set_yticklabels([NAMES[s] + (r"$^\dagger$" if s in FINAL_ONLY else "") for s in ORDER])
    fig.subplots_adjust(left=0.13, right=0.95, top=0.88, bottom=0.2, wspace=0.28)
    save(fig, outdir, "s1_engines_cold")


def gap_at(events, z, t):
    g = 1.0
    for te, obj, *_ in events:
        if te > t:
            break
        g = (obj - z) / obj
    return g


def fig_s2(recs, z, outdir, exp="AB"):
    grid = [0.0] + [8.0 * (i / 200) ** 2 for i in range(1, 201)]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.3))
    styles = {s: ls for s, ls in zip(ORDER, ["-", "--", "-.", ":", "-", "--", "-.", ":", "-", "--"])}
    for ax, t in zip(axes, ["S", "M15"]):
        for s in ORDER:
            rs = [r for r in recs if r["experiment"] == exp and r["tier"] == t and r["solver"] == s
                  and r["method"] == "S0" and r["budget"] == 8 and r["workers"] == 1 and r.get("status") != "NOT_SUPPORTED"]
            if not rs or all(any(st.get("status") == "LICENSE_LIMIT" for st in r.get("stages", [])) for r in rs):
                continue
            curves = []
            for r in rs:
                ev = [e for e in r.get("events", []) if e[0] <= 8.0] if r.get("status") == "OK" else []
                curves.append([gap_at(ev, z[r["instance_hash"]], g) for g in grid])
            med = [sorted(c[i] for c in curves)[len(curves) // 2] for i in range(len(grid))]
            ax.step(grid, med, where="post", ls=styles[s], lw=1.2,
                    color="#1b9e77" if TECH[s] == "CP" else "#7570b3", alpha=0.9,
                    label=NAMES[s] + (r"$^\dagger$" if s in FINAL_ONLY else ""))
        ax.set_xscale("symlog", linthresh=0.05)
        ax.set_xlim(0, 8)
        ax.set_xticks([0, 0.05, 0.1, 0.5, 1, 2, 4, 8])
        ax.xaxis.set_major_formatter(PLAIN)
        ax.set_ylim(-0.01, 1.01)
        ax.set_xlabel("elapsed wall-clock time (s)")
        ax.set_title(TIERLAB[t] + ", cold (S0)", fontsize=8.2)
        ax.grid(alpha=0.25, lw=0.5)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("median bounded gap")
    axes[1].legend(ncol=1, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.02), handlelength=2.4)
    fig.subplots_adjust(left=0.08, right=0.84, top=0.88, bottom=0.2, wspace=0.18)
    save(fig, outdir, "s2_trajectories")


def fig_s34(rows, outdir, exp="AB"):
    tiers = ["S", "M15", "M20"]
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.3), sharey=True)
    ys = list(range(len(ORDER)))[::-1]
    for ax, t in zip(axes, tiers):
        for y, s in zip(ys, ORDER):
            for k, m in enumerate(["S0", "S1", "S2", "S3", "S4", "S5"]):
                key = (exp, t, s, m, 8, 1)
                xs = stream_means(rows, key)
                if not xs or licence_limited(rows, key):
                    continue
                v = sum(xs) / len(xs)
                ax.plot([v], [y + (k - 2.5) * 0.11], marker=MMARK[m], color=MCOL[m], ms=3.8, mec="black", mew=0.25,
                        ls="none", label=MLAB[m] if (y == ys[0] and t == "S") else None)
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(PLAIN)
        ax.set_title(TIERLAB[t], fontsize=8.2)
        ax.set_xlabel("mean PI (bounded gap, log)")
        ax.grid(axis="x", alpha=0.25, lw=0.5, which="both")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_yticks(ys)
    axes[0].set_yticklabels([NAMES[s] + (r"$^\dagger$" if s in FINAL_ONLY else "") for s in ORDER])
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, ncol=6, frameon=False, loc="upper center", bbox_to_anchor=(0.55, 1.0), handletextpad=0.2,
               columnspacing=0.8)
    fig.subplots_adjust(left=0.13, right=0.99, top=0.80, bottom=0.2, wspace=0.12)
    save(fig, outdir, "s34_within_solver")


def fig_s4b(recs, z, outdir, exp="AB"):
    """Where S4's improvement over its (engine-independent) portfolio incumbent comes from, per
    engine and tier: each S4 trajectory is replayed with only its portfolio events, then with
    portfolio + initial stage + rounds, then in full (post-hoc descriptive; see attribute_stages.py)."""
    from analyze_results import pi_of
    from attribute_stages import stage_of
    tiers = ["S", "M15", "M20"]
    acc = defaultdict(lambda: defaultdict(lambda: [[], [], []]))
    for r in recs:
        if (r.get("experiment") != exp or r.get("method") != "S4" or r.get("budget") != 8 or r.get("workers") != 1
                or r.get("status") != "OK" or r.get("instance_hash") not in z):
            continue
        B, zh = r["budget"], z[r["instance_hash"]]
        ev = [e for e in r["events"] if e[0] <= B]
        cell = acc[(r["tier"], r["solver"])][r["stream"]]
        cell[0].append(pi_of([e for e in ev if stage_of(e[2]) == "portfolio"], zh, B))
        cell[1].append(pi_of([e for e in ev if stage_of(e[2]) != "global"], zh, B))
        cell[2].append(pi_of(ev, zh, B))
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.05), sharey=True)
    for ax, t in zip(axes, tiers):
        for y, s in enumerate(ORDER):
            if (t, s) not in acc:
                ax.text(0.002, y, "not executed (licence)", fontsize=6, color="0.5", va="center")
                continue
            per = list(acc[(t, s)].values())
            port, pre, full = (sum(sum(c[i]) / len(c[i]) for c in per) / len(per) for i in range(3))
            ax.barh(y, full, color="#bdbdbd", height=0.62, lw=0)
            ax.barh(y, max(pre - full, 0), left=full, color="#d95f02", height=0.62, lw=0)
            ax.barh(y, max(port - pre, 0), left=max(pre, full), color="#1b9e77", height=0.62, lw=0)
        ax.set_yticks(range(len(ORDER)))
        ax.set_yticklabels([NAMES[s] + (r"$^\dagger$" if s in FINAL_ONLY else "") for s in ORDER])
        ax.set_title(TIERLAB[t], fontsize=8.2)
        ax.set_xlabel("mean PI (bounded gap)")
        ax.set_xlim(0, None)
        ax.xaxis.set_major_formatter(PLAIN)
        ax.grid(axis="x", alpha=0.25, lw=0.5)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylim(len(ORDER) - 0.5, -0.5)
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color="#1b9e77", label="removed by initial stage + restricted rounds"),
                        Patch(color="#d95f02", label="removed by warm/global stage"),
                        Patch(color="#bdbdbd", label="remaining PI of S4")],
               frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.55, 1.0))
    fig.subplots_adjust(left=0.11, right=0.985, top=0.78, bottom=0.2, wspace=0.12)
    save(fig, outdir, "s4b_stage_attribution")


SCOL = dict(zip(ORDER, ["#1b9e77", "#66a61e", "#e6ab02", "#a6761d", "#d95f02", "#e7298a", "#7570b3", "#1f78b4",
                        "#666666", "#b15928"]))
SLS = {s: ("-" if TECH[s] == "CP" else "--") for s in ORDER}


def fig_s5(rows, outdir, exp="AB"):
    """Scalability: mean PI (stream-clustered) against tier for cold S0 and for S4, and S4 by disruption
    type on the paper-scale tiers. Disruption severity is not varied in the multisolver campaign (one
    delta per step, as in the CP-SAT study's primary setting); this is stated in the caption."""
    tiers = ["S", "M15", "M20"]
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.45), gridspec_kw={"width_ratios": [1, 1, 1.25]})
    for ax, m in zip(axes[:2], ("S0", "S4")):
        for s in ORDER:
            xs, vs = [], []
            for i, t in enumerate(tiers):
                key = (exp, t, s, m, 8, 1)
                sm = stream_means(rows, key)
                if not sm or licence_limited(rows, key):
                    continue
                xs.append(i); vs.append(sum(sm) / len(sm))
            if xs:
                ax.plot(xs, vs, ls=SLS[s], marker="o", ms=2.8, lw=1.0, color=SCOL[s],
                        label=NAMES[s] + (r"$^\dagger$" if s in FINAL_ONLY else "") if m == "S0" else None)
        ax.set_yscale("log"); ax.yaxis.set_major_formatter(PLAIN); ax.yaxis.set_minor_formatter(NullFormatter())
        ax.set_xticks(range(3)); ax.set_xticklabels([TIERLAB[t].replace(" (licence tier)", "") for t in tiers])
        ax.set_title({"S0": "S0 cold", "S4": "S4 portfolio + rounds"}[m], fontsize=8.2)
        ax.set_xlim(-0.25, 2.25)
        ax.grid(alpha=0.25, lw=0.5)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("mean PI (bounded gap, log)")
    kinds = ["arrival", "cancellation", "duration", "outage"]
    ax = axes[2]
    for s in ORDER:
        vs = []
        for kd in kinds:
            rs = [r["pi"] for r in rows if r["key"][:4] in ((exp, "M15", s, "S4"), (exp, "M20", s, "S4"))
                  and r["key"][4:] == (8, 1) and (r["delta_kind"] or "").startswith(kd)]
            vs.append(sum(rs) / len(rs) if rs else None)
        if any(v is not None for v in vs):
            ax.plot([i for i, v in enumerate(vs) if v is not None], [v for v in vs if v is not None],
                    ls=SLS[s], marker="o", ms=2.8, lw=1.0, color=SCOL[s])
    ax.set_ylim(0, None); ax.yaxis.set_major_formatter(PLAIN)
    ax.set_xticks(range(4)); ax.set_xticklabels(["arrival", "cancel.", "duration", "outage"])
    ax.set_title(r"S4 by disruption type (15$\times$15 + 20$\times$20)", fontsize=8.2)
    ax.grid(alpha=0.25, lw=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, ncol=10, frameon=False, loc="upper center", bbox_to_anchor=(0.52, 1.0), handlelength=1.6,
               columnspacing=0.7, handletextpad=0.3, fontsize=6.2)
    fig.subplots_adjust(left=0.08, right=0.99, top=0.80, bottom=0.12, wspace=0.28)
    save(fig, outdir, "s5_scalability")


def fig_s6(rows, outdir, exp="AB"):
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.2))
    pts = defaultdict(list)
    for r in rows:
        if r["key"][0] == exp and r["key"][3] == "S0" and r["key"][5] == 1 and r["vars"]:
            fam = {"cpsat": "CP-SAT interval model", "cpoptimizer": "CP Optimizer interval model",
                   "gecode": "MiniZinc model", "chuffed": "MiniZinc model"}.get(r["key"][2], "MILP (all MIP engines)")
            pts[fam].append((r["n_ops"], r["vars"], r["binary"], r["constraints"], r["build_s"]))
    cols = {"CP-SAT interval model": "#1b9e77", "CP Optimizer interval model": "#66a61e", "MiniZinc model": "#e6ab02",
            "MILP (all MIP engines)": "#7570b3"}
    for fam, ps in pts.items():
        ps = sorted(set(ps))
        axes[0].scatter([p[0] for p in ps], [p[1] for p in ps], s=6, color=cols[fam], label=fam + " (variables)")
        if fam.startswith("MILP"):
            axes[0].scatter([p[0] for p in ps], [p[3] for p in ps], s=6, marker="x", color=cols[fam],
                            label="MILP (constraints)")
        axes[1].scatter([p[0] for p in ps], [p[4] for p in ps], s=6, color=cols[fam], label=fam)
    for ax in axes:
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.xaxis.set_major_formatter(PLAIN); ax.yaxis.set_major_formatter(PLAIN)
        ax.xaxis.set_minor_formatter(NullFormatter()); ax.yaxis.set_minor_formatter(NullFormatter())
        ax.set_xticks([25, 50, 100, 200, 400])
        ax.set_xlabel("operations in instance")
        ax.grid(alpha=0.25, lw=0.5, which="both")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("model size (count)")
    axes[1].set_ylabel("model build + translation (s)")
    axes[0].legend(frameon=False, fontsize=5.8, loc="upper left")
    fig.subplots_adjust(left=0.08, right=0.98, top=0.95, bottom=0.18, wspace=0.3)
    save(fig, outdir, "s6_model_overhead")


def fmt(x, d=4):
    return "--" if x is None else f"{x:.{d}f}"


def tables(analysis, rows, tabdir, exp="AB"):
    cfg = analysis["configs"]
    inv = json.loads((ROOT / "results/multisolver/solver_inventory.json").read_text())
    # S1 availability
    L = [r"\begin{tabular}{lllllllll}", r"\toprule",
         r"Solver & Tech. & Version & Licence & Status & Warm start & Anytime & Threads & Interface \\", r"\midrule"]
    for s in ORDER:
        e = inv["solvers"][s]
        lim = e.get("documented_size_limit")
        lic = "open source" if not lim else f"free ed., $\\le${lim[0]} vars/{lim[1]} cons."
        api = "MiniZinc" if s in ("gecode", "chuffed") else ("OR-Tools" if s == "cbc" else "Python API")
        L.append(f"{NAMES[s]} & {TECH[s]} & {e.get('version', '-').split(' (')[0]} & {lic} & executed & "
                 f"{e['warm_start'].replace('_', ' ') if e['warm_start'] != 'none' else 'no'} & "
                 f"{e['anytime_trajectory'].replace('_', ' ')} & {'1/4' if e['parallel_workers'] else '1'} & {api} \\\\")
    L.append(r"\midrule")
    seen = set()
    for name, why in inv.get("not_installed", {}).items():
        if "Hexaly" in name and "Hexaly" in seen:
            continue
        seen.add("Hexaly" if "Hexaly" in name else name)
        tech = "CP" if "Choco" in name else ("MIP" if "Xpress" in name else "LS")
        reason = "no Java runtime" if "Java" in why else "commercial, no licence"
        L.append(f"{name.replace('LocalSolver/', '')} & {tech} & -- & {reason} & not executed & -- & -- & -- & -- \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    (tabdir / "tab_s1_availability.tex").write_text("\n".join(L) + "\n")
    # S2 main cross-solver results (cold, 8 s, 1 worker)
    for t in ("S", "M15", "M20"):
        L = [r"\begin{tabular}{lrrrrrrrr}", r"\toprule",
             r"Solver & PI & median PI & final gap & first feas.\ (s) & build (s) & runtime (s) & feasible & proven opt. \\",
             r"\midrule"]
        for s in ORDER:
            c = cfg.get(f"{exp}|{t}|{s}|S0|8|1")
            if c is None:
                continue
            if c["licence_limited_rate"] >= 1.0:
                L.append(f"{NAMES[s]} & \\multicolumn{{8}}{{c}}{{not executed: model exceeds bundled licence}} \\\\")
                continue
            L.append(f"{NAMES[s]}{'$^\\dagger$' if s in FINAL_ONLY else ''} & {fmt(c['mean_pi'])} & {fmt(c['median_pi'])} & " +
                     ("--" if c['mean_final_gap'] is None else f"{100 * c['mean_final_gap']:.2f}\\%") + " & " +
                     f"{fmt(c['mean_t_first'], 3)} & {fmt(c['mean_build_s'], 3)} & {fmt(c['mean_total_s'], 2)} & "
                     f"{100 * c['feasible_rate']:.0f}\\% & {100 * c['proven_optimal_rate']:.0f}\\% \\\\")
        L += [r"\bottomrule", r"\end{tabular}"]
        (tabdir / f"tab_s2_cold_{t}.tex").write_text("\n".join(L) + "\n")
    # S3 within-solver ablation (mean PI per method)
    for t in ("S", "M15", "M20"):
        L = [r"\begin{tabular}{lrrrrrr}", r"\toprule", r"Solver & S0 & S1 & S2 & S3 & S4 & S5 \\", r"\midrule"]
        for s in ORDER:
            vals = []
            for m in ("S0", "S1", "S2", "S3", "S4", "S5"):
                c = cfg.get(f"{exp}|{t}|{s}|{m}|8|1")
                vals.append("--" if c is None or c["licence_limited_rate"] >= 1.0 else fmt(c["mean_pi"]))
            if any(v != "--" for v in vals):
                L.append(f"{NAMES[s]} & " + " & ".join(vals) + r" \\")
        L += [r"\bottomrule", r"\end{tabular}"]
        (tabdir / f"tab_s3_ablation_{t}.tex").write_text("\n".join(L) + "\n")
    # S4 resources (cold and S4, 8 s; 4-worker runs where present)
    L = [r"\begin{tabular}{lllrrrrrrrr}", r"\toprule",
         r"Solver & tier & exp. & threads & vars & binary & constr. & CPU s & CPU/wall & RSS MB & max overrun (s) \\",
         r"\midrule"]
    for e_, w in ((exp, 1), ("W4", 4)):
        for t in ("S", "M15", "M20"):
            for s in ORDER:
                c = cfg.get(f"{e_}|{t}|{s}|S0|8|{w}")
                if c is None or c["licence_limited_rate"] >= 1.0:
                    continue
                L.append(f"{NAMES[s]} & {TIERLAB[t].replace(' (licence tier)', '')} & {e_} & {w} & {fmt(c['mean_vars'], 0)} & "
                         f"{fmt(c['mean_binary'], 0)} & "
                         f"{fmt(c['mean_constraints'], 0) if c['mean_constraints'] else '--'} & {fmt(c['mean_cpu_s'], 2)} & "
                         f"{fmt(c['mean_cpu_per_wall'], 2)} & {c['max_rss_mb']:.0f} & {fmt(c['max_overrun_s'], 2)} \\\\")
        L.append(r"\midrule")
    L[-1] = r"\bottomrule"
    L.append(r"\end{tabular}")
    (tabdir / "tab_s4_resources.tex").write_text("\n".join(L) + "\n")
    # S5 every frozen comparison family (confirmatory and exploratory)
    conf = set(analysis.get("confirmatory_families", []))
    L = [r"\begin{longtable}{llrrrrl}", r"\toprule",
         r"Family & comparison (a vs.\ b) & rel.\ diff.\ \% & W/L/T & Holm $p$ & 95\% CI (\%) & sig. \\", r"\midrule",
         r"\endhead"]
    for fam, comps in analysis["comparisons"].items():
        tag = fam.replace("_", r"\_") + ("" if fam in conf else "$^{e}$")
        for c in comps:
            a, b = c["a"].split("|"), c["b"].split("|")
            lab = (f"{NAMES[a[2]]} {a[3]} vs.\\ {b[3]}" if a[2] == b[2] else f"{NAMES[a[2]]} {a[3]} vs.\\ {NAMES[b[2]]} {b[3]}")
            lo, hi = c["ci95_rel_pct"]
            rd = c["rel_diff_pct"]
            L.append(f"{tag} & {lab} & {'--' if rd is None else f'{rd:+.1f}'.replace('-', '$-$')} & "
                     f"{c['wins_a']}/{c['losses_a']}/{c['ties']} & {c['holm_p']:.3g} & "
                     f"{'--' if lo is None else f'[{lo:+.1f}, {hi:+.1f}]'.replace('-', '$-$')} & "
                     f"{'yes' if c['significant'] else 'no'} \\\\")
            tag = ""
    L += [r"\bottomrule", r"\end{longtable}"]
    (tabdir / "tab_s5_comparisons.tex").write_text("\n".join(L) + "\n")
    # S6 stage attribution (post-hoc descriptive), if available
    attr_p = ROOT / "results/multisolver/analysis/stage_attribution.json"
    if attr_p.exists():
        at = json.loads(attr_p.read_text())["configs"]
        L = [r"\begin{tabular}{llrrrrrrr}", r"\toprule",
             r"Solver & tier & method & PI portfolio & PI pre-global & PI full & engine share & final from rounds & final from global \\",
             r"\midrule"]
        for t in ("S", "M15", "M20"):
            for s in ORDER:
                for m in ("S3", "S4"):
                    c = at.get(f"{exp}|{t}|{s}|{m}|8|1")
                    if c is None:
                        continue
                    src = c["final_incumbent_source"]
                    L.append(f"{NAMES[s]} & {TIERLAB[t].replace(' (licence tier)', '')} & {m} & {fmt(c['pi_portfolio'])} & "
                             f"{fmt(c['pi_pre_global'])} & {fmt(c['pi_full'])} & "
                             f"{100 * (c['engine_share_of_pi_reduction'] or 0):.0f}\\% & "
                             f"{100 * (src.get('round', 0) + src.get('initial', 0)):.0f}\\% & {100 * src.get('global', 0):.0f}\\% \\\\")
            L.append(r"\midrule")
        L[-1] = r"\bottomrule"
        L.append(r"\end{tabular}")
        (tabdir / "tab_s6_attribution.tex").write_text("\n".join(L) + "\n")
    print("wrote tables to", tabdir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="heldout")
    ap.add_argument("--exp", default="AB")
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)
    tabdir = outdir / "tables"; tabdir.mkdir(exist_ok=True)
    streams = {p.stem for p in (ROOT / "results/multisolver/instances" / a.phase).rglob("*.json")}
    recs = load(ROOT / "results/multisolver/runs", streams)
    rows, z = summarize(recs)
    fig_s1(rows, outdir, a.exp)
    fig_s2(recs, z, outdir, a.exp)
    fig_s34(rows, outdir, a.exp)
    fig_s4b(recs, z, outdir, a.exp)
    fig_s5(rows, outdir, a.exp)
    fig_s6(rows, outdir, a.exp)
    tables(json.loads(Path(a.analysis).read_text()), rows, tabdir, a.exp)


if __name__ == "__main__":
    main()
