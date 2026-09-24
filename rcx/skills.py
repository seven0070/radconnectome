"""Skill library — Voyager pattern, verified edition.

Skills are code-as-action-space: named, described, executable snippets stored
as JSON under `~/.rcx/skills/`. Retrieved by token overlap, strengthened by
verified use, weakened by failure (same STDP spirit as the connectome).

The auto-curriculum proposes the next skill from the weakest verified paths —
a proposal (area + rationale + interface), never invented code.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rcx.home import RcxHome, _read_json, _write_json

STOP = set("a an and are as at be but by for from had has have if in into is it "
           "its no not of on or so that the their them they this to was were "
           "will with you your".split())


def _toks(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9_]{3,}", text.lower()) if t not in STOP]


@dataclass
class Skill:
    name: str
    code: str
    description: str = ""
    uses: int = 0
    successes: int = 0
    created: float = 0.0

    @property
    def strength(self) -> float:
        if self.uses == 0:
            return 0.5
        return max(0.05, min(1.0, self.successes / self.uses))

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "code": self.code,
                "description": self.description, "uses": self.uses,
                "successes": self.successes, "created": self.created}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Skill":
        return cls(name=str(d["name"]), code=str(d.get("code", "")),
                   description=str(d.get("description", "")),
                   uses=int(d.get("uses", 0)), successes=int(d.get("successes", 0)),
                   created=float(d.get("created", 0.0)))


class SkillLibrary:
    """File-backed skill store. One JSON per skill, human-readable."""

    def __init__(self, home: RcxHome) -> None:
        self.home = home
        self.root = home.root / "skills"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        safe = re.sub(r"[^a-z0-9_]", "_", name.lower())[:64] or "skill"
        return self.root / f"{safe}.json"

    def add(self, name: str, code: str, description: str = "") -> Skill:
        if not name.strip():
            raise ValueError("skill needs a name")
        if not code.strip():
            raise ValueError("skill needs code (code-as-action-space, no empty skills)")
        s = Skill(name=name.strip(), code=code, description=description,
                  created=time.time())
        _write_json(self._path(name), s.to_dict())
        return s

    def get(self, name: str) -> Optional[Skill]:
        p = self._path(name)
        if not p.exists():
            return None
        try:
            return Skill.from_dict(_read_json(p, {}))
        except Exception:
            return None

    def all(self) -> List[Skill]:
        out = []
        for p in sorted(self.root.glob("*.json")):
            try:
                out.append(Skill.from_dict(_read_json(p, {})))
            except Exception:
                continue
        return [s for s in out if s.name]

    def retrieve(self, query: str, k: int = 5) -> List[Skill]:
        """Token-overlap rank (cheap, honest). Strength breaks ties."""
        q = set(_toks(query))
        if not q:
            return []
        scored = []
        for s in self.all():
            toks = set(_toks(s.name + " " + s.description + " " + s.code))
            overlap = len(q & toks) / len(q)
            if overlap > 0:
                scored.append((overlap + 0.01 * s.strength, s))
        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[:k]]

    def record_use(self, name: str, ok: bool) -> Optional[Skill]:
        s = self.get(name)
        if s is None:
            return None
        s.uses += 1
        s.successes += int(bool(ok))
        _write_json(self._path(name), s.to_dict())
        return s

    def remove(self, name: str) -> bool:
        p = self._path(name)
        if p.exists():
            p.unlink()
            return True
        return False

    # ------------------------------------------------------------ curriculum
    def propose_curriculum(self, home: Optional[RcxHome] = None) -> Dict[str, Any]:
        """Auto-curriculum: propose the next skill from the weakest verified path.

        Reads the connectome for verified edges with failures (hard-won areas)
        and proposes a skill interface for the weakest one. A proposal only —
        code comes from a verified run, never invented here.
        """
        h = home or self.home
        weakest: Optional[str] = None
        try:
            from rcx.connectome import Connectome
            cx = Connectome(h)
            cands = [(s.failures / max(1, s.successes + s.failures), f"{s.pre}->{s.post}")
                     for s in cx.synapses.values() if s.verified]
            cands.sort(key=lambda x: -x[0])
            if cands and cands[0][0] > 0:
                weakest = cands[0][1]
        except Exception:
            pass
        if weakest is None:
            low = sorted(self.all(), key=lambda s: s.strength)
            if low and low[0].uses > 0:
                weakest = f"improve:{low[0].name}"
        if weakest is None:
            return {"proposed": False, "reason": "no verified history yet — solve tasks first"}
        area = weakest.replace("->", "_to_")
        fn = re.sub(r"\W+", "_", area).strip("_")[:40] or "new_skill"
        return {"proposed": True, "area": area,
                "rationale": f"weakest verified path: {weakest}",
                "suggested_interface": f"def {fn}(): ..."}
