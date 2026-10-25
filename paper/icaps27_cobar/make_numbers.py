"""Structured claim registry for the COBAR manuscript (Task 11.4).

Every reported result is produced here from a saved analysis file and
written as a named LaTeX macro (numbers.tex), with a registry entry
(claims.json) that records what the number means: source file, setting,
algorithm, comparator, metric, aggregation and statistic. Tables are
generated from the same registry (tables/*.tex). The manuscript uses only
these macros for results; check_claims.py rejects any undefined macro and
any hand-typed result number.

    .venv/bin/python paper/icaps27_cobar/make_numbers.py
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R = ROOT / "results"

REG: dict[str, dict] = {}


def _macro(name: str) -> str:
    assert re.fullmatch(r"[A-Za-z]+", name), name
    return name


def put(name, value, **meta):
    name = _macro(name)
    assert name not in REG, f"duplicate claim {name}"
    REG[name] = {"value": value, **meta}
    return value


def fmt_pct(x, d=1):
    return f"{abs(100 * x):.{d}f}"


def fmt_p(p):
    if p < 1e-3:
        m, e = f"{p:.1e}".split("e")
        return f"{m}\\cdot10^{{{int(e)}}}"
    return f"{p:.3f}" if p < 0.1 else f"{p:.2f}"


def comparison(prefix, src, setting, comp, a, b, metric="pi", table=None):
    """Registers rel_diff (as a positive % reduction or increase), W/L, CI and Holm p."""
    c = comp[metric]
    sign = "-" if c["rel_diff"] < 0 else "+"
    base = dict(source=str(src.relative_to(ROOT)), setting=setting, algorithm=a, comparator=b, metric=metric,
                aggregation="stream mean over steps 1-10 and solver seeds; paired over streams", table=table)
    put(prefix + "Rel", fmt_pct(c["rel_diff"]), statistic=f"relative difference of means ({sign})", sign=sign, **base)
    put(prefix + "Sign", sign, statistic="sign of the relative difference", **base)
    put(prefix + "WL", f"{c['stream_wins']}/{c['stream_losses']}", statistic="streams won/lost by algorithm", **base)
    put(prefix + "CI", f"[{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]".replace("+", "+").replace("-", "-"),
        statistic="stream-clustered bootstrap 95% CI of the mean difference", **base)
    if "sign_p_holm" in c:
        put(prefix + "Holm", fmt_p(c["sign_p_holm"]), statistic="Holm-adjusted exact sign-test p", **base)


ALPH = {str(i): w for i, w in enumerate(["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"])}


def letters(s):
    return "".join(ALPH.get(ch, ch) for ch in s if ch.isalnum())


def main():
    # ---- COBAR confirmatory (frozen) ----
    conf_dir = R / "cobar/confirmatory"
    files = sorted(conf_dir.glob("confirmatory_analysis*.json"))
    conf = {}
    for f in files:  # the full analysis file wins over partial ones
        d = json.loads(f.read_text())
        for k, v in d["settings"].items():
            if k not in conf or f.name == "confirmatory_analysis.json":
                conf[k] = (f, v)
    for setting, (src, s) in conf.items():
        tag = letters(setting.split("_")[0])     # S1 -> SOne
        put(tag + "Units", str(s["n_units"]), source=str(src.relative_to(ROOT)), setting=setting, statistic="number of units")
        put(tag + "Records", f"{s['integrity']['records']:,}".replace(",", "{,}"), source=str(src.relative_to(ROOT)),
            setting=setting, statistic="run records")
        put(tag + "NotValidated", str(s["integrity"]["not_validated"]), source=str(src.relative_to(ROOT)),
            setting=setting, statistic="records not validated")
        for role, mm in s["means"].items():
            put(tag + "Mean" + letters(role.title().replace("_", "")), f"{mm['pi']:.4f}"[1:],
                source=str(src.relative_to(ROOT)), setting=setting, algorithm=role, metric="pi",
                statistic="mean of stream means", table="tab:conf")
            put(tag + "Gap" + letters(role.title().replace("_", "")), f"{mm['gap_B']:.4f}"[1:],
                source=str(src.relative_to(ROOT)), setting=setting, algorithm=role, metric="gap_B",
                statistic="mean of stream means", table="tab:conf")
        for k, comp in s["comparisons"].items():
            a, b = k.split(" vs ")
            pre = tag + letters(a.title().replace("_", "")) + "Vs" + letters(b.title().replace("_", ""))
            comparison(pre, src, setting, comp, a, b, table="tab:conf")
            comparison(pre + "Gap", src, setting, comp, a, b, metric="gap_B", table="tab:conf")
        if "non_inferiority_vs_iaip_sr" in s:
            put(tag + "NonInferior", "yes" if s["non_inferiority_vs_iaip_sr"] else "no",
                source=str(src.relative_to(ROOT)), setting=setting, statistic="non-inferiority vs iaip_sr, 5% margin")
    # ---- development evidence (exploratory) ----
    pilot = R / "cobar/pilot"
    for name, run, pairs in [
        ("PilotOne", "p1_b8", ["A2 vs A1", "A3 vs A1", "A4 vs A1", "A5 vs A4", "A6 vs A4", "A6r vs A1", "A9 vs A0"]),
        ("PilotEight", "p8_b8_seed1", ["C1 vs A1", "C1 vs C3", "C2 vs A1", "C2 vs C3", "C3 vs A1", "A6r vs A1"]),
        ("PilotTen", "p10a_b8_seed2", ["C2 vs A1", "C2 vs C3"]),
    ]:
        src = pilot / run / "analysis.json"
        d = json.loads(src.read_text())
        for k in pairs:
            a_, b_ = k.split(" vs ")
            comparison(name + letters(a_) + "Vs" + letters(b_), src, run, d["comparisons"][k], a_, b_, table="tab:dev")
    reg_src = pilot / "regimes_analysis.json"
    for d in json.loads(reg_src.read_text()):
        if d["campaign"] in ("p2_b2", "p4_w4"):
            tagp = {"p2_b2": "PilotTwo", "p4_w4": "PilotFour"}[d["campaign"]]
            comparison(tagp + "AFourVsAOne", reg_src, d["campaign"], d["comparisons"]["A4 vs A1"], "A4", "A1", table="tab:dev")
            comparison(tagp + "AOneVsAZero", reg_src, d["campaign"], d["comparisons"]["A1 vs A0"], "A1", "A0", table="tab:dev")
    p1 = json.loads((pilot / "p1_b8/analysis.json").read_text())
    cs = p1["certificate_stats"]
    src = pilot / "p1_b8/analysis.json"
    put("PilotCertSteps", str(cs["A2"]["steps"]), source=str(src.relative_to(ROOT)), setting="p1_b8", algorithm="A2", statistic="steps")
    put("PilotCertDecisive", str(cs["A2"]["certified_non_improving"]), source=str(src.relative_to(ROOT)), setting="p1_b8",
        algorithm="A2", statistic="IAIP-SR neighbourhoods certified non-improving")
    put("PilotReleaseNeeded", str(cs["A6"]["release_status"].get("released", 0)), source=str(src.relative_to(ROOT)),
        setting="p1_b8", algorithm="A6", statistic="steps in which arcs were released")
    put("PilotShortStage", str(cs["A6"]["decision_reasons"].get("certified opportunity", 0)), source=str(src.relative_to(ROOT)),
        setting="p1_b8", algorithm="A6", statistic="steps given a short local stage by the certificate rule")
    put("PilotCertMs", f"{cs['A6']['certificate_time_ms_mean']:.1f}", source=str(src.relative_to(ROOT)), setting="p1_b8",
        algorithm="A6", statistic="mean certificate time (ms)")
    put("PilotReleaseMs", f"{cs['A6']['release_time_ms_mean']:.1f}", source=str(src.relative_to(ROOT)), setting="p1_b8",
        algorithm="A6", statistic="mean release time (ms)")
    put("PilotLocalMeanS", f"{cs['A6']['local_time_s_mean']:.2f}", source=str(src.relative_to(ROOT)), setting="p1_b8",
        algorithm="A6", statistic="mean local-stage time (s)")
    # IAIP-SR development replay: certificate vs CP-SAT local status
    diag = R / "research_extension/dev_e5c/cobar_certificate_diagnostic.jsonl"
    rows = [json.loads(l) for l in open(diag)]
    inf = [r for r in rows if r["local_status"] == "INFEASIBLE"]
    put("DiagSteps", str(len(rows)), source=str(diag.relative_to(ROOT)), statistic="replayed IAIP-SR local stages")
    put("DiagDecisive", str(sum(r["decisive"] for r in rows)), source=str(diag.relative_to(ROOT)), statistic="certificate decisive")
    put("DiagInfeasible", str(len(inf)), source=str(diag.relative_to(ROOT)), statistic="CP-SAT INFEASIBLE local stages")
    put("DiagExplained", str(sum(r["decisive"] for r in inf)), source=str(diag.relative_to(ROOT)),
        statistic="INFEASIBLE stages with a decisive certificate")
    import numpy as np
    put("DiagInfeasibleMs", f"{1000 * np.median([r['local_s'] for r in inf]):.0f}", source=str(diag.relative_to(ROOT)),
        statistic="median time of INFEASIBLE local stages (ms)")
    put("DiagOptimalS", f"{np.median([r['local_s'] for r in rows if r['local_status'] == 'OPTIMAL']):.2f}",
        source=str(diag.relative_to(ROOT)), statistic="median time of OPTIMAL local stages (s)")
    # exact-oracle campaign
    oc_src = R / "cobar/oracle_campaign.json"
    oc = json.loads(oc_src.read_text())
    for k, nm in (("enumeration", "Enum"), ("cpsat", "Cpsat"), ("global", "Global")):
        put("Oracle" + nm + "Cases", f"{oc[k]['cases']:,}".replace(",", "{,}"), source=str(oc_src.relative_to(ROOT)), statistic=f"{k} oracle cases")
        put("Oracle" + nm + "Decisive", str(oc[k]["decisive"]), source=str(oc_src.relative_to(ROOT)), statistic=f"{k} decisive certificates")
        put("Oracle" + nm + "Violations", str(oc[k]["violations"]), source=str(oc_src.relative_to(ROOT)), statistic=f"{k} violations")
    put("OracleCutCases", f"{oc['cut']['cases']:,}".replace(",", "{,}"), source=str(oc_src.relative_to(ROOT)), statistic="decisive cases for the cut check")
    put("OracleCutMisses", str(oc["cut"]["miss_chain"] + oc["cut"]["not_minimum"]), source=str(oc_src.relative_to(ROOT)),
        statistic="cuts that miss a chain or are not minimum")
    # candidate behaviour in S1 (raw runs)
    cand = json.loads((R / "cobar/confirmatory/FROZEN_CONFIG.json").read_text())["roles"]["candidate"]
    runs = [json.loads(l) for f in sorted((R / "cobar/confirmatory/S1_primary/runs").glob("*.jsonl")) for l in open(f)]
    c = [r for r in runs if r["method"] == cand and r["step"] >= 1]
    src = "results/cobar/confirmatory/S1_primary/runs"
    put("SOneRoundsMean", f"{np.mean([len(r['meta'].get('rounds', [])) for r in c]):.1f}", source=src, setting="S1_primary",
        algorithm="candidate", statistic="extra rounds per instance (mean)")
    put("SOneRoundsImproving", f"{np.mean([sum(x['improved'] for x in r['meta'].get('rounds', [])) for r in c]):.1f}",
        source=src, setting="S1_primary", algorithm="candidate", statistic="improving extra rounds per instance (mean)")
    put("SOneLocalS", f"{np.mean([r['meta']['stage_s'].get('local_s', 0) for r in c]):.2f}", source=src, setting="S1_primary",
        algorithm="candidate", statistic="mean local-window time (s)")
    put("SOneSeedsMedian", f"{np.median([sd['n_seeds'] for r in c for sd in r['meta'].get('rounds_seed', [])]):.0f}",
        source=src, setting="S1_primary", algorithm="candidate", statistic="median seed operations per round")
    write_tables(conf)
    (HERE / "numbers.tex").write_text(
        "% generated by make_numbers.py -- do not edit\n" +
        "".join(f"\\newcommand{{\\{k}}}{{{v['value']}}}\n" for k, v in sorted(REG.items())))
    (HERE / "claims.json").write_text(json.dumps(REG, indent=1))
    print(len(REG), "claims written")


SETTING_LABEL = {"S1_primary": "8\\,s, 1 worker", "S2_short": "2\\,s, 1 worker", "S3_workers4": "8\\,s, 4 workers",
                 "S4_arrival": "arrivals only", "S5_outage": "outages only", "S6_b30": "30\\,s, 1 worker",
                 "S7_benchmarks": "published bases"}


def write_tables(conf):
    """Tables use registry macros only, so every cell is traceable (claim_map.md)."""
    (HERE / "tables").mkdir(exist_ok=True)
    rows = []
    for setting in ["S1_primary", "S2_short", "S3_workers4", "S4_arrival", "S5_outage", "S6_b30", "S7_benchmarks"]:
        if setting not in conf:
            continue
        t = letters(setting.split("_")[0])
        rows.append(f"{SETTING_LABEL[setting]} & \\{t}Units & \\{t}MeanCandidate & \\{t}MeanIaipSr & \\{t}MeanPortfolioHinted & "
                    f"$\\{t}CandidateVsIaipSrSign\\{t}CandidateVsIaipSrRel$\\% \\{t}CandidateVsIaipSrWL & "
                    f"$\\{t}CandidateVsPortfolioHintedSign\\{t}CandidateVsPortfolioHintedRel$\\% \\{t}CandidateVsPortfolioHintedWL \\\\")
    (HERE / "tables/conf.tex").write_text("% generated by make_numbers.py\n" + "\n".join(rows) + "\n")
    dev = [
        ("certificate skip", "A2 vs A1", "PilotOneATwoVsAOne"),
        ("certificate-guided release", "A3 vs A1", "PilotOneAThreeVsAOne"),
        ("certificate-aware allocation", "A5 vs A4", "PilotOneAFiveVsAFour"),
        ("full single-round certificate method", "A6 vs A4", "PilotOneASixVsAFour"),
        ("budget-only skip rule, 2\\,s", "A4 vs A1", "PilotTwoAFourVsAOne"),
        ("budget-only skip rule, 4 workers", "A4 vs A1", "PilotFourAFourVsAOne"),
        ("native interleaved LNS", "A9 vs A0", "PilotOneANineVsAZero"),
        ("rounds, min-cut seeds (seed 1)", "C1 vs A1", "PilotEightCOneVsAOne"),
        ("min-cut vs random seeds (seed 1)", "C1 vs C3", "PilotEightCOneVsCThree"),
        ("rounds, random seeds (seed 1)", "C3 vs A1", "PilotEightCThreeVsAOne"),
        ("rounds, critical-region seeds (seed 1)", "C2 vs A1", "PilotEightCTwoVsAOne"),
        ("rounds, critical-region seeds (seed 2)", "C2 vs A1", "PilotTenCTwoVsAOne"),
        ("critical-region vs random seeds (seed 2)", "C2 vs C3", "PilotTenCTwoVsCThree"),
    ]
    (HERE / "tables/dev.tex").write_text("% generated by make_numbers.py\n" + "\n".join(
        f"{lab} & {pair} & $\\{m}Sign\\{m}Rel$\\% & \\{m}WL & $\\{m}CI$ \\\\" for lab, pair, m in dev) + "\n")


if __name__ == "__main__":
    main()
