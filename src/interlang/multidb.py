"""
A :class:`~duck_db.create_duckdb.CallGraphDatabase`-compatible facade over the
per-service call-graph databases of a polyglot application.

The validator holds a single ``db`` object and asks it to resolve function
requests like ``name@services/<svc>/path/File.java:42`` or a bare
``ClassName.method``.  This facade routes each request to the right per-service
DuckDB and re-prefixes returned ``file_path`` values with ``services/<svc>/`` so
that source extraction against the global (symlink-farm) source root resolves.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from duck_db.create_duckdb import CallGraphDatabase

_SVC_PREFIX = re.compile(r"services/([^/]+)/")


class MultiServiceCallGraph:
    def __init__(self, service_dbs: Dict[str, Path], service_roots: Dict[str, Path]):
        """
        service_dbs   : service name -> path to that service's callgraph.duckdb
        service_roots : service name -> that service's real source root
        """
        self._dbs: Dict[str, CallGraphDatabase] = {}
        self._roots = {k: Path(v) for k, v in service_roots.items()}
        for name, path in service_dbs.items():
            p = Path(path)
            if p.exists():
                try:
                    self._dbs[name] = CallGraphDatabase(p)
                except Exception as exc:  # pragma: no cover
                    print(f"[multidb] could not open {name} db {p}: {exc}")

    # -- API expected by IterativeFlowValidator -----------------------------
    def get_function_by_identifier(self, identifier: str, source_root: Optional[Path] = None) -> List[Dict]:
        svc = self._service_of(identifier)
        if svc and svc in self._dbs:
            bare = identifier.replace(f"services/{svc}/", "")
            rows = self._dbs[svc].get_function_by_identifier(bare, source_root=self._roots.get(svc))
            return [self._tag(r, svc) for r in rows]

        # unknown service: try every service DB, aggregate
        out: List[Dict] = []
        for name, db in self._dbs.items():
            try:
                rows = db.get_function_by_identifier(identifier, source_root=self._roots.get(name))
            except Exception:
                rows = []
            out.extend(self._tag(r, name) for r in rows)
        return out

    def get_function_source_code(self, function_info: Dict, source_root: Path) -> Optional[str]:
        svc = function_info.get("_service")
        if svc and svc in self._dbs:
            info = dict(function_info)
            # undo the display prefix so it resolves against the service root
            if info.get("file_path", "").startswith(f"services/{svc}/"):
                info["file_path"] = info["file_path"][len(f"services/{svc}/"):]
            return self._dbs[svc].get_function_source_code(info, self._roots.get(svc, source_root))
        # fall back to the first db that can produce something
        for db, root in ((d, self._roots.get(n)) for n, d in self._dbs.items()):
            try:
                code = db.get_function_source_code(function_info, root or source_root)
                if code:
                    return code
            except Exception:
                continue
        return None

    def close(self):
        for db in self._dbs.values():
            try:
                db.close()
            except Exception:
                pass

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _service_of(identifier: str) -> Optional[str]:
        m = _SVC_PREFIX.search(identifier or "")
        return m.group(1) if m else None

    @staticmethod
    def _tag(row: Dict, svc: str) -> Dict:
        row = dict(row)
        row["_service"] = svc
        fp = row.get("file_path", "")
        if fp and not fp.startswith(f"services/{svc}/"):
            row["file_path"] = f"services/{svc}/{fp}"
        return row
