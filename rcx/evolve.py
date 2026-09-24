"""Evolution — TTRL majority vote, no labels needed.

Given K candidate outputs for one decision, the majority wins (exact-match
clustering, deterministic tie-break by first-seen). Unanimous or majority =
signal; total fragmentation = abstain. Every vote is journaled to
`~/.rcx/evolve.jsonl` with the evidence. No labels, no training — just
counting, which is why it can't hallucinate authority.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from rcx.home import RcxHome


def majority(candidates: List[str]) -> Dict[str, Any]:
    """Vote. Returns winner, votes, and whether the vote means anything."""
    if not candidates:
        return {"winner": None, "votes": {}, "decisive": False, "n": 0}
    counts: Dict[str, int] = {}
    order: List[str] = []
    for c in candidates:
        key = c.strip()
        if key not in counts:
            counts[key] = 0
            order.append(key)
        counts[key] += 1
    best = max(order, key=lambda k: (counts[k], -order.index(k)))
    n = len(candidates)
    return {"winner": best, "votes": dict(counts),
            "decisive": counts[best] * 2 > n or n == 1, "n": n}


class Evolver:
    """Majority-vote refiner with a persisted journal."""

    def __init__(self, home: RcxHome) -> None:
        self.home = home

    @property
    def journal_path(self):
        return self.home.root / "evolve.jsonl"

    def refine(self, question: str, candidates: List[str]) -> Dict[str, Any]:
        """One TTRL step: vote, journal, return the winner (or abstain)."""
        v = majority(candidates)
        entry = {"at": time.time(), "question": question[:300],
                 "winner": v["winner"], "votes": v["votes"],
                 "decisive": v["decisive"], "n": v["n"]}
        try:
            with open(self.journal_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
        return entry

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            lines = self.journal_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for ln in lines[-limit:]:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
