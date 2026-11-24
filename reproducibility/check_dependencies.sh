#!/usr/bin/env bash
# Verify that the environment set up by setup_environment.sh is usable (Task A2).
# Reports each dependency as OK or MISSING; does not stop at the first failure so the
# full picture is visible. Exit code is nonzero iff a REQUIRED dependency is missing.
#
#   bash reproducibility/check_dependencies.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0
req() { echo "REQUIRED  $1: $2"; }
opt() { echo "optional  $1: $2"; }

check_py() {
  local label="$1" bin="$2" mod="$3"
  if [ -x "$bin" ] && "$bin" -c "import $mod" >/dev/null 2>&1; then
    v=$("$bin" -c "import $mod; print(getattr($mod,'__version__','present'))" 2>/dev/null)
    req "$label" "OK ($v)"
  else
    req "$label" "MISSING"; FAIL=1
  fi
}

echo "== Core =="
[ -x .venv/bin/python ] && req ".venv (python $(.venv/bin/python --version 2>&1 | cut -d' ' -f2))" "OK" || { req ".venv" "MISSING -- run setup_environment.sh"; FAIL=1; }
[ -x .venv_ms/bin/python ] && req ".venv_ms" "OK" || { req ".venv_ms" "MISSING -- run setup_environment.sh"; FAIL=1; }
check_py "pytest" .venv/bin/python pytest
check_py "matplotlib" .venv/bin/python matplotlib
check_py "pypdf" .venv/bin/python pypdf

echo "== Engines (.venv_ms) required for the multisolver study =="
check_py "OR-Tools (CP-SAT, CBC)" .venv_ms/bin/python ortools
check_py "PySCIPOpt (SCIP)" .venv_ms/bin/python pyscipopt
check_py "highspy (HiGHS)" .venv_ms/bin/python highspy
check_py "swiglpk (GLPK)" .venv_ms/bin/python swiglpk
check_py "psutil" .venv_ms/bin/python psutil
MZN_BIN=".solvers/MiniZincIDE-2.10.1-x86_64-linux-gnu/bin/minizinc"
if [ -x "$MZN_BIN" ]; then
  req "MiniZinc (Gecode, Chuffed)" "OK ($("$MZN_BIN" --version 2>&1 | head -1))"
else
  req "MiniZinc" "MISSING -- run setup_environment.sh"; FAIL=1
fi

echo "== Licensed commercial engines (optional: tested only within free-edition size caps) =="
check_py_opt() {
  local label="$1" mod="$2"
  if .venv_ms/bin/python -c "import $mod" >/dev/null 2>&1; then
    opt "$label" "module present (licence/size limits checked at run time, not here)"
  else
    opt "$label" "module not installed -- results for this engine will read NOT EXECUTED"
  fi
}
check_py_opt "Gurobi" gurobipy
check_py_opt "CPLEX" cplex
check_py_opt "CP Optimizer (docplex)" docplex
[ -x .venv/bin/cpoptimizer ] && opt "cpoptimizer binary" "OK" || opt "cpoptimizer binary" "not found (CP Optimizer unavailable)"

echo "== Tools =="
command -v pdflatex >/dev/null && req "pdflatex" "OK" || { req "pdflatex" "MISSING"; FAIL=1; }
command -v bibtex >/dev/null && req "bibtex" "OK" || { req "bibtex" "MISSING"; FAIL=1; }
command -v git >/dev/null && req "git" "OK ($(git --version))" || { req "git" "MISSING"; FAIL=1; }
command -v java >/dev/null && opt "java (Choco solver)" "OK" || opt "java (Choco solver)" "not found -- Choco not evaluated (documented, not fabricated)"

echo "== Not installed anywhere on this project (documented, never substituted) =="
opt "FICO Xpress" "no Python module; commercial, no licence available"
opt "Hexaly" "no Python module; commercial, no licence available"

if [ "$FAIL" -ne 0 ]; then
  echo "RESULT: one or more REQUIRED dependencies are missing. See reproducibility/REPRODUCIBILITY.md."
  exit 1
fi
echo "RESULT: all required dependencies are present."
