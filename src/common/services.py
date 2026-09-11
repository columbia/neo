"""
Multi-service / polyglot application model.

The historical pipeline assumes one application == one language == one CodeQL
database (``codebases/<app>`` + ``databases/<app>``).  Real microservice systems
are polyglot: a single request crosses several services written in different
languages.  This module introduces a light-weight *manifest* that ties a set of
existing single-language apps together into one logical application so the
cross-service engine (``src/interlang``) can stitch their data flows.

Manifest file: ``codebases/<name>/neo.services.yaml`` (or any path passed
explicitly).  Schema::

    name: role-switch-demo            # optional, defaults to parent dir name
    services:
      - name: user-profile           # logical service name (required)
        app: userprofile-java        # existing codebases/ + databases/ key
        role: gateway                # gateway | internal   (default: internal)
        aliases: ["userprofile", "localhost:8080"]   # host/base-url tokens
        base_path: /api              # url prefix stripped before route matching
      - name: user-mgmt
        app: usermgmt-python
        role: internal
        aliases: ["localhost:5000"]

Instead of ``app:`` a service may give explicit ``source:`` / ``database:``
paths (absolute, or relative to the manifest directory) for monorepo layouts.

If no manifest is found the application degrades to a single service wrapping
the app as-is, so every existing call site keeps working unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

# service names become path segments (services/<name>/…) and appear in regexes
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

from common.helper import (
    get_app_database_dir,
    get_app_source_dir,
    get_codebases_dir,
    get_database_language,
    register_app_dirs,
)

MANIFEST_NAMES = ("neo.services.yaml", "neo.services.yml", "services.yaml")

GATEWAY_ROLE = "gateway"
INTERNAL_ROLE = "internal"


@dataclass
class Service:
    """One language-homogeneous service inside a polyglot application."""

    name: str
    role: str = INTERNAL_ROLE
    app: Optional[str] = None
    source_dir: Optional[Path] = None
    database_dir: Optional[Path] = None
    aliases: List[str] = field(default_factory=list)
    base_path: Optional[str] = None
    _language: Optional[str] = None

    # -- derived ----------------------------------------------------------------
    @property
    def key(self) -> str:
        """Stable identifier used for status files."""
        return self.app or self.name

    @property
    def workdir(self) -> Path:
        """Per-service work directory (mirrors the single-app ``neo-workdir``)."""
        return Path(self.source_dir) / "neo-workdir"

    @property
    def duckdb_path(self) -> Path:
        return self.workdir / "callgraph.duckdb"

    @property
    def language(self) -> str:
        if self._language is None:
            self._language = get_database_language(self.database_dir)
        return self._language

    @property
    def is_gateway(self) -> bool:
        return self.role == GATEWAY_ROLE

    def match_tokens(self) -> List[str]:
        """Lower-cased tokens an outbound URL/host may contain to target this service."""
        toks = {self.name.lower(), self.key.lower()}
        toks.update(a.lower() for a in self.aliases)
        toks.discard("")
        return sorted(toks)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "key": self.key,
            "role": self.role,
            "language": self._safe_language(),
            "source_dir": str(self.source_dir),
            "database_dir": str(self.database_dir),
            "aliases": self.aliases,
            "base_path": self.base_path,
        }

    def _safe_language(self) -> Optional[str]:
        try:
            return self.language
        except Exception:
            return self._language


@dataclass
class Application:
    name: str
    services: List[Service]
    manifest_path: Optional[Path] = None

    @property
    def is_multi_service(self) -> bool:
        return len(self.services) > 1

    def gateway_services(self) -> List[Service]:
        gws = [s for s in self.services if s.is_gateway]
        return gws or self.services  # if nobody is marked, every service is an entry

    def get(self, name: str) -> Optional[Service]:
        for s in self.services:
            if name in (s.name, s.key):
                return s
        return None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "multi_service": self.is_multi_service,
            "services": [s.to_dict() for s in self.services],
        }


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def _resolve_dir(value: str, base: Path) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else (base / p)


def _service_from_entry(entry: dict, manifest_dir: Path, index: int) -> Service:
    if not isinstance(entry, dict):
        raise ValueError(f"service entry #{index} must be a mapping, got {type(entry).__name__}")

    app = entry.get("app")
    name = entry.get("name") or app
    if not name:
        raise ValueError(f"service entry #{index} needs a 'name' or 'app'")
    if not _NAME_RE.match(str(name)):
        raise ValueError(
            f"service name {name!r} is invalid — use letters/digits/._- (it becomes a "
            f"path segment 'services/<name>/…')"
        )

    src = entry.get("source")
    db = entry.get("database")
    if app:
        source_dir = _resolve_dir(src, manifest_dir) if src else get_app_source_dir(app)
        database_dir = _resolve_dir(db, manifest_dir) if db else get_app_database_dir(app)
    else:
        if not src or not db:
            raise ValueError(
                f"service '{name}' must set 'app', or both 'source' and 'database'"
            )
        source_dir = _resolve_dir(src, manifest_dir)
        database_dir = _resolve_dir(db, manifest_dir)

    role = (entry.get("role") or INTERNAL_ROLE).strip().lower()
    if role not in (GATEWAY_ROLE, INTERNAL_ROLE):
        raise ValueError(f"service '{name}': role must be '{GATEWAY_ROLE}' or '{INTERNAL_ROLE}'")

    aliases = entry.get("aliases") or []
    if isinstance(aliases, str):
        aliases = [aliases]

    return Service(
        name=str(name),
        role=role,
        app=app,
        source_dir=Path(source_dir),
        database_dir=Path(database_dir),
        aliases=[str(a) for a in aliases],
        base_path=entry.get("base_path"),
        _language=(entry.get("language") or None),
    )


def _load_manifest(manifest_path: Path) -> Application:
    data = yaml.safe_load(manifest_path.read_text()) or {}
    entries = data.get("services")
    if not entries:
        raise ValueError(f"manifest {manifest_path} has no 'services' list")

    manifest_dir = manifest_path.parent
    services = [_service_from_entry(e, manifest_dir, i) for i, e in enumerate(entries)]

    names = [s.name for s in services]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"manifest {manifest_path} has duplicate service names: {sorted(dupes)}")

    # If nobody declared a role, the first service is treated as the entry point.
    if not any(s.is_gateway for s in services):
        services[0].role = GATEWAY_ROLE

    # Make each service's key resolvable through the get_app_* helpers even when
    # it was declared by explicit source:/database: paths (no codebases/<key>).
    for s in services:
        register_app_dirs(s.key, s.source_dir, s.database_dir)

    name = data.get("name") or manifest_dir.name
    return Application(name=str(name), services=services, manifest_path=manifest_path)


def find_manifest(app_or_path: str) -> Optional[Path]:
    """Locate a manifest for *app_or_path* (an app name, a dir, or a file)."""
    p = Path(app_or_path).expanduser()
    if p.is_file():
        return p
    if p.is_dir():
        for n in MANIFEST_NAMES:
            if (p / n).is_file():
                return p / n
    # bare app name -> codebases/<name>/<manifest>
    cand_dir = get_codebases_dir() / app_or_path
    if cand_dir.is_dir():
        for n in MANIFEST_NAMES:
            if (cand_dir / n).is_file():
                return cand_dir / n
    return None


def load_application(app_or_path: str) -> Application:
    """
    Resolve *app_or_path* to an :class:`Application`.

    Order: explicit manifest file/dir  ->  ``codebases/<app>/neo.services.yaml``
    ->  single-service fallback wrapping the app as its own gateway service.
    """
    manifest = find_manifest(app_or_path)
    if manifest is not None:
        return _load_manifest(manifest)

    # single-service fallback
    app = Path(app_or_path).name
    svc = Service(
        name=app,
        role=GATEWAY_ROLE,
        app=app,
        source_dir=get_app_source_dir(app),
        database_dir=get_app_database_dir(app),
    )
    return Application(name=app, services=[svc], manifest_path=None)
