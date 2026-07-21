"""Real RCPSP benchmark loader: the compact "Patterson" / .rcp format used
by PSPLIB and redistributed (e.g. by the ScheduleOpt/benchmarks repository,
https://github.com/ScheduleOpt/benchmarks/tree/main/rcpsp) for the classic
j30/j60/j90/j120 instance sets.

Format (plain whitespace-separated integers, one instance per file):
    line 1:  num_activities  num_resources
    line 2:  resource capacities (num_resources integers)
    lines 3..3+num_activities-1, one per activity in file order:
        duration  usage_1 .. usage_R  num_successors  succ_1 .. succ_k

Successors are 1-indexed activity numbers (matching file order); activities
0 and num_activities-1 (1-indexed: 1 and num_activities) are typically
zero-duration, zero-resource dummy source/sink nodes -- kept as ordinary
activities here (our model builder handles zero-duration activities fine,
and the dummy source/sink is exactly what makes precedence a connected DAG).

This is a *successor*-oriented format; our `Activity.predecessors` is
predecessor-oriented, so the loader inverts the successor lists into
predecessor lists after parsing every activity.
"""

from __future__ import annotations

from pathlib import Path

from .instances import Activity, RInstance


def load_rcp_instance(path: str | Path, name: str | None = None) -> RInstance:
    path = Path(path)
    name = name or path.stem
    tokens = path.read_text().split()
    pos = 0

    def next_int() -> int:
        nonlocal pos
        v = int(tokens[pos])
        pos += 1
        return v

    num_activities = next_int()
    num_resources = next_int()
    resource_ids = [f"r{i}" for i in range(num_resources)]
    resources = {rid: next_int() for rid in resource_ids}

    durations: list[int] = []
    usages: list[dict[str, int]] = []
    successors: list[list[int]] = []  # 1-indexed activity numbers
    for _ in range(num_activities):
        durations.append(next_int())
        usage = {}
        for rid in resource_ids:
            amt = next_int()
            if amt > 0:
                usage[rid] = amt
        usages.append(usage)
        n_succ = next_int()
        successors.append([next_int() for _ in range(n_succ)])

    if pos != len(tokens):
        raise ValueError(
            f"{path}: parsed {pos} tokens but file has {len(tokens)} -- "
            f"format mismatch (expected {num_activities} activities x "
            f"{num_resources} resources)"
        )

    # 0-indexed ("a0".."a{n-1}") to exactly match generate_rcpsp_instance's
    # synthetic-activity naming convention. This matters beyond cosmetics:
    # generate_rcpsp_stream(base_instance=...)'s activity_insertion delta
    # computes next_num = len(base_instance.activities) and names new
    # activities f"a{next_num}"; with 1-indexed IDs ("a1".."a{n}") that
    # collides with the real last activity "a{n}" (usually the dummy sink),
    # silently duplicating an activity_id and corrupting the precedence
    # graph (found 2026-07-12 via a crashed real-benchmark run: two Activity
    # objects sharing id "a122" made `activity_by_id` -- last-wins -- drop
    # one, so validate_rcpsp_solution saw predecessor edges inconsistent
    # with the object actually referenced by that id).
    activity_ids = [f"a{i}" for i in range(num_activities)]
    predecessors: list[list[str]] = [[] for _ in range(num_activities)]
    for i, succ_list in enumerate(successors):
        for s in succ_list:
            if not (1 <= s <= num_activities):
                raise ValueError(f"{path}: activity {i + 1} has out-of-range successor {s}")
            predecessors[s - 1].append(activity_ids[i])

    activities = tuple(
        Activity(
            activity_id=activity_ids[i],
            duration=durations[i],
            resource_usage=usages[i],
            predecessors=tuple(predecessors[i]),
        )
        for i in range(num_activities)
    )
    return RInstance(index=0, resources=resources, activities=activities)


def load_rcp_dir(dir_path: str | Path, max_files: int | None = None) -> list[tuple[str, RInstance]]:
    """Return [(instance_name, RInstance), ...] for every .rcp file in a
    directory, sorted by filename for determinism."""
    dir_path = Path(dir_path)
    files = sorted(p for p in dir_path.iterdir() if p.suffix == ".rcp")
    if max_files is not None:
        files = files[:max_files]
    return [(p.stem, load_rcp_instance(p)) for p in files]
