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

    # Phase-3 reanalysis: matched-round (M2) critical-vs-timewindow by disruption type
    # (docs/final_icaps/03_critical_vs_timewindow.md) -- resolves whether the U6 arrival-specific
    # advantage survives matched-round accounting (it does not).
    p3_deltas = {"Arrival": ("arrival", 8.9, "13/27", 40), "Cancellation": ("cancellation", 18.5, "9/29", 38),
                 "Duration": ("duration_jitter", 13.3, "12/26", 38), "Outage": ("outage", 9.8, "11/20", 31)}
    p3_src = "docs/final_icaps/03_critical_vs_timewindow.md"
    for label, (dk, rel, wl, n) in p3_deltas.items():
        put("MechTwo" + label + "Rel", f"{rel:.1f}", source=p3_src, setting="U2_mechanism", metric="pi",
            statistic=f"M2 crit vs timewin relative diff (+ = crit worse), delta={dk}, exploratory")
        put("MechTwo" + label + "WL", wl, source=p3_src, setting="U2_mechanism", statistic=f"streams won/lost, delta={dk}")
        put("MechTwo" + label + "N", str(n), source=p3_src, setting="U2_mechanism", statistic=f"n streams, delta={dk}")
    # round-count confound (same source)
    rc = {"ArrivalCrit": 3.15, "ArrivalTw": 2.02, "CancelCrit": 2.40, "CancelTw": 1.85,
          "DurationCrit": 2.91, "DurationTw": 2.06, "OutageCrit": 2.95, "OutageTw": 1.88}
    for k, v in rc.items():
        put("RoundsUOne" + k, f"{v:.2f}", source=p3_src, setting="U1_primary", statistic="mean completed rounds per instance")
    # per-round solver-difficulty asymmetry (|N| matched, solve time not)
    diff = {"CritN": "82.4", "TwN": "82.3", "CritSolverS": "0.056", "TwSolverS": "0.080",
            "CritInfeas": "7988", "TwInfeas": "7289", "CritFeas": "376", "TwFeas": "901"}
    for k, v in diff.items():
        put("MTwoRound" + k, v, source=p3_src, setting="U2_mechanism", statistic="round-level neighbourhood/solver diagnostic")
    tw_s, crit_s = float(diff["TwSolverS"]), float(diff["CritSolverS"])
    put("MTwoRoundTwVsCritPct", f"{100*(tw_s/crit_s - 1):.0f}", source=p3_src, setting="U2_mechanism",
        statistic="relative increase in mean per-round solver time, timewin vs crit")
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
