"""Adaptive thinking budget — spend compute where difficulty demands it.

Per task: estimate difficulty band (trivial/normal/hard) from the text,
allocate attempts + tool budget accordingly, track what was actually spent
per VERIFIED node, and adapt: bands that keep failing earn +1 attempt (capped).

This is the thinking-optimal insight (MSR 2025): longer isn't better —
*matched* effort is. The report metric is tools-per-verified-task: down is
better, and the trend is the proof.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List

from rcx.home import RcxHome

BANDS = ("trivial", "normal", "hard")

# base budgets per band: (max_attempts, max_tools). Harder >= easier, always.
BASE_BUDGETS: Dict[str, Dict[str, int]] = {
    "trivial": {"attempts": 1, "tools": 5},
    "normal": {"attempts": 2, "tools": 15},
    "hard": {"attempts": 3, "tools": 30},
}
MAX_ATTEMPTS_CAP = 5  # adaptation never exceeds this, whatever history says
ADAPT_AFTER = 3       # need this many samples before adapting a band

_HARD_SIGNS = re.compile(
    r"\b(refactor|migrate|redesign|debug|race|deadlock|performance|security|"
    r"distributed|concurrent|architect|verify end.to.end|across \w+ files?)\b", re.I)
_TRIVIAL_SIGNS = re.compile(r"^(write|create|list|show|print|echo)\b.{0,60}$", re.I)


def estimate(text: str) -> str:
    """Difficulty band from text signals. Documented heuristic, not magic."""
    t = (text or "").strip()
    if not t:
        return "trivial"
    if _HARD_SIGNS.search(t) or len(t.split()) > 40:
        return "hard"
    if _TRIVIAL_SIGNS.match(t) and len(t.split()) <= 12:
        return "trivial"
    return "normal"


class ThinkingBudget:
    """Allocator + tracker + adaptation. Persisted per-band stats."""

    def __init__(self, home: RcxHome) -> None:
        self.home = home
        self.path = home.root / "thinking.json"
        try:
            import json as _j
            raw = self.path.read_text(encoding="utf-8")
            self.bands: Dict[str, Any] = _j.loads(raw).get("bands", {})
        except Exception:
            self.bands = {}
        for b in BANDS:
            self.bands.setdefault(b, {"tasks": 0, "verified": 0, "tools": 0,
                                      "bonus_attempts": 0})

    def save(self) -> None:
        from rcx.home import _write_json
        _write_json(self.path, {"updated": time.time(), "bands": self.bands})

    def allocate(self, text: str) -> Dict[str, Any]:
        """Budget for a task: base + earned bonus, capped. Never invents."""
        band = estimate(text)
        base = BASE_BUDGETS[band]
        bonus = min(MAX_ATTEMPTS_CAP - base["attempts"],
                    self.bands[band]["bonus_attempts"])
        return {"band": band, "attempts": base["attempts"] + bonus,
                "tools": base["tools"], "cap": MAX_ATTEMPTS_CAP}

    def record(self, text: str, tools_used: int, verified: bool) -> Dict[str, Any]:
        """Log one finished task; adapt the band when evidence suffices."""
        band = estimate(text)
        st = self.bands[band]
        st["tasks"] += 1
        st["tools"] += max(0, tools_used)
        if verified:
            st["verified"] += 1
        # adapt: sustained failure earns one more attempt (capped)
        if st["tasks"] >= ADAPT_AFTER:
            rate = st["verified"] / st["tasks"]
            want = 1 if rate < 0.5 else 0
            st["bonus_attempts"] = min(MAX_ATTEMPTS_CAP - BASE_BUDGETS[band]["attempts"],
                                       want)
        self.save()
        return {"band": band, **dict(st)}

    def report(self) -> Dict[str, Any]:
        """Cost-per-verified per band + trend. Down is better."""
        out: Dict[str, Any] = {"bands": {}, "overall_tools_per_verified": None}
        tot_tools = tot_ver = 0
        for b in BANDS:
            st = self.bands[b]
            cpv = st["tools"] / st["verified"] if st["verified"] else None
            out["bands"][b] = {"tasks": st["tasks"], "verified": st["verified"],
                               "tools": st["tools"], "tools_per_verified": cpv,
                               "attempts": BASE_BUDGETS[b]["attempts"] + st["bonus_attempts"]}
            tot_tools += st["tools"]
            tot_ver += st["verified"]
        out["overall_tools_per_verified"] = tot_tools / tot_ver if tot_ver else None
        return out
