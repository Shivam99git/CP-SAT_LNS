"""Offline certificate diagnostic on archived IAIP-SR development runs (no
solver calls). For every step >= 1 of an IAIP-SR configuration it replays the
deterministic portfolio from the method's own recorded previous solution,
rebuilds IAIP-SR's N5 neighbourhood, computes the COBAR certificate and the
release, and compares with the local status CP-SAT actually reported.

    .venv/bin/python scripts/cobar/diagnose_certificates.py results/research_extension/dev_e5c \
        "iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted"
"""
import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from phase0.cobar_certificates import certificate, global_certificate  # noqa: E402
from phase0.cobar_neighborhood import release_obstructions  # noqa: E402
from phase0.incumbent_portfolio import PORTFOLIOS, build_portfolio  # noqa: E402
from phase0.run_iaip_campaign import CampaignSpec  # noqa: E402
from phase0.selective_reoptimization import disruption_set, make_neighbourhood  # noqa: E402

root, method = Path(sys.argv[1]), sys.argv[2]
man = json.loads(open(root / "manifests.jsonl").readline())["argv"]
rows = []
for f in sorted((root / "runs").glob("*.jsonl")):
    recs = {r["step"]: r for r in map(json.loads, open(f)) if r["method"] == method}
    if not recs:
        continue
    r0 = next(iter(recs.values()))
    m = int(r0["size"].split("x")[0])
    spec = CampaignSpec(m, m, r0["stream_seed"], man["stream_length"])
    stream = spec.build()
    for k in range(1, len(stream)):
        inst, prev_inst, prev = stream[k], stream[k - 1], recs[k - 1]["solution"]
        pf = build_portfolio(inst, prev, PORTFOLIOS["full"], construction_budget=0.05 * man["budget"])
        inc = pf.solution
        D = disruption_set(prev_inst, inst, prev)
        N = make_neighbourhood("N5", inst, inc, D, 0.25)
        cert = certificate(inst, inc, N)
        gc = global_certificate(inst, inc)
        rel = release_obstructions(inst, inc, N, mode="arcs")
        loc = recs[k]["meta"].get("local", {})
        replay_ok = pf.objective == recs[k]["construction_objective"]
        rows.append(dict(stream=spec.name, step=k, delta=inst.delta_kind, U=cert.U, L=cert.L, L_path=cert.L_path,
                         L_mach=cert.L_mach, decisive=cert.decisive, kind=cert.kind, cert_s=cert.time_s,
                         gL=gc.L, g_decisive=gc.decisive, rel_status=rel.status, rel_arcs=len(rel.R),
                         rel_iter=rel.iterations, rel_s=rel.time_s, rel_after_decisive=rel.after.decisive,
                         N=len(N), n_ops=len(inst.all_ops), local_status=loc.get("local_status"),
                         local_s=loc.get("local_time_s"), local_improved=loc.get("local_improved"),
                         replay_matches_record=replay_ok))
out = root / "cobar_certificate_diagnostic.jsonl"
with open(out, "w") as fh:
    for r in rows:
        fh.write(json.dumps(r) + "\n")
n = len(rows)
print(f"{n} steps; portfolio replay matches recorded construction objective: {sum(r['replay_matches_record'] for r in rows)}/{n}")
ct = collections.Counter((r["decisive"], r["local_status"]) for r in rows)
print("certificate decisive x recorded local status:", dict(ct))
print("decisive kinds:", dict(collections.Counter(r["kind"] for r in rows if r["decisive"])))
gap = np.array([(r["U"] - r["L"]) / r["U"] for r in rows if not r["decisive"]])
print(f"non-decisive opportunity gap (U-L)/U: median {np.median(gap):.3f}, p10 {np.quantile(gap,.1):.3f}, p90 {np.quantile(gap,.9):.3f}")
print("global certificates decisive:", sum(r["g_decisive"] for r in rows))
print("release status on decisive:", dict(collections.Counter(r["rel_status"] for r in rows if r["decisive"])))
ra = [r["rel_arcs"] for r in rows if r["rel_status"] == "released"]
print(f"released arcs per released step: median {np.median(ra) if ra else 0}, max {max(ra) if ra else 0}")
print(f"certificate time: median {1000*np.median([r['cert_s'] for r in rows]):.1f} ms, max {1000*max(r['cert_s'] for r in rows):.1f} ms; "
      f"release time median {1000*np.median([r['rel_s'] for r in rows]):.1f} ms, max {1000*max(r['rel_s'] for r in rows):.1f} ms")
inf = [r for r in rows if r["local_status"] == "INFEASIBLE"]
print(f"INFEASIBLE local stages explained by the certificate: {sum(r['decisive'] for r in inf)}/{len(inf)}")
print(f"wrote {out}")
