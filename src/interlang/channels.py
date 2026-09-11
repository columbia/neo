"""
Channel identifiers and cross-language matching.

A *channel identifier* is the string that names an inter-service communication
target: an HTTP URL/path, a Kafka/RabbitMQ topic, a gRPC ``Service/Method``,
etc.  The engine matches an outbound call's channel against the inbound
endpoints of the other services to draw a cross-service edge (Algorithm 1,
phase 2).

Matching is deliberately tolerant: microservice demos routinely hardcode
``http://localhost:5000/foo`` rather than a service name, so host is only a
tie-breaker while the *path* (with ``{id}`` / ``:id`` / ``<id>`` templating
collapsed to a wildcard) carries the match.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urlsplit

HTTP = "http"
KAFKA = "kafka"
RABBITMQ = "rabbitmq"
GRPC = "grpc"
WEBSOCKET = "websocket"
GRAPHQL = "graphql"
DUBBO = "dubbo"
UNKNOWN = "unknown"

_MQ_KINDS = {KAFKA, RABBITMQ}
_HTTP_LIKE = {HTTP, WEBSOCKET, GRAPHQL}

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}
_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}

# path-parameter syntaxes across frameworks:  {id}  :id  <id>  <int:id>  ${id}  [id]
_PARAM_RE = re.compile(r"^(\{.*\}|:.+|<.*>|\$\{.*\}|\[.*\]|\*+|__[A-Z_]+__)$")


def _norm_path(path: str) -> str:
    if not path:
        return "/"
    path = path.split("?", 1)[0].split("#", 1)[0].strip()
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


def _segments(path: str) -> List[str]:
    p = _norm_path(path)
    return [s for s in p.split("/") if s != ""]


def _seg_is_wild(seg: str) -> bool:
    return bool(_PARAM_RE.match(seg))


@dataclass
class Channel:
    """Normalized inter-service target extracted from an outbound call."""

    kind: str = UNKNOWN
    method: Optional[str] = None          # HTTP verb, upper-case, if known
    host: Optional[str] = None            # lower-case host[:port] if a URL was seen
    path: str = "/"                       # normalized path (HTTP) — "/" if none
    topic: Optional[str] = None           # queue/topic name (MQ) or Service/Method (gRPC)
    raw: str = ""                         # original string as found in source

    @classmethod
    def parse(cls, raw: str, kind: str = UNKNOWN, method: Optional[str] = None) -> "Channel":
        raw = (raw or "").strip().strip("\"'")
        m = (method or "").strip().upper() or None
        if m not in _HTTP_METHODS:
            m = None

        low = raw.lower()
        if kind in _MQ_KINDS or (kind == UNKNOWN and _looks_like_topic(raw)):
            return cls(kind=(kind if kind in _MQ_KINDS else KAFKA), topic=raw, raw=raw, method=m)

        if kind == GRPC or (kind == UNKNOWN and _looks_like_grpc(raw)):
            return cls(kind=GRPC, topic=raw.lstrip("/"), raw=raw, method=m)

        # HTTP-ish: URL or bare path
        if "://" in low:
            u = urlsplit(raw)
            return cls(
                kind=(kind if kind in _HTTP_LIKE else HTTP),
                method=m,
                host=(u.netloc.lower() or None),
                path=_norm_path(u.path or "/"),
                raw=raw,
            )
        if raw.startswith("/") or kind in _HTTP_LIKE:
            return cls(kind=(kind if kind in _HTTP_LIKE else HTTP), method=m, path=_norm_path(raw), raw=raw)

        # last resort: treat as opaque topic-like token
        return cls(kind=UNKNOWN, topic=raw or None, path="/", raw=raw, method=m)

    @property
    def host_is_local(self) -> bool:
        if not self.host:
            return True
        h = self.host.split(":", 1)[0]
        return h in _LOCAL_HOSTS or h == ""

    def to_dict(self) -> dict:
        return {
            "kind": self.kind, "method": self.method, "host": self.host,
            "path": self.path, "topic": self.topic, "raw": self.raw,
        }


@dataclass
class Endpoint:
    """Normalized inbound endpoint of a service."""

    service: str
    kind: str = HTTP
    method: Optional[str] = None          # HTTP verb, upper-case
    path: str = "/"
    topic: Optional[str] = None
    handler_id: str = ""                  # function_id:  name@file:line
    handler_name: str = ""
    file: str = ""
    line: int = 0
    raw: str = ""

    def to_dict(self) -> dict:
        return {
            "service": self.service, "kind": self.kind, "method": self.method,
            "path": self.path, "topic": self.topic, "handler_id": self.handler_id,
            "handler_name": self.handler_name, "file": self.file, "line": self.line,
            "raw": self.raw,
        }


def _looks_like_topic(raw: str) -> bool:
    if not raw or "/" in raw or " " in raw or raw.startswith("/"):
        return False
    return bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,}$", raw)) and ("." in raw or "-" in raw or "_" in raw)


def _looks_like_grpc(raw: str) -> bool:
    # e.g. "user.UserService/SetUserRole" or "/user.UserService/SetUserRole"
    return bool(re.match(r"^/?[A-Za-z_][\w.]*\.[A-Za-z_]\w*/[A-Za-z_]\w*$", raw))


def _strip_prefix(segs: List[str], prefix: Optional[str]) -> List[str]:
    pre = _segments(prefix) if prefix else []
    if pre and segs[: len(pre)] == pre:
        return segs[len(pre):]
    return segs


def _path_score(out_segs: List[str], ep_segs: List[str]) -> float:
    """
    Score how well an endpoint path template covers the tail of an outbound path.

    Returns 0.0 for "no match".  A full same-length match with literal segments
    scores highest; a suffix match scores a bit lower; every wildcard alignment
    costs a little.
    """
    if not ep_segs:
        return 0.5 if not out_segs else 0.0

    # endpoint path must align with the tail of the outbound path
    if len(ep_segs) > len(out_segs):
        return 0.0
    tail = out_segs[len(out_segs) - len(ep_segs):]

    literal_hits = 0
    for o, e in zip(tail, ep_segs):
        if _seg_is_wild(e) or _seg_is_wild(o):
            continue
        if o.lower() != e.lower():
            return 0.0
        literal_hits += 1

    if literal_hits == 0 and any(not _seg_is_wild(e) for e in ep_segs):
        return 0.0  # endpoint had literal segments but none matched

    base = 1.0 if len(tail) == len(out_segs) else 0.75          # exact vs suffix
    coverage = literal_hits / max(len(ep_segs), 1)
    return round(base * (0.5 + 0.5 * coverage), 4)


def match_channel(
    channel: Channel,
    endpoints: List[Endpoint],
    service_tokens: Optional[List[str]] = None,
    base_path: Optional[str] = None,
    min_score: float = 0.4,
) -> List[Tuple[Endpoint, float]]:
    """
    Rank a service's *endpoints* by how well they receive *channel*.

    ``service_tokens`` are the target service's name/alias tokens; a host that
    matches one of them boosts the score, a host that names a *different* known
    service is not penalised here (the caller filters per-service already).
    """
    service_tokens = [t.lower() for t in (service_tokens or [])]
    results: List[Tuple[Endpoint, float]] = []

    for ep in endpoints:
        score = 0.0

        if channel.kind in _MQ_KINDS or ep.kind in _MQ_KINDS:
            if ep.kind in _MQ_KINDS and channel.topic and ep.topic:
                if channel.topic.lower() == ep.topic.lower():
                    score = 1.0
        elif channel.kind == GRPC or ep.kind == GRPC:
            if ep.kind == GRPC and channel.topic and ep.topic:
                a = channel.topic.lower().lstrip("/")
                b = ep.topic.lower().lstrip("/")
                if a == b or a.endswith("/" + b.split("/")[-1]):
                    score = 1.0 if a == b else 0.7
        else:
            # HTTP-like
            out_segs = _strip_prefix(_segments(channel.path), base_path)
            ep_segs = _strip_prefix(_segments(ep.path), base_path)
            host = (channel.host or "").lower()
            host_hit = bool(host) and any(tok and tok in host for tok in service_tokens)

            score = _path_score(out_segs, ep_segs)
            if score > 0.0:
                if channel.method and ep.method and channel.method != ep.method:
                    score *= 0.35
                if not channel.host_is_local and host_hit:
                    score = min(1.0, score + 0.15)
            elif not out_segs and host_hit and ep.kind in _HTTP_LIKE:
                # host-only channel (hardcoded base URL, path built dynamically):
                # the host names this service, so it's a plausible target.
                score = 0.6
                if channel.method and ep.method and channel.method != ep.method:
                    score *= 0.5

        if score >= min_score:
            results.append((ep, round(score, 4)))

    results.sort(key=lambda t: t[1], reverse=True)
    return results
