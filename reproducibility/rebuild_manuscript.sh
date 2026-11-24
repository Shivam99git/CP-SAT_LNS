#!/usr/bin/env bash
# Regenerate the numerical macro registry, figures/tables, and compile the final
# manuscript PDF and the anonymous supplement PDF (Task A7, A8, A12).
#
#   bash reproducibility/rebuild_manuscript.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/paper/icaps27_multisolver_final"

echo "== Regenerating the numerical macro registry (no number is hand-typed) =="
../../.venv/bin/python make_numbers.py

echo "== Checking every manuscript number resolves to a registry macro =="
../../.venv/bin/python check_claims.py

echo "== Compiling manuscript.tex =="
pdflatex -interaction=nonstopmode manuscript >/dev/null
bibtex manuscript >/dev/null 2>&1 || true
pdflatex -interaction=nonstopmode manuscript >/dev/null
pdflatex -interaction=nonstopmode manuscript

echo "== Stripping metadata to produce the double-blind candidate PDF =="
../../.venv/bin/python make_candidate.py

echo "== Compiling the supplement =="
pdflatex -interaction=nonstopmode supplement >/dev/null
pdflatex -interaction=nonstopmode supplement

echo "== Verifying figures/tables are traceable and not stale =="
../../.venv/bin/python verify_visuals.py

echo "== Artifact manifest (SHA-256 of every generated output) =="
cd "$ROOT"
.venv/bin/python reproducibility/make_artifact_manifest.py

echo "RESULT: manuscript rebuild complete. See paper/icaps27_multisolver_final/manuscript_candidate.pdf,"
echo "        supplement.pdf, and reproducibility/REPRODUCTION_MANIFEST.json (artifacts section)."
