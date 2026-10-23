"""Measure the wall-clock cost of building the repair floor
(phase0.harness.list_schedule_bootstrap), which the campaign CSVs do not
record: warm_bootstrap_solve never sets SolveResult.bootstrap_time_s, so the
bootstrap_time_ms column is 0.0 for every boot_cold row and cannot be cited.

For each main-campaign size (full shop, durations U[5,50], same generator and
seeds 101-115 as results/icaps/runs/paper_main.csv) and each delta of the
stream, we take a CP-SAT solution of the previous instance (2 s solve), then
time the floor construction for the next instance, 50 repetitions each, and
report median and maximum. Results go to floor_timing.json.

    .venv/bin/python paper/icaps27/time_floor.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from phase0.harness import list_schedule_bootstrap  # noqa: E402
from phase0.model_builder import build_model, solve, validate_solution  # noqa: E402
from phase0.streams import StreamConfig, generate_stream  # noqa: E402

REPS = 50
out = {}
for m in (10, 15, 20):
    samples = []
    for seed in range(101, 116):
        cfg = StreamConfig(num_machines=m, initial_jobs=m, stream_length=10, seed=seed,
                           severity="medium")
        cfg.ops_per_job = (m, m)
        cfg.duration_range = (5, 50)
        stream = generate_stream(cfg)
        prev, _, _ = solve(build_model(stream[0]), time_limit=2.0)
        for inst in stream[1:]:
            for _ in range(REPS):
                t0 = time.perf_counter()
                floor = list_schedule_bootstrap(inst, prev)
                samples.append(time.perf_counter() - t0)
            validate_solution(inst, floor)  # the floor must be feasible
            prev = floor
    a = np.array(samples) * 1000.0
    out[f"{m}x{m}"] = {"median_ms": float(np.median(a)), "p99_ms": float(np.percentile(a, 99)),
                       "max_ms": float(a.max()), "n_timings": int(len(a))}
    print(f"{m}x{m}: median {np.median(a):.3f} ms, p99 {np.percentile(a, 99):.3f} ms, "
          f"max {a.max():.3f} ms over {len(a)} timings")

Path(__file__).with_name("floor_timing.json").write_text(json.dumps(out, indent=2))
