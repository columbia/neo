"""The cross-service validator uses the cross-service prompt template."""

from flows.validate_flows import IterativeFlowValidator


class _DummyDB:
    def get_function_by_identifier(self, *a, **k):
        return []

    def get_function_source_code(self, *a, **k):
        return None

    def close(self):
        pass


_FLOW = {
    "flow_id": "gflow_0",
    "source_location": "services/web/routes.js:10",
    "sink_location": "services/billing/billing.py:8",
    "steps": [
        {"step_role": "Step 1 [SOURCE]", "location": "services/web/routes.js:10",
         "statement": "req.body.amount", "function_id": "pay@services/web/routes.js:8"},
        {"step_role": "Step 2 [CROSS-SERVICE]", "location": "services/web/routes.js:11",
         "statement": "// inter-service call: web --[/charge]--> billing", "function_id": "N/A"},
        {"step_role": "Step 3 [SINK]", "location": "services/billing/billing.py:8",
         "statement": "ledger.charge(customer, amount)", "function_id": "charge@services/billing/billing.py:4"},
    ],
}


def test_cross_service_flag_selects_global_prompt(tmp_path):
    v = IterativeFlowValidator(llm_client=None, db=_DummyDB(),
                               source_root=tmp_path, output_dir=tmp_path / "out",
                               cross_service=True)
    first = v.create_flow_analysis_prompt(_FLOW, 0, 1, is_first_flow=True)
    nxt = v.create_flow_analysis_prompt(_FLOW, 1, 2, is_first_flow=False)
    assert "cross-service" in first.lower()
    assert "services/<svc>/" in first
    assert "[CROSS-SERVICE]" in first
    assert "cross-service" in nxt.lower()


def test_default_validator_uses_single_service_prompt(tmp_path):
    v = IterativeFlowValidator(llm_client=None, db=_DummyDB(),
                               source_root=tmp_path, output_dir=tmp_path / "out")
    first = v.create_flow_analysis_prompt(_FLOW, 0, 1, is_first_flow=True)
    assert "microservice" not in first.lower() or "cross-service" not in first.lower()
