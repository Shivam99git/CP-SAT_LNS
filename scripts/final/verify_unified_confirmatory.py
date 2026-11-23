"""Independent re-verification of the unified confirmatory campaign (U1-U9),
for the final ICAPS submission phase (docs/final_icaps/01_baseline_verification.md).

Reuses the independent, zero-shared-code verification machinery from
scripts/unified/verify_baseline.py (own instance reader, own feasibility
checker, own primal-integral integrator, own sign test / Holm / bootstrap --
none of this is the phase0.analyze_* code the original campaign used), and
applies it to every setting (U1-U9) of the unified study's confirmatory
campaign, using the frozen roles/family from FROZEN_CONFIG.json.

Also explicitly checks the stream/seed relationship: how many distinct
stream_seed values back the 40 (or 20, or 34) units of each setting, whether
seeds are reused across sizes, and whether that reuse could introduce
non-independence (it does not: see the report).

    .venv/bin/python scripts/final/verify_unified_confirmatory.py
"""
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/unified"))
from verify_baseline import checksums, verify  # noqa: E402

CONF = ROOT / "results/unified_icaps/confirmatory"


def stream_seed_report(d: Path) -> dict:
    """How many distinct stream_seed values, how many distinct sizes, and
    whether seed values are shared across sizes (they are, by design)."""
    import glob
    seeds_by_size = collections.defaultdict(set)
    all_streams = set()
    for f in glob.glob(str(d / "runs" / "*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            seeds_by_size[r.get("size", "bench")].add(r["stream_seed"])
            all_streams.add(r["stream"])
    sizes = sorted(seeds_by_size)
    shared = len(sizes) > 1 and len(set.intersection(*seeds_by_size.values())) > 0
    return {
        "n_physical_streams": len(all_streams),
        "sizes": sizes,
        "n_distinct_seed_values_per_size": {s: len(v) for s, v in seeds_by_size.items()},
        "seed_values_shared_across_sizes": shared,
        "note": ("Seed numbers ARE reused across sizes (e.g. seed 1101 backs both a 15x15 and a "
                 "20x20 stream); this does not create non-independent units because (a) the unit "
                 "of analysis is the full stream identifier '{size}_s{seed}', which denotes a "
                 "genuinely different physical instance sequence per size (different job/machine "
                 "counts change every size-dependent random draw after the shared PRNG seed), and "
                 "(b) no analysis anywhere treats the bare seed number, or multiple solver seeds of "
                 "the same stream, as separate independent units.") if shared else "no sharing detected",
    }


def main():
    raw = (CONF / "FROZEN_CONFIG.json").read_bytes()
    cfg = json.loads(raw)
    sha = (CONF / "FROZEN_CONFIG.sha256").read_text().split()[0]
    assert hashlib.sha256(raw).hexdigest() == sha, "FROZEN_CONFIG.json changed after freezing!"
    arch = json.loads((CONF / "confirmatory_analysis.json").read_text())["settings"]

    out = {"frozen_sha256_verified": True, "settings": {}}
    for name in cfg["run_order"]:
        d = CONF / name
        if not (d / "runs").exists():
            print(f"SKIP {name}: no runs directory")
            continue
        fam = [tuple(x) for x in (cfg["family_U1"] if name == "U1_primary"
                                   else cfg["family_U2"] if name == "U2_mechanism"
                                   else cfg["family_other"])]
        rep = verify(d, cfg["roles"], fam, arch.get(name))
        rep["checksums"] = checksums(d)
        rep["stream_seed_analysis"] = stream_seed_report(d)
        out["settings"][name] = rep
        print(f"\n=== {name} ===")
        print(json.dumps({k: rep[k] for k in ("records", "solver_invocations", "physical_instances",
                                               "grid_complete", "infeasible_final_schedules",
                                               "objective_vs_own_makespan_mismatch", "duplicate_run_keys",
                                               "checksums")}))
        print("stream/seed:", json.dumps(rep["stream_seed_analysis"]))
        for k, c in rep["comparisons"].items():
            ag = rep.get("agreement_with_archived", {}).get("comparisons", {}).get(k, {})
            print(f"  {k:36s} {100 * c['rel_diff']:+6.1f}% {c['W']}/{c['L']} holm={c['holm']:.2g}  agree={ag}")

    total_records = sum(s["records"] for s in out["settings"].values())
    total_infeasible = sum(s["infeasible_final_schedules"] for s in out["settings"].values())
    total_mismatch = sum(s["objective_vs_own_makespan_mismatch"] for s in out["settings"].values())
    print(f"\nTOTAL records across all settings: {total_records}")
    print(f"TOTAL infeasible (own checker): {total_infeasible}")
    print(f"TOTAL objective mismatches: {total_mismatch}")
    out["totals"] = {"records": total_records, "infeasible": total_infeasible, "objective_mismatches": total_mismatch}

    dest = ROOT / "results/final_icaps/unified_confirmatory_independent_verification.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, default=float))
    print("wrote", dest)


if __name__ == "__main__":
    main()
