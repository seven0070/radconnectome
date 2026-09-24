"""Hive — bot roster + blackboard relay + parallel fan-out.

Bots are roles with capability sets and tool budgets (MausBot roster idea).
They talk through a file-backed relay (Buzz Nostr idea, local files instead
of a network). They run in parallel via threads, each inside a FractalSwarm
ticket (budget conservation + ledger + halt). Every transcript is secret-
scrubbed before storage — a leak test enforces it.

No Docker in P3 (probe-only): isolation is capability-gating + redaction +
budgets. Docker comes post-v1.0, explicitly out of scope.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from rcx.fractal import FractalSwarm, SpawnTicket
from rcx.home import RcxHome, _read_json, _write_json
from rcx.policy import (CAP_READ, CAP_SHELL, CAP_WRITE, Policy)

# secret shapes that must never land in a transcript
SECRET_RES = [
    re.compile(r"\b(sk-[A-Za-z0-9_-]{16,})"),
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})"),
    re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)(\s*[:=]\s*)(['\"]?)([^\s'\"]{8,})"),
]


def redact(text: str) -> str:
    if not text:
        return text
    for pat in SECRET_RES:
        text = pat.sub("REDACTED", text)
    return text


@dataclass
class Bot:
    name: str
    role: str
    caps: List[str] = field(default_factory=lambda: [CAP_READ])
    budget_tools: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "role": self.role, "caps": self.caps,
                "budget_tools": self.budget_tools}

    def can(self, capability: str, policy: Optional[Policy] = None) -> bool:
        if capability not in self.caps:
            return False
        if policy is not None:
            return not policy.decide(capability).denied
        return True


# backend(bot, task) -> {"reply": str, "tools_used": int}
BackendFn = Callable[[Bot, str], Dict[str, Any]]


class Hive:
    """Roster + relay + parallel fan-out."""

    def __init__(self, home: RcxHome, policy: Optional[Policy] = None,
                 max_workers: int = 8) -> None:
        self.home = home
        self.policy = policy or Policy()
        self.max_workers = max_workers
        self.root = home.root / "hive"
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "relay").mkdir(exist_ok=True)
        self.swarm = FractalSwarm(home)
        self._bots: Dict[str, Bot] = {}
        self._load_roster()

    # ------------------------------------------------------------ roster
    @property
    def roster_path(self):
        return self.root / "roster.json"

    def _load_roster(self) -> None:
        for b in _read_json(self.roster_path, {"bots": []}).get("bots", []):
            try:
                bot = Bot(name=str(b["name"]), role=str(b.get("role", "")),
                          caps=list(b.get("caps", [CAP_READ])),
                          budget_tools=int(b.get("budget_tools", 10)))
                self._bots[bot.name] = bot
            except Exception:
                continue

    def _save_roster(self) -> None:
        _write_json(self.roster_path, {"bots": [b.to_dict() for b in self._bots.values()]})

    def register(self, name: str, role: str, caps: Optional[List[str]] = None,
                 budget_tools: int = 10) -> Bot:
        if not name.strip():
            raise ValueError("bot needs a name")
        bot = Bot(name=name.strip(), role=role, caps=caps or [CAP_READ],
                  budget_tools=max(1, budget_tools))
        self._bots[bot.name] = bot
        self._save_roster()
        return bot

    def unregister(self, name: str) -> bool:
        if name in self._bots:
            del self._bots[name]
            self._save_roster()
            return True
        return False

    def roster(self) -> List[Bot]:
        return sorted(self._bots.values(), key=lambda b: b.name)

    # ------------------------------------------------------------ relay
    def post(self, scope: str, author: str, text: str) -> Dict[str, Any]:
        safe = re.sub(r"[^a-z0-9_]", "_", scope.lower())[:48] or "general"
        path = self.root / "relay" / f"{safe}.jsonl"
        entry = {"at": time.time(), "author": author, "text": redact(text)}
        try:
            with open(path, "a", encoding="utf-8") as f:
                import json
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass
        return entry

    def read(self, scope: str, limit: int = 50) -> List[Dict[str, Any]]:
        import json
        safe = re.sub(r"[^a-z0-9_]", "_", scope.lower())[:48] or "general"
        path = self.root / "relay" / f"{safe}.jsonl"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for ln in lines[-limit:]:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out

    # ------------------------------------------------------------ fan-out
    def run(self, task: str, bots: List[str], backend: BackendFn,
            scope: str = "general") -> Dict[str, Any]:
        """Run bots in parallel on one task. Each inside a swarm ticket.

        Budgets conserved via FractalSwarm; halt respected; transcripts
        redacted. Returns per-bot results + rollup.
        """
        if self.swarm.is_halted():
            return {"halted": True, "results": {}}
        chosen = [self._bots[n] for n in bots if n in self._bots]
        if not chosen:
            return {"halted": False, "results": {}, "note": "no such bots"}
        root = SpawnTicket(goal=f"hive:{task[:80]}", budget_tools=sum(b.budget_tools for b in chosen),
                           budget_seconds=600)
        tickets = self.swarm.spawn(root, [f"hive:{b.name}:{task[:60]}" for b in chosen])
        by_goal = {t.goal: t for t in tickets}
        results: Dict[str, Any] = {}
        workers = max(1, min(self.max_workers, len(chosen)))

        def _one(bot: Bot) -> tuple[str, Dict[str, Any]]:
            ticket = by_goal.get(f"hive:{bot.name}:{task[:60]}")
            if ticket is None:
                return bot.name, {"ok": False, "detail": "no ticket (budget too small)"}
            try:
                raw = backend(bot, task) or {}
            except Exception as e:
                raw = {"reply": "", "tools_used": 0, "error": str(e)[:200]}
            reply = redact(str(raw.get("reply", "")))
            self.post(scope, bot.name, reply)
            return bot.name, {"ok": "error" not in raw, "reply": reply,
                              "tools_used": int(raw.get("tools_used", 0)),
                              "ticket": ticket.agent_id,
                              **({"error": raw["error"]} if "error" in raw else {})}

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_one, b): b.name for b in chosen}
            for f in as_completed(futs):
                name, res = f.result()
                results[name] = res
        ok = sum(1 for r in results.values() if r.get("ok"))
        return {"halted": False, "results": results, "ok": ok,
                "total": len(results)}
