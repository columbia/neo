import os
import z3
from typing import Dict, Any

# String-theory constraints can make Z3 run for a long time (or forever).
# Bound every check; a timeout is reported as satisfiable == "unknown", which
# callers treat conservatively (the flow is NOT pruned).
DEFAULT_TIMEOUT_MS = int(os.getenv("Z3_TIMEOUT_MS", "10000"))

_PLACEHOLDER_MARKERS = (
    "; define variables",
    "; express logical conditions",
    "no constraints provided",
)


def _looks_empty(smt: str) -> bool:
    """True when the LLM emitted only comments / the template stub / nothing."""
    if not smt or not smt.strip():
        return True
    meaningful = [
        ln.strip() for ln in smt.splitlines()
        if ln.strip() and not ln.strip().startswith(";")
    ]
    if not meaningful:
        return True
    low = smt.strip().lower()
    if low in _PLACEHOLDER_MARKERS:
        return True
    # needs at least one assertion to be checkable
    return not any("(assert" in ln for ln in meaningful)


def check_z3_constraints(smt_lib2_str: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> Dict[str, Any]:
    """
    Check Z3 SMT-LIB2 constraints for syntax and satisfiability.

    Returns a dict with:
      valid_syntax : bool   - the string parsed and had at least one assertion
      satisfiable  : str    - "sat" | "unsat" | "unknown" | "empty" | "error"
      errors       : list   - parser / solver error messages
      model        : dict   - variable -> value, only when satisfiable == "sat"
    """
    result = {
        "valid_syntax": False,
        "satisfiable": "error",
        "errors": [],
        "model": {},
    }

    if _looks_empty(smt_lib2_str):
        result["satisfiable"] = "empty"
        result["errors"].append("no checkable assertions in constraint block")
        return result

    try:
        solver = z3.Solver()
        solver.set("timeout", int(timeout_ms))

        constraints = z3.parse_smt2_string(smt_lib2_str)
        if len(constraints) == 0:
            result["satisfiable"] = "empty"
            result["errors"].append("parsed to zero assertions")
            return result

        solver.add(constraints)
        result["valid_syntax"] = True

        check_result = solver.check()
        result["satisfiable"] = str(check_result)  # sat | unsat | unknown

        if check_result == z3.unknown:
            reason = solver.reason_unknown()
            if reason:
                result["errors"].append(f"z3 unknown: {reason}")

        if check_result == z3.sat:
            model = solver.model()
            result["model"] = {str(var): str(model[var]) for var in model.decls()}

    except z3.Z3Exception as e:
        result["errors"].append(f"z3: {e}")
    except Exception as e:
        result["errors"].append(str(e))

    return result


# Test example
if __name__ == "__main__":
    constraints = """
(declare-const username String)
(declare-const authentication_required Bool)
(declare-const authorization_check_present Bool)
(assert (and
  (not (= username ""))
  (not authentication_required)
  (not authorization_check_present)))
"""
    result = check_z3_constraints(constraints)
    print(f"Valid: {result['valid_syntax']}")
    print(f"Satisfiable: {result['satisfiable']}")
    if result["model"]:
        print(f"Model: {result['model']}")
    if result["errors"]:
        print(f"Errors: {result['errors']}")
