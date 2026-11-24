"""SHA-256 manifest of every generated manuscript/analysis artifact (Task A8).

    .venv/bin/python reproducibility/make_artifact_manifest.py
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = "paper/icaps27_multisolver_final"
GLOBS = [
    f"{P}/manuscript.pdf", f"{P}/manuscript_candidate.pdf", f"{P}/supplement.pdf",
    f"{P}/numbers.tex", f"{P}/claims.json", f"{P}/claim_map.md",
    f"{P}/figures/*.pdf", f"{P}/figures/ms/*.pdf", f"{P}/figures/ms/tables/*.tex",
    "results/multisolver/solver_inventory.json", "results/multisolver/FROZEN_PLAN.json",
    "results/multisolver/analysis/*.json", "results/multisolver/audit/*.json",
    "results/multisolver/validation_report.json",
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    entries = {}
    for pat in GLOBS:
        for p in sorted(ROOT.glob(pat)):
            if p.is_file():
                entries[str(p.relative_to(ROOT))] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    out = ROOT / "reproducibility/ARTIFACT_MANIFEST.json"
    out.write_text(json.dumps({"generated": "reproducibility/make_artifact_manifest.py",
                                "n_files": len(entries), "files": entries}, indent=1))
    print(f"{len(entries)} artifacts hashed -> {out}")


if __name__ == "__main__":
    main()
