"""Claim registry for the unified manuscript (Task 14). Every reported number
is generated here from a saved analysis file and written as a named LaTeX
macro, with a registry entry recording its source, setting, algorithm,
comparator, metric and statistic. check_claims.py verifies the manuscript
uses only these macros for results.

    .venv/bin/python paper/icaps27_unified/make_numbers.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R = ROOT / "results"
HERE_DIR = Path(__file__).resolve().parent
REG: dict[str, dict] = {}


def put(name, value, **meta):
    assert re.fullmatch(r"[A-Za-z]+", name), name
    assert name not in REG, f"duplicate {name}"
    REG[name] = {"value": value, **meta}


def pct(x, d=1):
    return f"{abs(100 * x):.{d}f}"


def fmt_p(p):
    if p < 1e-3:
        m, e = f"{p:.1e}".split("e")
        return f"{m}\\cdot10^{{{int(e)}}}"
    return f"{p:.3f}" if p < 0.1 else f"{p:.2f}"


def wl(c):
    return f"{c['stream_wins']}/{c['stream_losses']}"


def ci(c):
    return f"[{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]"


ALPH = {str(i): w for i, w in enumerate(["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"])}

BUDGET_S = {"U1_primary": 8.0, "U2_mechanism": 8.0, "U3_workers4": 8.0, "U4_b2": 2.0, "U5_b30": 30.0,
            "U6_arrival": 8.0, "U7_outage": 8.0, "U8_high": 8.0, "U9_benchmarks": 8.0}


def letters(s):
    return "".join(ALPH.get(ch, ch) for ch in s if ch.isalnum())


def comparison(prefix, src, setting, comp, metric="pi"):
    c = comp[metric]
    sign = "-" if c["rel_diff"] < 0 else "+"
    base = dict(source=str(src.relative_to(ROOT)), setting=setting, metric=metric)
    put(prefix + "Rel", pct(c["rel_diff"]), statistic="relative difference (%)", sign=sign, **base)
    put(prefix + "Sign", sign, statistic="sign", **base)
    put(prefix + "WL", wl(c), statistic="streams won/lost", **base)
    put(prefix + "CI", ci(c), statistic="95% bootstrap CI of mean difference", **base)
    lo, hi = 100 * c["ci95"][0] / c["mean_b"], 100 * c["ci95"][1] / c["mean_b"]
    put(prefix + "CIRel", f"[{lo:+.1f}, {hi:+.1f}]", statistic="95% bootstrap CI, relative to comparator mean (%)", **base)
    if "sign_p_holm" in c:
        put(prefix + "Holm", fmt_p(c["sign_p_holm"]), statistic="Holm-adjusted sign-test p", **base)


def main():
    conf = json.loads((R / "unified_icaps/confirmatory/confirmatory_analysis.json").read_text())
    src = R / "unified_icaps/confirmatory/confirmatory_analysis.json"

    for sname, s in conf["settings"].items():
        tag = letters(sname.split("_")[0])
        put(tag + "N", str(s["n_units"]), source=str(src.relative_to(ROOT)), setting=sname, statistic="units")
        put(tag + "Records", f"{s['integrity']['records']:,}".replace(",", "{,}"), source=str(src.relative_to(ROOT)),
            setting=sname, statistic="records")
        for role, mm in s["means"].items():
            put(tag + "Mean" + letters(role), f"{mm['pi']:.4f}"[1:], source=str(src.relative_to(ROOT)),
                setting=sname, statistic="mean PI")
            if "gap_B" in mm:
                put(tag + "GapB" + letters(role), f"{100*mm['gap_B']:.1f}", source=str(src.relative_to(ROOT)),
                    setting=sname, statistic="mean final gap to z* (%)")
            if "t_first" in mm and sname in BUDGET_S:
                ms = mm["t_first"] * BUDGET_S[sname] * 1000
                put(tag + "TfirstMs" + letters(role), f"{ms:.0f}", source=str(src.relative_to(ROOT)),
                    setting=sname, statistic="mean time to first incumbent (ms)")
        for k, comp in s["comparisons"].items():
            a, b = k.split(" vs ")
            pre = tag + letters(a) + "Vs" + letters(b)
            comparison(pre, src, sname, comp)

    crit = conf["criteria"]
    for k, v in crit.items():
        put("Crit" + letters(k.split("_")[0]), str(v), source=str(src.relative_to(ROOT)), statistic=k)
    put("Classification", conf["classification"], source=str(src.relative_to(ROOT)), statistic="overall verdict")

    # development pilot numbers (exploratory)
    d1 = json.loads((R / "unified_icaps/dev/d1_b8/analysis.json").read_text())
    src_d1 = R / "unified_icaps/dev/d1_b8/analysis.json"
    for k in ("crit_expand vs B0", "crit_expand vs time_window", "crit_expand vs B5"):
        a, b = k.split(" vs ")
        comparison("DevOne" + letters(a) + "Vs" + letters(b), src_d1, "d1_b8", d1["comparisons"][k])

    # round-diagnostic rates (from the unified analyze_unified round diagnostics on U1)
    rd_src = R / "unified_icaps/confirmatory/U1_rounds_diagnostic.json"
    if rd_src.exists():
        rd = json.loads(rd_src.read_text())["round_diagnostics"]
        put("RoundCritRate", f"{100*rd['crit_expand']['round_improvement_rate']:.0f}", source=str(rd_src.relative_to(ROOT)), statistic="crit round improvement rate %")
        put("RoundTimewinRate", f"{100*rd['time_window']['round_improvement_rate']:.0f}", source=str(rd_src.relative_to(ROOT)), statistic="timewin round improvement rate %")

    # oracle / intermediate counts reused from COBAR (shared infrastructure)
    oc_src = R / "cobar/oracle_campaign.json"
    if oc_src.exists():
        oc = json.loads(oc_src.read_text())
        put("OracleEnumCases", f"{oc['enumeration']['cases']:,}".replace(",", "{,}"), source=str(oc_src.relative_to(ROOT)), statistic="enum cases")
        put("OracleCpsatCases", f"{oc['cpsat']['cases']:,}".replace(",", "{,}"), source=str(oc_src.relative_to(ROOT)), statistic="cpsat cases")

    # Mechanism quantities, RECOMPUTED from raw U1/U2 records by
    # scripts/multisolver/reproduce_mechanism.py (they were previously transcribed
    # from docs/final_icaps/03_critical_vs_timewindow.md; values agree exactly).
    mk_src = R / "multisolver/audit/mechanism_reproduction.json"
    mk = json.loads(mk_src.read_text())
    srcm = str(mk_src.relative_to(ROOT))
    for label, dk in (("Arrival", "arrival"), ("Cancellation", "cancellation"), ("Duration", "duration_jitter"),
                      ("Outage", "outage")):
        c = mk["M2_crit_vs_timewin_by_delta"][dk]
        put("MechTwo" + label + "Rel", f"{c['rel_diff_pct']:.1f}", source=srcm, setting="U2_mechanism", metric="pi",
            statistic=f"M2 crit vs timewin rel diff (+ = crit worse), delta={dk}, exploratory")
        put("MechTwo" + label + "WL", f"{c['crit_wins']}/{c['crit_losses']}", source=srcm, setting="U2_mechanism",
            statistic=f"streams won/lost by crit, delta={dk}")
        put("MechTwo" + label + "N", str(c["n_streams"]), source=srcm, setting="U2_mechanism", statistic=f"n streams, delta={dk}")
        put("MechTwo" + label + "CI", f"[{c['ci95_rel_pct'][0]:+.1f}, {c['ci95_rel_pct'][1]:+.1f}]", source=srcm,
            setting="U2_mechanism", statistic=f"bootstrap 95% CI of rel diff (%), delta={dk}, exploratory")
        put("MechTwo" + label + "P", fmt_p(c["sign_p_uncorrected"]), source=srcm, setting="U2_mechanism",
            statistic=f"uncorrected sign-test p, delta={dk}, exploratory")
    m1, m2 = mk["M1_round_stats_U1"], mk["M2_round_stats_U2"]
    for tag, role in (("Crit", "B2_crit"), ("Tw", "B3_timewin")):
        put(f"RoundsMOne{tag}", f"{m1[role]['mean_completed_rounds']:.2f}", source=srcm, setting="U1_primary",
            statistic="mean completed restricted rounds per instance (M1)")
        put(f"RestrSMOne{tag}", f"{m1[role]['mean_restricted_solver_s_per_instance']:.2f}", source=srcm,
            setting="U1_primary", statistic="restricted-solver seconds per instance (M1)")
        put(f"ImprRateMOne{tag}", f"{100 * m1[role]['round_improvement_rate']:.0f}", source=srcm, setting="U1_primary",
            statistic="round improvement rate % (M1)")
    for tag, role in (("Crit", "M2_crit"), ("Tw", "M2_timewin")):
        put(f"RoundsMTwo{tag}", f"{m2[role]['mean_completed_rounds']:.2f}", source=srcm, setting="U2_mechanism",
            statistic="mean completed restricted rounds per instance (M2)")
        put(f"RestrSMTwo{tag}", f"{m2[role]['mean_restricted_solver_s_per_instance']:.2f}", source=srcm,
            setting="U2_mechanism", statistic="restricted-solver seconds per instance (M2)")
        put(f"GlobalSMTwo{tag}", f"{m2[role]['mean_global_time_s']:.2f}", source=srcm, setting="U2_mechanism",
            statistic="global-continuation seconds per instance (M2)")
    put("RestrMTwoTwVsCritPct", f"{100 * (m2['M2_timewin']['mean_restricted_solver_s_per_instance'] / m2['M2_crit']['mean_restricted_solver_s_per_instance'] - 1):.0f}",
        source=srcm, setting="U2_mechanism", statistic="extra restricted-solver time, timewin vs crit (M2), %")
    for tag, role in (("Crit", "M2_crit"), ("Tw", "M2_timewin")):
        s_ = m2[role]
        put(f"MTwoRound{tag}N", f"{s_['mean_released_ops']:.1f}", source=srcm, setting="U2_mechanism",
            statistic="mean released operations per round (M2)")
        put(f"MTwoRound{tag}SolverS", f"{s_['mean_round_solver_s']:.3f}", source=srcm, setting="U2_mechanism",
            statistic="mean solver seconds per round (M2)")
        put(f"MTwoRound{tag}Infeas", str(s_["round_status"].get("INFEASIBLE", 0)), source=srcm, setting="U2_mechanism",
            statistic="rounds proved to contain no strictly better schedule (INFEASIBLE under C<=U-1)")
        put(f"MTwoRound{tag}Feas", str(s_["round_status"].get("FEASIBLE", 0)), source=srcm, setting="U2_mechanism",
            statistic="rounds stopped by the 0.4 s cap with an improvement but no proof")
        put(f"MTwoRound{tag}Unknown", str(s_["round_status"].get("UNKNOWN", 0)), source=srcm, setting="U2_mechanism",
            statistic="rounds stopped by the cap with neither improvement nor proof")
    put("MTwoRoundTwVsCritPct", f"{100 * (m2['M2_timewin']['mean_round_solver_s'] / m2['M2_crit']['mean_round_solver_s'] - 1):.0f}",
        source=srcm, setting="U2_mechanism", statistic="relative increase in mean per-round solver time, timewin vs crit")
    # restricted-solve status semantics over the whole confirmatory campaign (strict-improvement cutoff)
    st_src = R / "multisolver/audit/restricted_status_counts.json"
    if st_src.exists():
        st = json.loads(st_src.read_text())
        for k, v in st.items():
            put("RestrStatus" + k.capitalize(), f"{v:,}".replace(",", "{,}"), source=str(st_src.relative_to(ROOT)),
                statistic=f"restricted solves with status {k}, all confirmatory settings")
    # Figure 2 (real archived trajectories) numbers
    fig2_src = HERE_DIR / "figures/figure2_numbers.json"
    if fig2_src.exists():
        fig2 = json.loads(fig2_src.read_text())
        for size, tag in (("15x15", "OneFive"), ("20x20", "TwoZero")):
            for label, tag2 in (("SR+Crit", "Crit"), ("SR+TimeWin", "Tw"), ("SR (IAIP-SR)", "Sr")):
                key = f"{size}|{label}"
                if key in fig2:
                    put(f"FigTwo{tag}{tag2}At", f"{fig2[key]['median_gap_pct']['8.0']:.1f}",
                        source=str(fig2_src.relative_to(ROOT)), setting="U1_primary (figure)",
                        statistic=f"median gap % at t=8s, {size}, {label}")
    (HERE / "numbers.tex").write_text(
        "% generated by make_numbers.py -- do not edit\n" +
        "".join(f"\\newcommand{{\\{k}}}{{{v['value']}}}\n" for k, v in sorted(REG.items())))
    (HERE / "claims.json").write_text(json.dumps(REG, indent=1))
    print(len(REG), "claims written")


if __name__ == "__main__":
    main()
