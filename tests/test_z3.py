"""Z3 path-constraint checking and its use as a false-positive filter."""

import pytest

from common.z3helper import check_z3_constraints
from flows.validate_flows import IterativeFlowValidator as V


# --------------------------------------------------------------------------- #
# check_z3_constraints
# --------------------------------------------------------------------------- #

def test_satisfiable():
    r = check_z3_constraints(
        "(declare-const role String)\n"
        "(declare-const authz_present Bool)\n"
        '(assert (and (= role "admin") (not authz_present)))'
    )
    assert r["valid_syntax"] is True
    assert r["satisfiable"] == "sat"
    assert r["model"].get("role") in ('"admin"', "admin")


def test_unsatisfiable():
    r = check_z3_constraints("(declare-const p Bool)\n(assert (and p (not p)))")
    assert r["valid_syntax"] is True
    assert r["satisfiable"] == "unsat"


def test_comment_only_block_is_empty_not_error():
    r = check_z3_constraints(
        "; declare the variables\n; assert exploitation conditions\n"
    )
    assert r["valid_syntax"] is False
    assert r["satisfiable"] == "empty"


def test_no_assertion_is_empty():
    r = check_z3_constraints("(declare-const x Int)")
    assert r["satisfiable"] == "empty"


def test_malformed_is_error_not_crash():
    r = check_z3_constraints("(assert (and (this is not smtlib")
    assert r["satisfiable"] in ("error", "empty")
    assert r["valid_syntax"] is False


def test_timeout_arg_is_accepted():
    r = check_z3_constraints("(declare-const x Int)\n(assert (> x 0))", timeout_ms=500)
    assert r["satisfiable"] == "sat"


# --------------------------------------------------------------------------- #
# _z3_prunes_flow  (paper: drop a True Positive whose path constraints are UNSAT)
# --------------------------------------------------------------------------- #

def _fa(satisfiable, valid_syntax=True):
    return {"flow_id": "f", "constraints_solver": {"satisfiable": satisfiable, "valid_syntax": valid_syntax}}


def test_unsat_prunes_by_default(monkeypatch):
    monkeypatch.delenv("Z3_PRUNE_UNSAT", raising=False)
    assert V._z3_prunes_flow(_fa("unsat")) is True


def test_sat_and_unknown_are_kept(monkeypatch):
    monkeypatch.delenv("Z3_PRUNE_UNSAT", raising=False)
    assert V._z3_prunes_flow(_fa("sat")) is False
    assert V._z3_prunes_flow(_fa("unknown")) is False
    assert V._z3_prunes_flow(_fa("empty", valid_syntax=False)) is False
    assert V._z3_prunes_flow(_fa("unsat", valid_syntax=False)) is False  # unparsed -> keep


def test_pruning_can_be_disabled(monkeypatch):
    monkeypatch.setenv("Z3_PRUNE_UNSAT", "0")
    assert V._z3_prunes_flow(_fa("unsat")) is False


def test_save_positive_vulnerabilities_drops_unsat_tp(tmp_path, monkeypatch):
    monkeypatch.delenv("Z3_PRUNE_UNSAT", raising=False)

    class _DummyLLM:
        def get_model_name(self):
            return "test"

    v = V(_DummyLLM(), db=None, source_root=tmp_path, output_dir=tmp_path / "o")
    validations = [{
        "success": True,
        "flow_analyses": [
            {"flow_id": "keep", "source_location": "a:1", "sink_location": "b:2",
             "vulnerability_assessment": "True Positive",
             "constraints_solver": {"satisfiable": "sat", "valid_syntax": True}},
            {"flow_id": "drop", "source_location": "a:1", "sink_location": "c:3",
             "vulnerability_assessment": "True Positive",
             "constraints_solver": {"satisfiable": "unsat", "valid_syntax": True}},
        ],
    }]
    v.save_positive_vulnerabilities_sink(validations, tmp_path / "o")

    import json
    doc = json.loads((tmp_path / "o" / "vulnerabilities.json").read_text())
    sinks = {vv["sink"] for vv in doc["vulnerabilities"]}
    assert sinks == {"b:2"}
    assert doc["z3_pruned_flows"] == ["drop"]
