"""Manifest loading and single-service fallback."""

import textwrap

import pytest

from common import services as svc_mod
from common.services import GATEWAY_ROLE, INTERNAL_ROLE, load_application


@pytest.fixture
def fake_codebases(tmp_path, monkeypatch):
    """Redirect codebases/databases resolution into a temp tree."""
    (tmp_path / "solo").mkdir()
    (tmp_path / "db_solo").mkdir()
    (tmp_path / "svc_a").mkdir()
    (tmp_path / "svc_b").mkdir()

    monkeypatch.setattr(svc_mod, "get_app_source_dir", lambda a: tmp_path / a)
    monkeypatch.setattr(svc_mod, "get_app_database_dir", lambda a: tmp_path / ("db_" + a))
    monkeypatch.setattr(svc_mod, "get_codebases_dir", lambda: tmp_path)
    monkeypatch.setattr(svc_mod, "get_database_language", lambda p: "java")
    return tmp_path


def test_single_service_fallback(fake_codebases):
    app = load_application("solo")
    assert not app.is_multi_service
    assert len(app.services) == 1
    assert app.services[0].role == GATEWAY_ROLE
    assert app.services[0].key == "solo"


def test_manifest_with_explicit_paths(tmp_path, fake_codebases):
    manifest = tmp_path / "mapp" / "neo.services.yaml"
    manifest.parent.mkdir()
    manifest.write_text(textwrap.dedent(f"""
        name: shop
        services:
          - name: gateway
            source: {tmp_path / "svc_a"}
            database: {tmp_path / "svc_a"}
            role: gateway
            aliases: ["edge", "localhost:8080"]
          - name: orders
            source: {tmp_path / "svc_b"}
            database: {tmp_path / "svc_b"}
            base_path: /api
    """))

    app = load_application(str(manifest))
    assert app.is_multi_service
    assert app.name == "shop"
    gw = app.get("gateway")
    assert gw.is_gateway and "edge" in gw.match_tokens()
    orders = app.get("orders")
    assert orders.role == INTERNAL_ROLE
    assert orders.base_path == "/api"
    assert [s.name for s in app.gateway_services()] == ["gateway"]


def test_invalid_service_name_rejected(tmp_path, fake_codebases):
    manifest = tmp_path / "bad" / "services.yaml"
    manifest.parent.mkdir()
    manifest.write_text(textwrap.dedent(f"""
        services:
          - name: "svc/with/slash"
            source: {tmp_path / "svc_a"}
            database: {tmp_path / "svc_a"}
    """))
    with pytest.raises(ValueError, match="invalid"):
        load_application(str(manifest))


def test_duplicate_service_names_rejected(tmp_path, fake_codebases):
    manifest = tmp_path / "dup" / "services.yaml"
    manifest.parent.mkdir()
    manifest.write_text(textwrap.dedent(f"""
        services:
          - name: api
            source: {tmp_path / "svc_a"}
            database: {tmp_path / "svc_a"}
          - name: api
            source: {tmp_path / "svc_b"}
            database: {tmp_path / "svc_b"}
    """))
    with pytest.raises(ValueError, match="duplicate"):
        load_application(str(manifest))


def test_manifest_defaults_first_service_to_gateway(tmp_path, fake_codebases):
    manifest = tmp_path / "m2" / "services.yaml"
    manifest.parent.mkdir()
    manifest.write_text(textwrap.dedent(f"""
        services:
          - name: a
            source: {tmp_path / "svc_a"}
            database: {tmp_path / "svc_a"}
          - name: b
            source: {tmp_path / "svc_b"}
            database: {tmp_path / "svc_b"}
    """))
    app = load_application(str(manifest))
    assert app.get("a").is_gateway
    assert not app.get("b").is_gateway
