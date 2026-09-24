"""Minimal home — all RadConnectome state lives in one folder (~/.rcx).

Human-readable JSON/Markdown only. Nothing opaque.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULTS: Dict[str, Any] = {
    "workspace": None,
    "auto": False,
    "max_plan_tasks": 16,
    "max_tool_calls": 60,
    "tool_router": "existing",   # Needle OFF, always
    "memory.evolve": False,
}


def _read_json(path: Path, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    try:
        tmp.replace(path)
    except OSError:
        time.sleep(0.02)
        tmp.replace(path)


class RcxHome:
    """Filesystem home of the agent. Test-friendly via RCX_HOME env var."""

    def __init__(self, root: Optional[str] = None) -> None:
        self.root = Path(root or os.environ.get("RCX_HOME") or (Path.home() / ".rcx"))
        self._make_tree()
        self.cfg = self.load_config()

    def _make_tree(self) -> None:
        for sub in ("", "memory", "connectome", "tribe", "world", "skills",
                    "objectives", "workspace", "logs"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    @property
    def config_path(self) -> Path:
        return self.root / "rcx.json"

    @property
    def memory_dir(self) -> Path:
        return self.root / "memory"

    def load_config(self) -> Dict[str, Any]:
        cfg = dict(DEFAULTS)
        cfg.update(_read_json(self.config_path, {}))
        return cfg

    def save_config(self) -> None:
        _write_json(self.config_path, self.cfg)

    def update(self, **kw: Any) -> None:
        for k, v in kw.items():
            if k in DEFAULTS:
                self.cfg[k] = v
        self.save_config()

    def workspace(self) -> Path:
        ws = self.cfg.get("workspace")
        if ws:
            return Path(str(ws)).expanduser()
        p = self.root / "workspace"
        p.mkdir(parents=True, exist_ok=True)
        return p
