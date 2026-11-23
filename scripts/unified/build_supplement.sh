#!/usr/bin/env bash
# Build the anonymous reproducibility supplement for the unified ICAPS-27
# submission (docs/unified_icaps/FINAL_SUBMISSION_RESEARCH_REPORT.md Part XI).
# Stages a clean copy (no .git, no author paths/emails) of: all code, tests,
# scripts, the unified/cobar/research_extension docs, the frozen configs,
# manifests, and all *analysis* result files (not raw per-run trajectories,
# which exceed the 100MB ICAPS-27 supplementary limit -- see the report).
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT="${1:-$(mktemp -d)/supplement}"
rm -rf "$OUT" && mkdir -p "$OUT"

cp -r phase0 tests scripts docs "$OUT/"
mkdir -p "$OUT/paper"
cp -r paper/icaps27_unified paper/icaps27_unified_final "$OUT/paper/"
rm -f "$OUT/paper/icaps27_unified_final/manuscript.aux" "$OUT/paper/icaps27_unified_final/manuscript.log" "$OUT/paper/icaps27_unified_final/manuscript.blg"
cp requirements_research.txt "$OUT/" 2>/dev/null || true

mkdir -p "$OUT/results"
find results -name "*.json" -not -path "*/runs/*" -exec cp --parents {} "$OUT/" \;
find results -name "manifests.jsonl" -exec cp --parents {} "$OUT/" \;
find results -name "RUNS.sha256" -exec cp --parents {} "$OUT/" \;
find results -name "*.jsonl" -path "*cobar_certificate_diagnostic*" -exec cp --parents {} "$OUT/" \;

# scrub any accidental author-identifying strings
grep -rIl "shivam-sharma\|Shivamgfa987\|/home/shivam" "$OUT" 2>/dev/null | while read -r f; do
  sed -i 's#/home/shivam-sharma/[^"'"'"' ]*#<repo-root>#g; s/shivam-sharma/<redacted>/g; s/Shivamgfa987@gmail.com/<redacted>/g' "$f"
done

cat > "$OUT/README_SUPPLEMENT.md" <<'EOF'
# Anonymous reproducibility supplement

**Submission manuscript:** paper/icaps27_unified_final/manuscript_candidate.pdf
(this is the paper this supplement accompanies; paper/icaps27_unified/ is an
earlier, superseded draft kept for provenance, and paper/icaps27_iaip/ and
paper/icaps27_cobar/ -- the two still-earlier, independently-preserved
research stages -- are intentionally NOT included here to keep the bundle
focused on the submitted paper's own lineage; their code and data are the
same phase0/ code already included, so nothing about their claims is lost.)

Contents: all source code (phase0/, tests/, scripts/), all documentation
(docs/, including docs/final_icaps/ -- the final verification/audit phase),
the manuscript sources for both the submitted candidate and its immediate
predecessor draft, and every saved *analysis* output (aggregate statistics,
means, comparisons, criteria, the independent re-verification records, and
the machine-readable verified_metrics.json claim registry) for every campaign
referenced in the manuscript, plus frozen-configuration files, run manifests
(software/hardware/seed provenance), saved solver-log transcripts
(results/final_icaps/solver_logs/, demonstrating which CP-SAT subsolvers
actually ran under each configuration), and per-campaign raw-file SHA-256
checksums.

NOT included (size): raw per-run trajectory files (results/**/runs/*.jsonl).
These total several hundred MB across all campaigns reported in this study,
exceeding the ICAPS-27 100MB supplementary-material limit (re-confirmed
directly from the live CFP page on 2026-11-23: "the total size must not
exceed 100 MB", anonymization required, reviewers not obliged to read it).
Their SHA-256 checksums ARE included (RUNS.sha256 in each campaign
directory), so the included analysis outputs are independently checkable
against the raw files without redistributing them in the capped bundle. The
raw files are preserved in the authors' private repository and will be
deposited at a stable, anonymous location (e.g. an anonymized OSF/Zenodo
record) for the camera-ready version.

Reproduction: see docs/unified_icaps/01-08 and docs/final_icaps/01-08
(numbered in run order across the two phases) for the full methodology, and
scripts/unified/run_confirmatory.sh / freeze_unified.py and
scripts/final/verify_unified_confirmatory.py / build_verified_metrics.py for
the exact launch and independent-verification commands.
requirements_research.txt pins dependency versions.
EOF

du -sh "$OUT"
find "$OUT" -type f | wc -l
(cd "$OUT/.." && zip -rq supplement.zip supplement -x '*.pyc')
du -sh "$OUT/../supplement.zip"
sha256sum "$OUT/../supplement.zip"
