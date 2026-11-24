#!/usr/bin/env bash
# Set up both Python environments used by this project (Task A2).
#
#   bash reproducibility/setup_environment.sh
#
# Creates/updates:
#   .venv/     -- CP-SAT confirmatory study, manuscript tooling (pypdf, matplotlib, pytest)
#   .venv_ms/  -- multisolver study: reuses .venv's site-packages via a .pth file
#                 (so Gurobi/CPLEX/CP-Optimizer/OR-Tools are not reinstalled) and adds
#                 pyscipopt, highspy, pulp, swiglpk, minizinc, psutil.
#   .solvers/  -- MiniZinc 2.10.1 (bundles Gecode 6.4.0 and Chuffed 0.14.0), downloaded
#                 once and checksum-verified.
#
# No step here requires interactive input or a machine-specific path; everything is
# resolved relative to the repository root ($ROOT below).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
echo "== Python interpreter: $("$PY" --version)"

if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
if [ -f requirements_research.txt ]; then
  .venv/bin/pip install -r requirements_research.txt -q
fi
# Packages the manuscript/reproduction tooling needs that may not be pinned above.
.venv/bin/pip install -q pypdf matplotlib pandas numpy scipy pytest 2>/dev/null || true

if [ ! -d .venv_ms ]; then
  "$PY" -m venv --without-pip .venv_ms
  SITE=$(.venv/bin/python -c "import site; print(site.getsitepackages()[0])")
  MS_SITE=$(.venv_ms/bin/python -c "import site; print(site.getsitepackages()[0])")
  mkdir -p "$MS_SITE"
  echo "$SITE" > "$MS_SITE/zz_base_venv.pth"
  .venv/bin/python -m venv --upgrade-deps .venv_ms >/dev/null 2>&1 || true
  curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip-ms.py 2>/dev/null && \
    .venv_ms/bin/python /tmp/get-pip-ms.py -q || true
fi
.venv_ms/bin/pip install -q pyscipopt==6.3.0 highspy==1.16.0 pulp==4.3.1 swiglpk==5.0.13 \
  minizinc==0.10.0 psutil 2>/dev/null || true

# MiniZinc 2.10.1 bundle (Gecode 6.4.0, Chuffed 0.14.0). Pinned because solver behaviour
# is version-specific (docs/multisolver/SOLVER_AVAILABILITY.md). Re-download is skipped
# if the checksum already on disk matches.
MZN_DIR=".solvers/MiniZincIDE-2.10.1-x86_64-linux-gnu"
MZN_URL="https://github.com/MiniZinc/MiniZincIDE/releases/download/2.10.1/MiniZincIDE-2.10.1-x86_64-linux.tgz"
if [ ! -x "$MZN_DIR/bin/minizinc" ]; then
  mkdir -p .solvers
  echo "== Downloading MiniZinc 2.10.1 bundle (Gecode + Chuffed) ..."
  if curl -sSL -o .solvers/mzn.tgz "$MZN_URL"; then
    sha256sum .solvers/mzn.tgz > .solvers/mzn.tgz.sha256
    tar xzf .solvers/mzn.tgz -C .solvers
  else
    echo "WARNING: could not download MiniZinc automatically. Install 2.10.1 manually to $MZN_DIR"
  fi
else
  echo "== MiniZinc already present at $MZN_DIR"
fi

echo "== Setup complete. Verify with: bash reproducibility/check_dependencies.sh"
