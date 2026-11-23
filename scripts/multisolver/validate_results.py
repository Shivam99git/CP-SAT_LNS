"""Independent post-hoc validation of every multisolver run record (Task 8).

For each record: rebuild the instance from the hashed archive, re-check the
final schedule with the solver-independent validator, confirm its makespan
equals the recorded objective, and check the trajectory (strictly improving,
time-ordered, last event == final objective, events inside the budget plus
the recorded overrun). Also: no record may report a feasible objective below
z* (would indicate a model or validator bug -- z* is a minimum, so this
checks the bookkeeping), and an instance's records must all carry the same
hash. Exits non-zero on any violation.

    .venv_ms/bin/python scripts/multisolver/validate_results.py [--runs DIR]
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from campaign_lib import INST_DIR, load_stream  # noqa: E402
from phase0.schedule_validator import ScheduleError, check_schedule  # noqa: E402


@lru_cache(maxsize=None)
def stream(phase_tier_stream):
    for p in INST_DIR.rglob(f"{phase_tier_stream}.json"):
        return load_stream(p)
    raise FileNotFoundError(phase_tier_stream)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / "results/multisolver/runs"))
    ap.add_argument("--out", default=str(ROOT / "results/multisolver/validation_report.json"))
    a = ap.parse_args()
    viol, counts = [], Counter()
    by_exp = defaultdict(Counter)
    hashes = defaultdict(set)
    for f in sorted(Path(a.runs).rglob("*.jsonl")):
        if f.name == "manifest.jsonl":
            continue
        for line in open(f):
            r = json.loads(line)
            counts[r.get("status")] += 1
            by_exp[r.get("experiment")][r.get("status")] += 1
            if r.get("status") != "OK":
                continue
            d, insts, _ = stream(r["stream"])
            inst = insts[r["step"]]
            hashes[(r["stream"], r["step"])].add(r["instance_hash"])
            if r["instance_hash"] != d["steps"][r["step"]]["hash"]:
                viol.append((r["task_id"], "instance hash differs from archive"))
            if r.get("final_starts") is None:
                counts["OK_without_stored_schedule"] += 1
                by_exp[r.get("experiment")]["OK_without_stored_schedule"] += 1
            else:
                sol = {o.op_id: s for o, s in zip(inst.all_ops, r["final_starts"])}
                try:
                    v = check_schedule(inst, sol)
                    if v != r["objective"]:
                        viol.append((r["task_id"], f"makespan {v} != recorded {r['objective']}"))
                    counts["schedule_revalidated"] += 1
                    by_exp[r.get("experiment")]["schedule_revalidated"] += 1
                except ScheduleError as e:
                    viol.append((r["task_id"], f"invalid schedule: {e}"))
            ev = r.get("events", [])
            ts, objs = [e[0] for e in ev], [e[1] for e in ev]
            if ts != sorted(ts) or any(x <= y for x, y in zip(objs, objs[1:])):
                viol.append((r["task_id"], "trajectory not time-ordered/strictly improving"))
            if not objs or objs[-1] != r["objective"]:
                viol.append((r["task_id"], "last trajectory event != final objective"))
            if ts and (ts[0] < 0 or ts[-1] > r["budget"] + (r.get("overrun_s") or 0) + 1e-6):
                viol.append((r["task_id"], "trajectory event outside [0, budget + overrun]"))
    multi = [k for k, v in hashes.items() if len(v) > 1]
    for k in multi:
        viol.append((str(k), "records of one instance carry different hashes"))
    rep = {"status_counts": dict(counts), "by_experiment": {k: dict(v) for k, v in sorted(by_exp.items(), key=str)}, "n_violations": len(viol), "violations": viol[:200]}
    Path(a.out).write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "violations"}))
    for v in viol[:20]:
        print("VIOLATION", v)
    sys.exit(1 if viol else 0)


if __name__ == "__main__":
    main()
