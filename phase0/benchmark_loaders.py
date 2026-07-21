"""Static job-shop benchmark loaders -> phase0 Instance/Job/Operation.

Two formats supported:

1. `load_taillard_style` -- the widely-distributed plain-text job-shop
   specification format used by most OR-Library-derived JSSP instance sets
   (e.g. ft06, la01, abz5, and Taillard's own ta* instances as commonly
   redistributed): first non-comment line is "<num_jobs> <num_machines>",
   followed by one line per job listing (machine, duration) pairs in
   processing order. Machine indices are auto-detected as 0- or 1-indexed
   (many redistributions use 1-indexed machines; this loader normalizes to
   0-indexed to match phase0's convention) by checking whether machine 0
   ever appears in the file.

   VALIDATED (2026-07-11) against 10 real OR-Library instances (ft06, ft10,
   ft20, la01-la05, abz5, abz6; see tests/fixtures/benchmarks_real/
   PROVENANCE.md) -- all 10 solved via CP-SAT to their exact published
   optimal makespan, with independent solution validation passing on each.
   See tests/test_icaps_benchmark_loaders.py::test_real_instances_match_
   published_optima for the permanent regression test.

2. `load_json_instance` -- a robust internal fallback format that avoids any
   ambiguity: {"num_machines": int, "jobs": [{"job_id": str,
   "ops": [{"machine": int, "duration": int}, ...]}, ...]}.

`load_benchmark_dir` loads every file in a directory (auto-detecting format
by extension: .txt/.jssp -> taillard-style, .json -> json), optionally
capped at `max_files`.
"""

from __future__ import annotations

import json
from pathlib import Path

from .streams import Instance, Job, Operation


def _make_instance(name: str, num_machines: int,
                   job_ops: list[list[tuple[int, int]]]) -> Instance:
    jobs = []
    for ji, ops in enumerate(job_ops):
        job_ops_built = tuple(
            Operation(op_id=f"{name}_j{ji}_o{k}", machine=m, duration=d)
            for k, (m, d) in enumerate(ops)
        )
        jobs.append(Job(job_id=f"{name}_j{ji}", ops=job_ops_built))
    return Instance(index=0, num_machines=num_machines, jobs=tuple(jobs))


def load_taillard_style(path: str | Path, name: str | None = None) -> Instance:
    """Load the (machine, duration)-pairs-per-line JSSP format. See module
    docstring for format details and the honest limitation notice."""
    path = Path(path)
    name = name or path.stem
    lines = [
        ln.strip() for ln in path.read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if not lines:
        raise ValueError(f"{path}: empty benchmark file")
    header = lines[0].split()
    num_jobs, num_machines = int(header[0]), int(header[1])

    job_ops: list[list[tuple[int, int]]] = []
    all_machine_ids: list[int] = []
    for job_line in lines[1:1 + num_jobs]:
        nums = [int(x) for x in job_line.split()]
        if len(nums) != 2 * num_machines:
            raise ValueError(
                f"{path}: job line has {len(nums)} numbers, "
                f"expected {2 * num_machines} (machine,duration pairs)"
            )
        pairs = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
        job_ops.append(pairs)
        all_machine_ids.extend(m for m, _ in pairs)

    one_indexed = min(all_machine_ids) >= 1 and max(all_machine_ids) == num_machines
    if one_indexed:
        job_ops = [[(m - 1, d) for m, d in ops] for ops in job_ops]

    if len(job_ops) != num_jobs:
        raise ValueError(f"{path}: expected {num_jobs} job lines, got {len(job_ops)}")
    return _make_instance(name, num_machines, job_ops)


def load_json_instance(path: str | Path, name: str | None = None) -> Instance:
    path = Path(path)
    name = name or path.stem
    data = json.loads(path.read_text())
    num_machines = data["num_machines"]
    job_ops = [
        [(op["machine"], op["duration"]) for op in job["ops"]]
        for job in data["jobs"]
    ]
    inst = _make_instance(name, num_machines, job_ops)
    if any("job_id" in job for job in data["jobs"]):
        jobs = tuple(
            Job(job_id=job.get("job_id", f"{name}_j{ji}"), ops=inst.jobs[ji].ops)
            for ji, job in enumerate(data["jobs"])
        )
        inst = Instance(index=0, num_machines=num_machines, jobs=jobs)
    return inst


def save_json_instance(instance: Instance, path: str | Path) -> None:
    """Round-trip helper: write an Instance out in the JSON fallback format
    (e.g. after loading/deriving one) for reuse without re-parsing text."""
    data = {
        "num_machines": instance.num_machines,
        "jobs": [
            {"job_id": job.job_id,
             "ops": [{"machine": op.machine, "duration": op.duration} for op in job.ops]}
            for job in instance.jobs
        ],
    }
    Path(path).write_text(json.dumps(data, indent=2))


_LOADERS = {".txt": load_taillard_style, ".jssp": load_taillard_style,
           ".json": load_json_instance}


def load_benchmark_file(path: str | Path, fmt: str = "auto") -> Instance:
    path = Path(path)
    if fmt == "auto":
        loader = _LOADERS.get(path.suffix.lower())
        if loader is None:
            raise ValueError(f"cannot auto-detect format for {path}; pass --benchmark-format")
        return loader(path)
    if fmt == "taillard":
        return load_taillard_style(path)
    if fmt == "json":
        return load_json_instance(path)
    raise ValueError(f"unknown benchmark format {fmt!r}")


def load_benchmark_dir(dir_path: str | Path, fmt: str = "auto",
                       max_files: int | None = None) -> list[Instance]:
    dir_path = Path(dir_path)
    files = sorted(
        p for p in dir_path.iterdir()
        if p.suffix.lower() in _LOADERS
    )
    if max_files is not None:
        files = files[:max_files]
    return [load_benchmark_file(p, fmt=fmt) for p in files]
