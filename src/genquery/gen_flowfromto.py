"""
Fill ``queries/<lang>/templateFlowFromTo.ql`` with a concrete (from, to) pair so
``Qflow`` can issue a real on-demand taint query (paper §4.1, "Flow Tracking").

All six languages have a template; when one is missing ``Qflow`` falls back to
the approximate mode that matches against already-computed flows.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from common.helper import get_query_dir, get_query_tmp_dir, san_appname

_SUPPORTED = {"java", "python", "go", "javascript", "csharp", "cpp"}


def _to_codeql_regex(term: str) -> str:
    """A user term ('update_role', 'update.*', 'request') -> a CodeQL name regex."""
    term = term.strip()
    if not term:
        return ".*"
    # already a regex?
    if re.search(r"[.*+?()\[\]|\\^$]", term):
        return term
    # bare identifier -> case-insensitive substring match
    return f"(?i).*{re.escape(term)}.*"


def gen_flowfromto_query(language: str, appname: str, source: str, sink: str) -> Optional[Path]:
    language = language.lower()
    if language not in _SUPPORTED:
        return None
    template = get_query_dir() / language / "templateFlowFromTo.ql"
    if not template.exists():
        return None

    body = (template.read_text()
            .replace("{{FROM}}", _to_codeql_regex(source))
            .replace("{{TO}}", _to_codeql_regex(sink)))

    tag = re.sub(r"[^A-Za-z0-9]+", "", f"{source}_{sink}")[:40] or "x"
    out = get_query_tmp_dir(language) / f"{san_appname(appname)}_qflow_{tag}.ql"
    out.write_text(body)
    return out
