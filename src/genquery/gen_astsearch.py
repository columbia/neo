"""
Fill ``queries/<lang>/astSearch.ql`` with a concrete op so ``Qast`` can locate
AST constructs beyond call/method (paper §4.1, "AST-based Lookup").

All six languages have a template; without one ``Qast`` reports the op as
unsupported.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from common.helper import get_query_dir, get_query_tmp_dir, san_appname

_SUPPORTED = {"java", "python", "go", "javascript", "csharp", "cpp"}

# ops the templates understand
OPS = {
    "call", "method", "field_access", "assignment", "return",
    "string_literal", "conditional", "catch", "parameter", "new",
}
_ALIASES = {
    "invocation": "call", "callsite": "call", "function": "method",
    "callable": "method", "attribute": "field_access", "field": "field_access",
    "assign": "assignment", "if": "conditional", "branch": "conditional",
    "except": "catch", "try": "catch", "param": "parameter",
    "string": "string_literal", "str": "string_literal", "constructor": "new",
}


def normalize_op(op: str) -> Optional[str]:
    op = (op or "").strip().lower()
    op = _ALIASES.get(op, op)
    return op if op in OPS else None


def gen_astsearch_query(language: str, appname: str, op: str) -> Optional[Path]:
    language = language.lower()
    norm = normalize_op(op)
    if language not in _SUPPORTED or norm is None:
        return None
    template = get_query_dir() / language / "astSearch.ql"
    if not template.exists():
        return None
    body = template.read_text().replace("{{OP}}", norm)
    out = get_query_tmp_dir(language) / f"{san_appname(appname)}_qast_{norm}.ql"
    out.write_text(body)
    return out
