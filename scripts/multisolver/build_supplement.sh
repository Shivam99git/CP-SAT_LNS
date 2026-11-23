#!/usr/bin/env bash
# Anonymous reproducibility supplement for paper/icaps27_multisolver_final.
# Includes all code and tests, the multisolver instance archive (hashed), every
# multisolver raw run record (compressed), all analysis outputs, the solver
# inventory, the CP-SAT confirmatory analysis files and the manuscript sources.
# Excludes CP-SAT confirmatory raw trajectories (several hundred MB; their
# SHA-256 checksums are included) and solver binaries/licences.
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT="${1:-$(mktemp -d)/supplement}"
rm -rf "$OUT" && mkdir -p "$OUT/paper"
cp -r phase0 tests scripts docs "$OUT/"
cp -r paper/icaps27_multisolver_final "$OUT/paper/"
find "$OUT/paper" \( -name "*.aux" -o -name "*.log" -o -name "*.blg" -o -name "*.out" \) -delete
find "$OUT" -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
rm -f "$OUT/scripts/unified/build_supplement.sh"  # superseded; its redaction patterns embed identity strings
cp requirements_research.txt "$OUT/" 2>/dev/null || true
mkdir -p "$OUT/results"
find results -name "*.json" -not -path "*/runs/*" -exec cp --parents {} "$OUT/" \;
find results -name "manifests.jsonl" -exec cp --parents {} "$OUT/" \;
find results -name "RUNS.sha256" -exec cp --parents {} "$OUT/" \;
cp --parents results/multisolver/FROZEN_PLAN.sha256 "$OUT/"
cp -r --parents results/multisolver/instances "$OUT/"
tar czf "$OUT/results/multisolver/runs.tar.gz" results/multisolver/runs
( cd results/unified_icaps/confirmatory && find . -path "*/runs/*.jsonl" -exec sha256sum {} + ) > "$OUT/results/unified_icaps/confirmatory/RAW_RUNS.sha256"
# identity strings are read from the environment, so this script itself contains none
ID_USER="$(whoami)"; ID_HOST="$(hostname)"; ID_HOME="$HOME"
ID_EMAIL="$(git config user.email || true)"; ID_NAME="$(git config user.name || true)"
python3 - "$OUT" "$ID_USER" "$ID_HOST" "$ID_HOME" "$ID_EMAIL" "$ID_NAME" <<'EOF'
import io, os, re, sys, tarfile
out, user, host, home, email, name = sys.argv[1:7]
subs = [(re.escape(home) + r"/[^\"' \n]*", "<repo-root>"), (re.escape(host), "<host>")]
subs += [(re.escape(x), "<redacted>") for x in (email, name, user) if x]
def clean(b):
    t = b.decode("utf-8", "surrogateescape")
    for pat, rep in subs:
        t = re.sub(pat, rep, t, flags=re.I)
    return t.encode("utf-8", "surrogateescape")
for root, _, files in os.walk(out):
    for fn in files:
        p = os.path.join(root, fn)
        if fn.endswith((".gz", ".zip", ".pdf", ".png")):
            continue
        b = open(p, "rb").read()
        if b"\0" in b[:4096]:
            continue
        c = clean(b)
        if c != b:
            open(p, "wb").write(c)
src = f"{out}/results/multisolver/runs.tar.gz"
data = io.BytesIO()
with tarfile.open(src) as tin, tarfile.open(fileobj=data, mode="w:gz") as tout:
    for m in tin.getmembers():
        f = tin.extractfile(m)
        if f is None:
            tout.addfile(m); continue
        b = clean(f.read())
        m.size = len(b)
        tout.addfile(m, io.BytesIO(b))
open(src, "wb").write(data.getvalue())
# final check: nothing identifying left anywhere (text, PDFs, archive)
left = []
for root, _, files in os.walk(out):
    for fn in files:
        p = os.path.join(root, fn)
        b = open(p, "rb").read()
        if fn.endswith(".gz"):
            with tarfile.open(p) as t:
                b = b"".join(t.extractfile(m).read() for m in t.getmembers() if m.isfile())
        toks = [user, host, email] + [w for w in name.split() if len(w) >= 4]
        if any(x and x.lower().encode() in b.lower() for x in toks):
            left.append(p)
print("identifying strings remaining in:", left or "none")
sys.exit(1 if left else 0)
EOF
cat > "$OUT/README_SUPPLEMENT.md" <<'EOF'
# Anonymous reproducibility supplement

Manuscript: paper/icaps27_multisolver_final/manuscript_candidate.pdf.

* CP-SAT confirmatory study: analysis files under results/unified_icaps/, independent re-verification under
  results/final_icaps/ and results/multisolver/audit/ (third code-disjoint recomputation from raw events).
  Raw trajectories are not included (size); RAW_RUNS.sha256 lists their checksums.
* Cross-solver study: results/multisolver/ -- solver_inventory.json (what was runnable, licence limits),
  FROZEN_PLAN.json (+ sha256, written before any held-out run), instances/ (hashed archive with reference
  histories), runs.tar.gz (every held-out and pilot record, including failures), analysis/*.json,
  validation_report.json, smoke/smoke_results.json.
* Supplementary PDF: paper/icaps27_multisolver_final/supplement.pdf (tables S1-S6, figures S1-S6, all frozen comparisons).
* Reproduce: scripts/multisolver/run_all_available.py (one command), or scripts/multisolver/{discover_solvers,run_smoke,run_benchmark,validate_results,analyze_results,
  generate_figures}.py; tests/multisolver (equivalence vs an exhaustive oracle).
* Solvers: OR-Tools 9.15.6755, CP Optimizer CE / CPLEX CE 22.2.0.0 (pip, size-limited), Gurobi 13.0.2
  (pip, size-limited), SCIP 10.0 (PySCIPOpt 6.3.0), HiGHS 1.16.0, CBC 2.10.12 (via OR-Tools), GLPK 5.0
  (swiglpk), Gecode 6.4.0 and Chuffed 0.14.0 (MiniZinc 2.10.1). No licence files are included.
EOF
du -sh "$OUT"
(cd "$OUT/.." && zip -rq supplement.zip supplement -x '*.pyc')
du -sh "$OUT/../supplement.zip"
sha256sum "$OUT/../supplement.zip"
