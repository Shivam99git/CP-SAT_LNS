"""Solver adapters (multisolver phase). One adapter per independent solver
engine; MiniZinc backends are registered under the backend's own name.
OR-Tools' own CP-SAT reached through MiniZinc (fzn-cp-sat) is deliberately
NOT registered: it is the same engine as `cpsat` and would double-count."""

from .base import AdapterResult, Capabilities, SolveRequest, cached_version, run_adapter  # noqa: F401
from .cpoptimizer_adapter import CPOptimizerAdapter
from .cpsat_adapter import CPSATAdapter
from .minizinc_adapter import CHUFFED, GECODE
from .mip_backends import CBCAdapter, CplexAdapter, GLPKAdapter, GurobiAdapter, HiGHSAdapter, SCIPAdapter

ADAPTERS = {
    "cpsat": CPSATAdapter(),
    "cpoptimizer": CPOptimizerAdapter(),
    "gecode": GECODE,
    "chuffed": CHUFFED,
    "gurobi": GurobiAdapter(),
    "cplex": CplexAdapter(),
    "scip": SCIPAdapter(),
    "highs": HiGHSAdapter(),
    "cbc": CBCAdapter(),
    "glpk": GLPKAdapter(),
}
