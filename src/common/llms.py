"""
LLM backends.

Every backend is reached through one interface — :meth:`LLMClient.messages_create`
— which mimics ``anthropic.messages.create`` and returns an object with
``.content[0].text``.

Backends
--------
``anthropic``        Anthropic API           (ANTHROPIC_API_KEY / CLAUDE_API_KEY)
``openai``           OpenAI API              (OPENAI_API_KEY)
``gcloud-anthropic`` Claude on Vertex AI     (GOOGLE_APPLICATION_CREDENTIALS,
                                              VERTEX_PROJECT_ID, VERTEX_LOCATION)
``cli``              shell out to an agent CLI (``claude``, ``codex``, ``gemini`` …)
                     — no API key, uses your own subscription.  See below.

CLI backend
-----------
Set ``NEO_LLM_PROVIDER=cli``.  The command is configurable:

    LLM_CLI_COMMAND="claude --print --output-format json"   # default
    LLM_CLI_PARSER=claude-json                               # or: text
    LLM_CLI_TIMEOUT=600

The rendered transcript is written to the process' stdin; the parser turns its
stdout into a single text string.  ``claude-json`` understands the Claude CLI's
JSONL stream (``{"type":"assistant",...}`` / ``{"type":"result",...}``); ``text``
returns stdout verbatim (works with any CLI that just prints the answer).

Config resolution
-----------------
``resolve_llm_config()`` reads ``NEO_LLM_PROVIDER`` / ``NEO_LLM_MODEL``
(falling back to Vertex Claude Sonnet), so nothing in the pipeline hard-codes a
provider.  ``build_llm()`` is the one-call constructor used by ``main.py``.
"""

from typing import List, Dict, Any, Optional
import json
import os
import shlex
import shutil
import subprocess
import sys

# Agent-CLI backends — no API key, they use your own subscription. The named
# ones (claude_cli / agy_cli / gemini_cli) mirror peng-hui/python-llm-cli and
# ~/code-plus/agent/synth/session.py; "cli" is a generic escape hatch driven by
# LLM_CLI_COMMAND / LLM_CLI_PARSER.
_CLI_PROVIDERS = {"cli", "claude_cli", "agy_cli", "gemini_cli"}
_KEYLESS = {"gcloud-anthropic"} | _CLI_PROVIDERS

# executable name for each named CLI provider (matches code-plus)
_CLI_EXE = {"claude_cli": "claude", "agy_cli": "agy", "gemini_cli": "gemini"}

DEFAULT_MODELS = {
    "gcloud-anthropic": "claude-sonnet-4@20250514",
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-5-mini",
    "cli": "",
    "claude_cli": "",
    "agy_cli": "",
    "gemini_cli": "",
}

_DEFAULT_CLI_COMMAND = "claude --print --output-format json"
# model values that mean "let the CLI pick its own default"
_MODEL_UNSET = {"", "cli", "default", None}


def get_api_key(provider: str) -> Optional[str]:
    """Get API key for provider from environment."""
    env_vars = {
        "anthropic": ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "gcloud-anthropic": ["GOOGLE_APPLICATION_CREDENTIALS"],
    }
    for var_name in env_vars.get(provider, []):
        if var_name in os.environ:
            return os.environ[var_name]
    return None


def validate_model(provider: str, model: str) -> bool:
    """CLI providers accept any model string; API providers are checked against models.json."""
    if provider in _CLI_PROVIDERS:
        return True

    from .helper import get_models

    models = get_models()
    if provider in models:
        return model in models[provider] or "*" in models[provider]
    return False


def resolve_llm_config() -> tuple[str, str]:
    """(provider, model) from env, defaulting to Claude Sonnet on Vertex AI."""
    provider = os.getenv("NEO_LLM_PROVIDER", "gcloud-anthropic").strip()
    model = os.getenv("NEO_LLM_MODEL", "").strip() or DEFAULT_MODELS.get(provider, "cli")
    return provider, model


def build_llm() -> "LLMClient":
    """One-call constructor honouring NEO_LLM_PROVIDER / NEO_LLM_MODEL."""
    provider, model = resolve_llm_config()
    if not validate_model(provider, model):
        raise ValueError(f"unknown model for provider: {provider} / {model}")

    api_key = get_api_key(provider)
    if not api_key and provider not in _KEYLESS:
        raise RuntimeError(f"no API key found for provider '{provider}'")

    return LLMClient(provider, model, api_key or "")


def _render_transcript(messages: List[Dict[str, str]]) -> str:
    """Flatten a role/content message list into a single prompt for a stateless CLI."""
    if len(messages) == 1 and messages[0].get("role") == "user":
        return messages[0].get("content", "")
    parts = []
    for m in messages:
        role = (m.get("role") or "user").upper()
        parts.append(f"[{role}]\n{m.get('content', '')}")
    parts.append("[ASSISTANT]")
    return "\n\n".join(parts)


class _TextResponse:
    """Duck-types the pieces of an Anthropic response the pipeline touches."""

    def __init__(self, text: str):
        self.content = [type("Block", (), {"text": text})()]


class LLMClient:
    """Unified LLM client across API and CLI backends."""

    def __init__(self, provider: str, model: str, api_key: str = ""):
        self.provider = provider.lower()
        self.api_key = api_key
        self.model = model
        self._client = None
        if self.provider not in _CLI_PROVIDERS:
            self._client = self._initialize_client()

    # -- init --------------------------------------------------------------
    def _initialize_client(self):
        print(f"Initializing LLM client for {self.provider}")
        if self.provider == "anthropic":
            import anthropic
            return anthropic.Anthropic(api_key=self.api_key)
        if self.provider == "openai":
            import openai
            return openai.OpenAI(api_key=self.api_key)
        if self.provider == "gcloud-anthropic":
            from anthropic import AnthropicVertex
            location = os.getenv("VERTEX_LOCATION", "us-east5")
            project_id = os.getenv("VERTEX_PROJECT_ID")
            if not project_id:
                raise RuntimeError("VERTEX_PROJECT_ID is not set (required for gcloud-anthropic)")
            return AnthropicVertex(region=location, project_id=project_id)
        raise ValueError(f"Unsupported provider: {self.provider}")

    # -- per-backend calls ----------------------------------------------
    def _anthropic_message(self, full_messages, max_tokens, temperature):
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=full_messages,
        )
        return _TextResponse(response.content[0].text)

    def _openai_message(self, full_messages, max_tokens, temperature):
        model_lower = (self.model or "").lower()
        is_reasoning = model_lower.startswith(("gpt-5", "o1", "o3"))
        kwargs = {"model": self.model, "messages": full_messages}
        if is_reasoning:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
            kwargs["temperature"] = temperature
        response = self._client.chat.completions.create(**kwargs)
        return _TextResponse(response.choices[0].message.content)

    def _resolve_cli_exe(self, name: str) -> str:
        exe = shutil.which(name)
        if not exe and name == "agy":
            local = os.path.expanduser("~/.local/bin/agy")
            if os.path.exists(local):
                exe = local
        if not exe:
            raise RuntimeError(f"{name!r} CLI not found on PATH (provider {self.provider})")
        return exe

    def _build_cli_invocation(self, prompt: str, timeout: int):
        """Return (argv, stdin_text, parser, extra_env) for the configured CLI provider."""
        model = None if (self.model in _MODEL_UNSET) else self.model
        env: Dict[str, str] = {}

        if self.provider == "cli":
            argv = shlex.split(os.getenv("LLM_CLI_COMMAND", _DEFAULT_CLI_COMMAND))
            parser = os.getenv("LLM_CLI_PARSER", "claude-json")
            return argv, prompt, parser, env

        if self.provider == "claude_cli":
            exe = self._resolve_cli_exe("claude")
            argv = [exe, "--print", "--output-format", "json"]
            if model:
                argv += ["--model", model]
            return argv, prompt, "claude-json", env

        if self.provider == "agy_cli":
            exe = self._resolve_cli_exe("agy")
            argv = [exe, "--dangerously-skip-permissions",
                    f"--print={prompt}", "--output-format", "text",
                    "--print-timeout", f"{timeout}s"]
            if model:
                argv += ["--model", model]
            return argv, "", "text", env

        if self.provider == "gemini_cli":
            exe = self._resolve_cli_exe("gemini")
            env["GEMINI_SANDBOX"] = os.getenv("GEMINI_SANDBOX", "false")
            argv = [exe, "--prompt", "", "--output-format", "text"]
            if model:
                argv += ["--model", model]
            return argv, prompt, "text", env

        raise ValueError(f"Unsupported CLI provider: {self.provider}")

    def _cli_message(self, full_messages, max_tokens, temperature):
        timeout = int(os.getenv("LLM_CLI_TIMEOUT", "600"))
        prompt = _render_transcript(full_messages)
        argv, stdin_text, parser, extra_env = self._build_cli_invocation(prompt, timeout)

        run_env = {**os.environ, **extra_env}
        try:
            proc = subprocess.run(argv, input=stdin_text.encode(), capture_output=True,
                                  timeout=timeout, env=run_env)
        except FileNotFoundError:
            raise RuntimeError(f"LLM CLI not found: {argv[0]!r}")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"LLM CLI timed out after {timeout}s")

        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM CLI failed (rc={proc.returncode}): {err[:400]}")

        out = proc.stdout.decode("utf-8", errors="replace")
        text = _parse_claude_jsonl(out) if parser == "claude-json" else out.strip()
        if not text.strip():
            raise RuntimeError("LLM CLI returned no text on stdout")
        return _TextResponse(text)

    # -- public --------------------------------------------------------
    def messages_create(self, history: List[Dict[str, str]], message: List[Dict[str, str]],
                        max_tokens: int = 4000, temperature: float = 0.1, **kwargs) -> Any:
        """Unified call; mimics anthropic.messages.create."""
        full_messages = list(history) + list(message)

        if self.provider in _CLI_PROVIDERS:
            return self._cli_message(full_messages, max_tokens, temperature)
        if self.provider in ("anthropic", "gcloud-anthropic"):
            return self._anthropic_message(full_messages, max_tokens, temperature)
        if self.provider == "openai":
            return self._openai_message(full_messages, max_tokens, temperature)
        raise ValueError(f"Unsupported provider: {self.provider}")

    def get_model_name(self) -> str:
        if self.provider in _CLI_PROVIDERS:
            m = "" if self.model in _MODEL_UNSET else f" {self.model}"
            return f"{self.provider}{m}".strip()
        return self.model


def _parse_claude_jsonl(stdout: str) -> str:
    """Extract assistant text from the Claude CLI's `--output-format json` stream."""
    texts: List[str] = []
    # The CLI emits either JSONL (stream-json) or a single JSON object.
    stripped = stdout.strip()
    candidates = []
    if stripped.startswith("{") and "\n" not in stripped:
        candidates = [stripped]
    else:
        candidates = [ln.strip() for ln in stdout.splitlines() if ln.strip()]

    for line in candidates:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = obj.get("type")
        if t == "assistant":
            for block in obj.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    texts.append(block["text"])
        elif t == "result":
            if isinstance(obj.get("result"), str) and not texts:
                texts.append(obj["result"])
            cost = obj.get("total_cost_usd")
            if cost is not None:
                print(f"[cli turns={obj.get('num_turns', '?')} cost=${cost:.4f}]", file=sys.stderr)
        elif t is None and isinstance(obj.get("content"), str):
            texts.append(obj["content"])  # plain {"content": "..."} shape

    if texts:
        return "\n".join(texts)
    # last resort: the CLI may have printed raw text
    return stripped
