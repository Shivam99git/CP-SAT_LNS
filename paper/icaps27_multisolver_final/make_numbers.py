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
    # third, code-disjoint recomputation of the CP-SAT confirmatory study (this revision)
    rp_src = R / "multisolver/audit/cpsat_reproduction.json"
    if rp_src.exists():
        rp = json.loads(rp_src.read_text())
        agr = [a for s in rp["settings"].values() for a in s["agreement_with_archived"]]
        meta = dict(source=str(rp_src.relative_to(ROOT)), setting="all confirmatory settings")
        put("ReproRecords", f"{rp['record_counts']['top_level_run_records']:,}".replace(",", "{,}"),
            statistic="top-level run records recomputed from raw files", **meta)
        put("ReproComparisons", str(len(agr)), statistic="confirmatory comparisons recomputed", **meta)
        m, e = f"{max(a['rel_diff_abs_err_pct'] for a in agr):.1e}".split("e")
        put("ReproMaxErr", f"{m}\\times10^{{{int(e)}}}", statistic="max |rel-diff error| vs archived (pct points)", **meta)
        put("ReproWLMismatch", str(sum(1 for a in agr if not a.get("wl_match", True))),
            statistic="win/loss mismatches", **meta)
    # ---- multisolver held-out campaign (scripts/multisolver/analyze_results.py) ----
    ms_src = R / "multisolver/analysis/heldout.json"
    if ms_src.exists():
        ms = json.loads(ms_src.read_text())
        srcs = str(ms_src.relative_to(ROOT))
        cap = lambda w: w[0].upper() + w[1:]
        for fam, comps in ms["comparisons"].items():
            for c in comps:
                ea, ta, sa, ma, ba, wa = c["a"].split("|")
                eb, tb, sb, mb, bb, wb = c["b"].split("|")
                pre = "MS" + letters(fam.replace("_", "")) + cap(sa) + letters(ma) + "Vs" + (cap(sb) if sb != sa else "") + letters(mb)
                base = dict(source=srcs, setting=f"{ea}|{ta}|{ba}s|{wa}w", algorithm=f"{sa}:{ma}",
                            comparator=f"{sb}:{mb}", metric="pi (bounded gap)")
                put(pre + "Rel", f"{abs(c['rel_diff_pct']):.1f}", statistic="relative difference (%)",
                    sign="-" if c["rel_diff_pct"] < 0 else "+", **base)
                put(pre + "Sign", "-" if c["rel_diff_pct"] < 0 else "+", statistic="sign", **base)
                put(pre + "WL", f"{c['wins_a']}/{c['losses_a']}", statistic="streams won/lost", **base)
                put(pre + "Holm", fmt_p(c["holm_p"]), statistic="Holm-adjusted sign-test p", **base)
                lo, hi = c["ci95_rel_pct"]
                put(pre + "CIRel", f"[{lo:+.1f}, {hi:+.1f}]" if lo is not None else "--",
                    statistic="95% stream-bootstrap CI of rel. diff (%)", **base)
                put(pre + "Sig", "yes" if c["significant"] else "no", statistic="Holm p<0.05 and CI excludes 0", **base)
        for k, c in ms["configs"].items():
            e, t, sv, m, b, w = k.split("|")
            pre = "MSCfg" + letters(e) + letters(t) + cap(sv) + letters(m) + letters(b) + "s" + letters(w) + "w"
            base = dict(source=srcs, setting=f"{e}|{t}|{b}s|{w}w", algorithm=f"{sv}:{m}")
            if c["mean_pi"] is not None:
                put(pre + "PI", f"{c['mean_pi']:.4f}", statistic="mean PI (bounded gap), stream units", **base)
            put(pre + "Feas", f"{100 * c['feasible_rate']:.0f}", statistic="% runs with a validated incumbent by B", **base)
            put(pre + "Opt", f"{100 * c['proven_optimal_rate']:.0f}", statistic="% runs proven optimal by B", **base)
            put(pre + "N", str(c["n_streams"]), statistic="streams", **base)
            if c.get("mean_vars"):
                put(pre + "Vars", f"{c['mean_vars']:,.0f}".replace(",", "{,}"), statistic="mean model variables", **base)
                put(pre + "Cons", f"{(c['mean_constraints'] or 0):,.0f}".replace(",", "{,}"),
                    statistic="mean model constraints (0 = not reported by the API)", **base)
            put(pre + "Runs", str(c["n_runs"]), statistic="runs", **base)
        for t, tag in (("M15", "MOneFive"), ("M20", "MTwoZero")):
            mi, cp = ms["configs"][f"AB|{t}|scip|S0|8|1"], ms["configs"][f"AB|{t}|cpsat|S0|8|1"]
            put(f"MSMilpVsCpsatVars{tag}", f"{mi['mean_vars'] / cp['mean_vars']:.1f}", source=srcs, setting=f"AB|{t}|8s|1w",
                statistic="ratio of mean MILP variables (identical for all six MIP engines) to CP-SAT interval-model variables")
            put(f"MSMilpBuildS{tag}", f"{mi['mean_build_s']:.2f}", source=srcs, setting=f"AB|{t}|8s|1w",
                statistic="mean MILP build + API translation seconds (SCIP)")
            put(f"MSCpsatBuildS{tag}", f"{cp['mean_build_s']:.3f}", source=srcs, setting=f"AB|{t}|8s|1w",
                statistic="mean CP-SAT model build seconds")
        put("MSRecords", f"{ms['n_records']:,}".replace(",", "{,}"), source=srcs, statistic="held-out multisolver records")
        put("MSInstances", str(ms["n_instances_with_zstar"]), source=srcs, statistic="physical instances")
        ct = ms["contention"]
        put("MSLoadAvg", f"{ct['median_loadavg_1m']:.0f}", source=srcs, statistic="median 1-min load average over runs")
        put("MSCpuWall", f"{ct['median_cpu_per_wall_1w']:.2f}", source=srcs, statistic="median CPU/wall, 1-worker runs")
        put("MSCpuWallLowPct", f"{100 * ct['share_1w_rows_below_0_8']:.0f}", source=srcs,
            statistic="% of 1-worker runs with CPU/wall < 0.8")
        put("MSLicenceRefusals", str(sum(v for k, v in ms["status_counts"].items()
                                         if k.split("|")[1] in ("M15", "M20") and k.split("|")[2] in ("cpoptimizer", "gurobi", "cplex"))),
            source=srcs, statistic="licence-refused paper-scale attempts (CP Optimizer, Gurobi, CPLEX)")
        n_conf = sum(len(ms["comparisons"][f]) for f in ms["confirmatory_families"] if f in ms["comparisons"])
        n_expl = sum(len(ms["comparisons"][f]) for f in ms["exploratory_families"] if f in ms["comparisons"])
        put("MSNConfirmatory", str(n_conf), source=srcs, statistic="confirmatory comparisons in frozen families")
        put("MSNExploratory", str(n_expl), source=srcs, statistic="exploratory comparisons in frozen families")
        # per tier: engines whose S4 beats S3 in EVERY stream (direction count; descriptive for 5-stream tiers)
        for t in ("S", "MOneFive", "MTwoZero"):
            raw = {"S": "S", "MOneFive": "M15", "MTwoZero": "M20"}[t]
            for x, y, tag in (("S4", "S3", "SFourVsSThree"), ("S2", "S0", "STwoVsSZero"), ("S3", "S2", "SThreeVsSTwo")):
                cs = [c for f, L in ms["comparisons"].items() if f.startswith(f"B_{raw}_") for c in L
                      if c["a"].split("|")[3] == x and c["b"].split("|")[3] == y]
                if not cs:
                    continue
                put(f"MSB{t}{tag}Engines", str(len(cs)), source=srcs, statistic=f"engines with a {x} vs {y} comparison, tier {raw}")
                put(f"MSB{t}{tag}AllStreams", str(sum(c["wins_a"] == c["n_streams"] for c in cs)), source=srcs,
                    statistic=f"engines where {x} has lower PI than {y} in every stream, tier {raw}")
                put(f"MSB{t}{tag}Sig", str(sum(c["significant"] for c in cs)), source=srcs,
                    statistic=f"engines with a significant {x} vs {y} improvement or deterioration, tier {raw}")
        # pre-declared contention sensitivity: significance decisions that change
        sens_src = R / "multisolver/analysis/heldout_cpu08.json"
        if sens_src.exists():
            sens = json.loads(sens_src.read_text())
            k = lambda c: (c["a"], c["b"])
            base_sig = {k(c): c["significant"] for L in ms["comparisons"].values() for c in L}
            s_sig = {k(c): c["significant"] for L in sens["comparisons"].values() for c in L}
            common = set(base_sig) & set(s_sig)
            put("MSSensTotal", str(len(common)), source=str(sens_src.relative_to(ROOT)),
                statistic="comparisons present in both the full and the CPU/wall>=0.8 analysis")
            put("MSSensChanged", str(sum(base_sig[c] != s_sig[c] for c in common)), source=str(sens_src.relative_to(ROOT)),
                statistic="significance decisions that differ under the CPU/wall>=0.8 filter")
            brel = {k(c): c["rel_diff_pct"] for L in ms["comparisons"].values() for c in L}
            srel = {k(c): (c["rel_diff_pct"], c["significant"]) for L in sens["comparisons"].values() for c in L}
            flips = [c for c in common if (base_sig[c] or srel[c][1]) and brel[c] and srel[c][0]
                     and (brel[c] > 0) != (srel[c][0] > 0)]
            put("MSSensSigFlips", str(len(flips)), source=str(sens_src.relative_to(ROOT)),
                statistic="comparisons significant in either analysis whose sign differs between them")
    ph_src = R / "multisolver/analysis/posthoc.json"
    if ph_src.exists():
        ph = json.loads(ph_src.read_text())
        cap = lambda w: w[0].upper() + w[1:]
        for c in ph["comparisons"]:
            e, t, s, m, b, w = c["a"].split("|")
            pre = "MSPost" + letters(t) + cap(s) + "VsCpsat"
            meta = dict(source=str(ph_src.relative_to(ROOT)), setting=f"{e}|{t}|{b}s|{w}w", algorithm=f"{s}:{m}",
                        comparator="cpsat:S4", metric="pi (bounded gap)")
            put(pre + "Rel", f"{abs(c['rel_diff_pct']):.1f}", statistic="relative difference (%), post-hoc exploratory",
                sign="-" if c["rel_diff_pct"] < 0 else "+", **meta)
            put(pre + "WL", f"{c['wins_a']}/{c['losses_a']}", statistic="streams won/lost, post-hoc exploratory", **meta)
            lo, hi = c["ci95_rel_pct"]
            put(pre + "CIRel", f"[{lo:+.1f}, {hi:+.1f}]", statistic="95% stream-bootstrap CI (%), post-hoc exploratory", **meta)
    val_src = R / "multisolver/validation_report.json"
    if val_src.exists():
        v = json.loads(val_src.read_text())
        ho = [c for e, c in v["by_experiment"].items() if e in ("AB", "R2", "R30", "W4")]
        n_ok, n_rev = sum(c.get("OK", 0) for c in ho), sum(c.get("schedule_revalidated", 0) for c in ho)
        assert n_ok == n_rev, "a held-out OK record lacks a stored schedule"
        put("MSValidated", f"{n_rev:,}".replace(",", "{,}"),
            source=str(val_src.relative_to(ROOT)), statistic="held-out final schedules re-validated post hoc (all OK records)")
        put("MSViolations", str(v["n_violations"]), source=str(val_src.relative_to(ROOT)), statistic="validation violations")
    at_src = R / "multisolver/analysis/stage_attribution.json"
    if at_src.exists():
        at = json.loads(at_src.read_text())["configs"]
        cap = lambda w: w[0].upper() + w[1:]
        for key, c in at.items():
            e, t, sv, m, b, w = key.split("|")
            if e != "AB" or c["pi_portfolio"] <= 0:
                continue
            pre = "MSAttr" + letters(t) + cap(sv) + letters(m)
            meta = dict(source=str(at_src.relative_to(ROOT)), setting=f"{e}|{t}|{b}s|{w}w", algorithm=f"{sv}:{m}",
                        metric="pi (bounded gap)")
            put(pre + "Rounds", f"{100 * (c['pi_portfolio'] - c['pi_pre_global']) / c['pi_portfolio']:.0f}",
                statistic="% of portfolio-only PI removed by initial stage + rounds (post-hoc descriptive)", **meta)
            put(pre + "Global", f"{100 * (c['pi_pre_global'] - c['pi_full']) / c['pi_portfolio']:.0f}",
                statistic="% of portfolio-only PI removed by the global stage (post-hoc descriptive)", **meta)
        # largest global-stage share among non-CP-SAT engines at paper scale (S3 and S4)
        oth = [(c["pi_pre_global"] - c["pi_full"]) / c["pi_portfolio"] for key, c in at.items()
               if key.split("|")[0] == "AB" and key.split("|")[1] in ("M15", "M20") and key.split("|")[2] != "cpsat"
               and c["pi_portfolio"] > 0]
        put("MSAttrMaxGlobalOtherM", f"{100 * max(oth):.0f}", source=str(at_src.relative_to(ROOT)),
            statistic="max % of portfolio-only PI removed by the global stage, non-CP-SAT engines, 15x15/20x20")
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
    # typographic minus: a bare "-" before a digit prints as a hyphen in text mode; \ensuremath{-}
    # is correct in text (CIs such as [-5.6, +19.7]) and inside math ($p=1.5\cdot10^{-11}$) alike
    tex_val = lambda v: re.sub(r"(?<![\w])-(?=\d)", r"\\ensuremath{-}", str(v))
    (HERE / "numbers.tex").write_text(
        "% generated by make_numbers.py -- do not edit\n" +
        "".join(f"\\newcommand{{\\{k}}}{{{tex_val(v['value'])}}}\n" for k, v in sorted(REG.items())))
    (HERE / "claims.json").write_text(json.dumps(REG, indent=1))
    print(len(REG), "claims written")


if __name__ == "__main__":
    main()
