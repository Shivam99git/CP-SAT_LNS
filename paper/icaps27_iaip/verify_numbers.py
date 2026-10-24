"""Recompute the numbers stated in manuscript.tex from the saved analysis
outputs and check that each formatted value occurs in the .tex source.

Sources (all produced by the project's analysis scripts from raw run files):
  results/research_extension/gate1_historical_reuse/analysis.json
  results/research_extension/confirmatory/confirmatory_analysis.json
  results/research_extension/confirmatory/supplementary_analysis.json
  results/research_extension/e6_analysis.json
  results/research_extension/e6e_lns/analysis.json
  paper/icaps27_iaip/figure_numbers.json

    .venv/bin/python paper/icaps27_iaip/verify_numbers.py
Exit status 1 if any expected string is missing. A substring match shows that
the value occurs in the text, not that it stands next to the right label;
short strings such as W/L counts can match elsewhere.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "results/research_extension"
tex = (Path(__file__).with_name("manuscript.tex")).read_text()
g1 = json.loads((R / "gate1_historical_reuse/analysis.json").read_text())
cf = json.loads((R / "confirmatory/confirmatory_analysis.json").read_text())
sup = json.loads((R / "confirmatory/supplementary_analysis.json").read_text())
e6 = {r["campaign"]: r for r in json.loads((R / "e6_analysis.json").read_text())}
e6e = json.loads((R / "e6e_lns/analysis.json").read_text())[0]
fig = json.loads((Path(__file__).with_name("figure_numbers.json")).read_text())

checks = []  # (label, expected substring)


def pct(x, d=1):
    return f"{abs(100 * x):.{d}f}"


def pi3(x):  # .0339 style
    return f"{x:.4f}"[1:]


def wl(c):
    return f"{c['stream_wins']}/{c['stream_losses']}"


# ---- Stage 1 (Table 1 and text) ----
for P, col in (("protocol_B", "B"), ("protocol_A", "A")):
    for k, c in g1[P]["pi"]["comparisons"].items():
        checks.append((f"G1 {col} {k} rel", f"{pct(c['rel_diff'])}\\%"))
        checks.append((f"G1 {col} {k} W/L", wl(c)))
mB = g1["protocol_B"]["pi"]["means"]
for m in ("floor", "mwkr_cold", "spt_cold", "cold", "hint"):
    checks.append((f"G1 mean {m}", pi3(mB[m])))
cB = g1["protocol_B"]
checks += [("G1 late", f"{pct(cB['pi_late']['comparisons']['floor-mwkr_cold']['rel_diff'])}\\%"),
           ("G1 late W/L", wl(cB["pi_late"]["comparisons"]["floor-mwkr_cold"])),
           ("G1 gapB", f"{pct(cB['gap_B']['comparisons']['floor-mwkr_cold']['rel_diff'])}\\%"),
           ("G1 gapB W/L", wl(cB["gap_B"]["comparisons"]["floor-mwkr_cold"]))]
for k, v in cB["by_delta"].items():
    c = v["comparisons"]["floor-mwkr_cold"]
    checks += [(f"G1 delta {k}", f"{pct(c['rel_diff'])}\\%"), (f"G1 delta {k} W/L", wl(c))]
ig = g1["initial_incumbent_gap_median"]
checks += [("G1 arrival init floor", f"{100 * ig['arrival']['floor']:.1f}\\%"),
           ("G1 arrival init mwkr", f"{100 * ig['arrival']['mwkr_cold']:.1f}\\%")]
holmA = max(c["sign_p_holm"] for c in g1["protocol_A"]["pi"]["comparisons"].values())
holmB = max(c["sign_p_holm"] for c in g1["protocol_B"]["pi"]["comparisons"].values())
checks.append(("G1 max Holm p", f"p\\le {max(holmA, holmB):.4f}"))
integ = g1["integrity"]
n_g1 = sum(integ["solver_status"].values())
checks += [("G1 runs", f"{n_g1:,}".replace(",", "{,}")),
           ("G1 overrun max", f"{integ['overrun_max_s']:.2f}\\,s")]

# ---- Confirmatory (Table 2 and text) ----
for role, mm in cf["means"].items():
    checks.append((f"CF mean pi {role}", pi3(mm["pi"])))
    checks.append((f"CF mean gapB {role}", pi3(mm["gap_B"])))
for k, v in cf["family"].items():
    c = v["pi"]
    checks += [(f"CF {k} rel", f"{pct(c['rel_diff'])}\\%"), (f"CF {k} W/L", wl(c))]
prim = cf["family"]["iaip_sr vs fresh_portfolio_cold"]
checks += [("CF CI", f"[{prim['pi']['ci95'][0]:.4f},{prim['pi']['ci95'][1]:.4f}]"),
           ("CF Holm", f"{prim['pi']['sign_p_holm']:.1e}".replace("e-", "\\cdot10^{-").replace("e", "") + "}"),
           ("CF gapB rel", f"{pct(prim['gap_B']['rel_diff'])}\\%"), ("CF gapB W/L", wl(prim["gap_B"])),
           ("CF integrity records", f"{cf['integrity']['records']:,}".replace(",", "{,}")),
           ("CF overrun max", f"{cf['integrity']['overrun_max_s']:.2f}\\,s")]
assert all(cf["go_criteria"].values()), cf["go_criteria"]
for k, v in cf["by_delta"].items():
    c = v["primary"]
    checks += [(f"CF delta {k}", f"{pct(c['rel_diff'])}\\%"), (f"CF delta {k} W/L", wl(c))]
for r in ("floor", "fresh_portfolio_cold", "iaip_sr"):
    checks.append((f"CF arrival {r}", pi3(cf["by_delta"]["arrival"][r])))
for r in ("portfolio_hinted", "portfolio_cold"):
    checks.append((f"CF outage {r}", pi3(cf["by_delta"]["outage"][r])))
for k in ("portfolio_hinted vs portfolio_cold", "fresh_portfolio_hinted vs fresh_portfolio_cold"):
    c = sup[k]
    checks += [(f"SUP {k}", f"{pct(c['rel_diff'])}\\%"), (f"SUP {k} W/L", wl(c))]
st = sup["stability_frac_changed"]
for r in ("iaip_sr", "floor", "cold"):
    checks.append((f"stability {r}", f"{100 * st[r]:.1f}\\%"))
tot = cf["means"]["fresh_portfolio_cold"]["pi"] - cf["means"]["iaip_sr"]["pi"]
steps = [cf["means"]["fresh_portfolio_cold"]["pi"] - cf["means"]["portfolio_cold"]["pi"],
         cf["means"]["portfolio_cold"]["pi"] - cf["means"]["portfolio_hinted"]["pi"],
         cf["means"]["portfolio_hinted"]["pi"] - cf["means"]["iaip_sr"]["pi"]]
checks.append(("CF attribution", ", ".join(f"{round(100 * s / tot)}\\%" for s in steps[:2]) + f" and {round(100 * steps[2] / tot)}\\%"))
for size, lbl in (("15x15", "IAIP-SR"), ("20x20", "IAIP-SR"), ("15x15", "fresh portfolio + Cold"), ("20x20", "fresh portfolio + Cold")):
    checks.append((f"fig {size} {lbl}", f"{fig[f'{size}|{lbl}']['median_gap_pct_at']['8.0']:.1f}\\%"))

# ---- E6 (Table 3 and text) ----
for camp in ("e6a_b2", "e6a_b30", "e6b_w4", "e6c_arrival", "e6c_outage", "e6c_high", "e6d_benchmarks"):
    for b in ("fresh_portfolio_cold", "portfolio_hinted", "floor"):
        c = e6[camp]["comparisons"][f"iaip_sr vs {b}"]["pi"]
        checks.append((f"E6 {camp} {b}", f"$-{pct(c['rel_diff'], 0)}$\\% {wl(c)}"))
checks += [("E6 b30 text", f"{pct(e6['e6a_b30']['comparisons']['iaip_sr vs fresh_portfolio_cold']['pi']['rel_diff'])}\\%"),
           ("E6 w4 text", f"{pct(e6['e6b_w4']['comparisons']['iaip_sr vs fresh_portfolio_cold']['pi']['rel_diff'])}\\%"),
           ("E6 w4 ph mean", pi3(e6["e6b_w4"]["means"]["portfolio_hinted"]["pi"])),
           ("E6 w4 iaip mean", pi3(e6["e6b_w4"]["means"]["iaip_sr"]["pi"]))]
for b, lbl in (("floor", "floor"), ("lns_prev_solution", "lns"), ("fix_and_optimize_50", "fo")):
    c = e6e["comparisons"][f"iaip_sr vs {b}"]["pi"]
    checks += [(f"E6e {lbl}", f"{pct(c['rel_diff'])}\\% ({wl(c)})")]

def found(s):
    return s in tex or s.replace("\\%", "$\\%") in tex  # table cells: $+20.9$\%


missing = [(lbl, s) for lbl, s in checks if not found(s)]
print(f"{len(checks) - len(missing)}/{len(checks)} expected strings found in manuscript.tex")
for lbl, s in missing:
    print(f"  NOT FOUND  {lbl}: {s}")
sys.exit(1 if missing else 0)
