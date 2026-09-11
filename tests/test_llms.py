"""LLM backend selection and the agent-CLI backends."""

import json
import os
import stat
import textwrap

import pytest

from common import llms
from common.llms import (
    LLMClient,
    _parse_claude_jsonl,
    _render_transcript,
    build_llm,
    resolve_llm_config,
    validate_model,
)


# --------------------------------------------------------------------------- #
# config resolution
# --------------------------------------------------------------------------- #

def test_default_provider_is_vertex(monkeypatch):
    monkeypatch.delenv("NEO_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("NEO_LLM_MODEL", raising=False)
    provider, model = resolve_llm_config()
    assert provider == "gcloud-anthropic"
    assert model == "claude-sonnet-4@20250514"


def test_env_overrides_provider_and_model(monkeypatch):
    monkeypatch.setenv("NEO_LLM_PROVIDER", "claude_cli")
    monkeypatch.setenv("NEO_LLM_MODEL", "claude-opus-4")
    assert resolve_llm_config() == ("claude_cli", "claude-opus-4")


def test_validate_model_permissive_for_cli():
    for p in ("cli", "claude_cli", "agy_cli", "gemini_cli"):
        assert validate_model(p, "anything") is True
    assert validate_model("openai", "not-a-real-model") is False


def test_build_llm_cli_needs_no_key(monkeypatch):
    monkeypatch.setenv("NEO_LLM_PROVIDER", "claude_cli")
    monkeypatch.setenv("NEO_LLM_MODEL", "")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = build_llm()
    assert client.provider == "claude_cli"
    assert client._client is None  # no API client constructed


# --------------------------------------------------------------------------- #
# transcript flattening + output parsing
# --------------------------------------------------------------------------- #

def test_render_transcript_single_user_message_passthrough():
    assert _render_transcript([{"role": "user", "content": "hello"}]) == "hello"


def test_render_transcript_multi_turn_is_labelled():
    out = _render_transcript([
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
    ])
    assert "[USER]" in out and "[ASSISTANT]" in out
    assert out.strip().endswith("[ASSISTANT]")


def test_parse_claude_jsonl_stream():
    stream = "\n".join([
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "part 1"}]}}),
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "part 2"}]}}),
        json.dumps({"type": "result", "total_cost_usd": 0.01, "num_turns": 2}),
    ])
    assert _parse_claude_jsonl(stream) == "part 1\npart 2"


def test_parse_claude_json_single_object():
    obj = json.dumps({"type": "result", "subtype": "success", "result": "the answer", "total_cost_usd": 0.0})
    assert _parse_claude_jsonl(obj) == "the answer"


def test_parse_falls_back_to_raw_text():
    assert _parse_claude_jsonl("just plain text\n") == "just plain text"


# --------------------------------------------------------------------------- #
# CLI invocation shape (per provider)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("provider,exe,stdin_used,parser", [
    ("claude_cli", "claude", True, "claude-json"),
    ("agy_cli", "agy", False, "text"),
    ("gemini_cli", "gemini", True, "text"),
])
def test_build_cli_invocation(monkeypatch, provider, exe, stdin_used, parser):
    monkeypatch.setattr(llms.shutil, "which", lambda name: f"/usr/bin/{name}")
    c = LLMClient(provider, model="", api_key="")
    argv, stdin_text, got_parser, env = c._build_cli_invocation("PROMPT", timeout=42)
    assert argv[0] == f"/usr/bin/{exe}"
    assert got_parser == parser
    if stdin_used:
        assert stdin_text == "PROMPT"
    else:
        assert stdin_text == "" and any("PROMPT" in a for a in argv)


def test_generic_cli_uses_env_command(monkeypatch):
    monkeypatch.setenv("LLM_CLI_COMMAND", "mytool --go")
    monkeypatch.setenv("LLM_CLI_PARSER", "text")
    c = LLMClient("cli", model="", api_key="")
    argv, stdin_text, parser, _env = c._build_cli_invocation("P", timeout=1)
    assert argv == ["mytool", "--go"]
    assert parser == "text" and stdin_text == "P"


def test_model_flag_added_when_set(monkeypatch):
    monkeypatch.setattr(llms.shutil, "which", lambda name: f"/usr/bin/{name}")
    c = LLMClient("claude_cli", model="claude-opus-4", api_key="")
    argv, *_ = c._build_cli_invocation("P", timeout=1)
    assert "--model" in argv and "claude-opus-4" in argv


# --------------------------------------------------------------------------- #
# end-to-end through a fake CLI executable
# --------------------------------------------------------------------------- #

def test_cli_message_end_to_end(tmp_path, monkeypatch):
    fake = tmp_path / "fakeclaude"
    fake.write_text(textwrap.dedent("""\
        #!/usr/bin/env bash
        cat >/dev/null           # consume stdin
        printf '%s\\n' '{"type":"assistant","message":{"content":[{"type":"text","text":"hi from fake"}]}}'
        printf '%s\\n' '{"type":"result","total_cost_usd":0,"num_turns":1}'
    """))
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setattr(llms.shutil, "which", lambda name: str(fake) if name == "claude" else None)
    c = LLMClient("claude_cli", model="", api_key="")
    resp = c.messages_create(history=[], message=[{"role": "user", "content": "hello"}])
    assert resp.content[0].text == "hi from fake"
    assert c.get_model_name() == "claude_cli"
