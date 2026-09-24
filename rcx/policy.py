"""Policy — capabilities + hard layer. Distilled from Rad's policy.py (P0).

Soft layer: capabilities with ALLOW/ASK/DENY defaults, per-call decisions.
Hard layer: code-only blocklist (shell/path/URL) that no mode can cross.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ALLOW, ASK, LIMITED, DENY, HARD_DENY = "ALLOW", "ASK", "LIMITED", "DENY", "HARD_DENY"
SCOPE_VIOLATION, UNAUTHORIZED = "SCOPE_VIOLATION", "UNAUTHORIZED"

CAP_READ, CAP_WRITE, CAP_SHELL, CAP_WEB, CAP_VISION, CAP_SPAWN, CAP_MCP = (
    "fs.read", "fs.write", "shell", "web", "vision", "agents.spawn", "mcp")
CAP_PY, CAP_BROWSER, CAP_PACKAGES, CAP_CREDENTIALS, CAP_MEMORY = (
    "py.run", "browser", "packages", "credentials", "memory")

BUILTIN_DEFAULTS: Dict[str, str] = {
    CAP_READ: ALLOW, CAP_WRITE: ASK, CAP_SHELL: ASK, CAP_WEB: ALLOW,
    CAP_VISION: ALLOW, CAP_SPAWN: ASK, CAP_MCP: ASK,
    CAP_PY: ASK, CAP_BROWSER: ALLOW, CAP_PACKAGES: ASK,
    CAP_CREDENTIALS: DENY, CAP_MEMORY: ALLOW,
}

HARD_SHELL = [
    r"\bsudo\b", r"\brm\s+(-[a-z]*[rf][a-z]*\s+)+(/|~|\$HOME)(\s|$)",
    r"\bmkfs", r"\bdd\s+if=", r":\(\)\s*\{", r"\bshutdown\b", r"\breboot\b",
    r"curl[^|]*\|\s*(ba)?sh", r"wget[^|]*\|\s*(ba)?sh", r">\s*/dev/sd",
    r"\.rcx/keys", r"~/\.ssh|/\.ssh/", r"/etc/shadow",
    r"\bgit\s+push\s+(-f|--force)\b",
]
HARD_PATH_PARTS = ("/.rcx/keys", "/.ssh/", "/etc/shadow", ".git-credentials",
                   ".netrc", ".aws/credentials", ".gnupg/")
HARD_PATH_NAMES = ("keys.env", "vault.enc", "id_rsa", "id_ed25519", ".netrc")
HARD_HOSTS = (r"^localhost$", r"^127\.", r"^0\.0\.0\.0$", r"^10\.", r"^192\.168\.",
              r"^172\.(1[6-9]|2\d|3[01])\.", r"^169\.254\.", r"^\[?::1\]?$",
              r"^metadata\.google\.internal$")


def hard_check_shell(cmd: str) -> Optional[str]:
    for pat in HARD_SHELL:
        if re.search(pat, cmd, re.I):
            return f"shell pattern {pat!r}"
    return None


def hard_check_path(p: Path) -> Optional[str]:
    s = str(p).replace("\\", "/")
    for part in HARD_PATH_PARTS:
        if part in s:
            return f"protected path {part}"
    if p.name in HARD_PATH_NAMES:
        return f"protected file {p.name}"
    return None


def hard_check_url(url: str) -> Optional[str]:
    from urllib.parse import urlparse
    try:
        u = urlparse(url)
    except Exception:
        return "unparseable url"
    if u.scheme not in ("http", "https"):
        return f"only http(s) urls are allowed, got {u.scheme or '?'}"
    host = (u.hostname or "").lower()
    if not host:
        return "no host"
    for pat in HARD_HOSTS:
        if re.match(pat, host):
            return f"private/loopback host {host}"
    if u.username or u.password:
        return "credentials in url"
    return None


@dataclass
class Decision:
    effect: str
    reason: str
    by: str = "default"

    @property
    def denied(self) -> bool:
        return self.effect in (DENY, HARD_DENY, SCOPE_VIOLATION, UNAUTHORIZED)


class Policy:
    """Per-call capability decisions. Hard layer always wins."""

    def __init__(self, defaults: Optional[Dict[str, str]] = None) -> None:
        self.defaults = dict(BUILTIN_DEFAULTS)
        if defaults:
            self.defaults.update(defaults)
        self.rules: List[Dict[str, Any]] = []

    def default_for(self, cap: str) -> str:
        return self.defaults.get(cap, ASK)

    def decide(self, capability: str, resource: str = "") -> Decision:
        # hard layer first — no mode crosses it
        if capability == CAP_SHELL and resource:
            hit = hard_check_shell(resource)
            if hit:
                return Decision(HARD_DENY, hit, by="hard")
        if capability in (CAP_READ, CAP_WRITE) and resource:
            hit = hard_check_path(Path(resource))
            if hit:
                return Decision(HARD_DENY, hit, by="hard")
        if capability == CAP_WEB and resource:
            hit = hard_check_url(resource)
            if hit:
                return Decision(DENY, hit, by="hard")
        if capability == CAP_CREDENTIALS:
            return Decision(DENY, "credentials never model-driven", by="builtin")
        return Decision(self.default_for(capability), "default", by="default")
