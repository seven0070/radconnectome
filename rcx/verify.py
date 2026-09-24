"""Verifier — never trust a declaration of completion. Distilled P0.

Levels, cheapest first:
  1. check   — machine-checkable Checks (files, shell, json, regex)
  2. artifact — produced files still exist and are non-empty
  3. evidence — claims backed by recorded observations (advisory, machine=False)

Result is a structured dict, never a bare bool.
LLM opinion is never VERIFIED.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

VERIFIED = "VERIFIED"
FAILED = "FAILED"
UNVERIFIED = "UNVERIFIED"   # no machine checks available — not success


@dataclass
class Check:
    kind: str
    args: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


class Verifier:
    def __init__(self, workspace: Path, shell_timeout: int = 60) -> None:
        self.ws = workspace
        self.shell_timeout = shell_timeout

    # ------------------------------------------------------------ checks
    def run_check(self, c: Check, reply: str = "") -> Dict[str, Any]:
        a = c.args
        base = {"level": "check", "kind": c.kind,
                "detail": c.description or json.dumps(a)[:120]}
        try:
            if c.kind == "file_exists":
                p = self._p(a["path"])
                return {**base, "ok": p.exists(), "detail": f"{p} exists={p.exists()}"}
            if c.kind == "file_min_bytes":
                p = self._p(a["path"])
                n = p.stat().st_size if p.exists() else -1
                return {**base, "ok": n >= int(a.get("n", 1)),
                        "detail": f"{p} size={n} min={a.get('n', 1)}"}
            if c.kind == "file_contains":
                p = self._p(a["path"])
                txt = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
                ok = str(a["text"]) in txt
                return {**base, "ok": ok, "detail": f"{p} contains={ok}"}
            if c.kind == "file_equals":
                p = self._p(a["path"])
                got = p.read_text(encoding="utf-8", errors="replace").strip() if p.exists() else None
                ok = got == str(a.get("text", "")).strip()
                return {**base, "ok": ok, "detail": f"{p} equals={ok}"}
            if c.kind == "file_absent":
                p = self._p(a["path"])
                return {**base, "ok": not p.exists(), "detail": f"{p} absent={not p.exists()}"}
            if c.kind == "dir_exists":
                p = self._p(a["path"])
                return {**base, "ok": p.is_dir(), "detail": f"{p} is_dir={p.is_dir()}"}
            if c.kind == "json_valid":
                p = self._p(a["path"])
                try:
                    json.loads(p.read_text(encoding="utf-8"))
                    return {**base, "ok": True, "detail": f"{p} is valid JSON"}
                except Exception as e:
                    return {**base, "ok": False, "detail": f"{p} invalid JSON: {e}"}
            if c.kind == "json_field":
                p = self._p(a["path"])
                doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
                if doc is None:
                    return {**base, "ok": False, "detail": f"{p} missing"}
                node = doc
                for part in str(a["key"]).split("."):
                    if isinstance(node, dict) and part in node:
                        node = node[part]
                    else:
                        return {**base, "ok": False, "detail": f"{p}: key '{a['key']}' not found"}
                if "equals" in a:
                    ok = node == a["equals"]
                    return {**base, "ok": ok, "detail": f"{p}: equals={ok}"}
                return {**base, "ok": bool(node), "detail": f"{p}: truthy={bool(node)}"}
            if c.kind == "shell_ok":
                code, out = self._sh(a["command"])
                return {**base, "ok": code == 0, "detail": f"exit={code} {out[-120:]}"}
            if c.kind == "shell_output":
                code, out = self._sh(a["command"])
                ok = str(a.get("contains", "")) in out
                return {**base, "ok": ok, "detail": f"exit={code} contains={ok}"}
            if c.kind == "reply_matches":
                ok = re.search(a["pattern"], reply or "", re.I | re.S) is not None
                return {**base, "ok": ok, "detail": f"reply matches={ok}"}
            return {**base, "ok": False, "detail": f"unknown check kind {c.kind}"}
        except Exception as e:
            return {**base, "ok": False, "detail": f"check error: {e}"}

    def verify(self, checks: List[Check], reply: str = "",
               artifacts: Optional[List[str]] = None) -> Dict[str, Any]:
        """Verify a list of checks + artifact paths. Returns structured verdict."""
        results = [self.run_check(c, reply=reply) for c in checks]
        for loc in artifacts or []:
            p = self._p(loc)
            ok = p.exists() and p.stat().st_size > 0
            results.append({"level": "artifact", "kind": "file_nonempty",
                            "ok": ok, "detail": str(p)})
        machine = [r for r in results if r.get("machine", True)]
        if any(not r["ok"] for r in machine):
            status = FAILED
        elif any(r["level"] == "check" for r in machine):
            status = VERIFIED
        elif any(r["level"] == "artifact" for r in results):
            status = VERIFIED
        else:
            status = UNVERIFIED
        return {"status": status, "results": results,
                "summary": "; ".join(f"{'✓' if r['ok'] else '✗'} {r['kind']}" for r in results)}

    # ------------------------------------------------------------ helpers
    def _p(self, path: str) -> Path:
        p = Path(path).expanduser()
        return p if p.is_absolute() else self.ws / p

    def _sh(self, cmd: str):
        import shutil
        if os.name == "nt":
            sh_bin = shutil.which("sh")
            shell = [sh_bin, "-c"] if sh_bin else ["cmd", "/c"]
        else:
            shell = ["sh", "-c"]
        try:
            pr = subprocess.run(shell + [cmd], cwd=str(self.ws), capture_output=True,
                                text=True, timeout=self.shell_timeout)
            return pr.returncode, (pr.stdout or "") + (pr.stderr or "")
        except subprocess.TimeoutExpired:
            return 124, "[timeout]"
