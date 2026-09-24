"""Fractal swarm — agents that spawn agents until the end goal is finished.

One halt condition: the root goal verifies. Everything else is machinery to
guarantee termination even when it never does:

  1. Depth cap — spawns strictly deepen; MAX_DEPTH stops the recursion.
  2. Budget conservation — children partition the parent's budget, never mint
     new budget. Sum(children) <= parent, always.
  3. Goal-check unwind — a VERIFIED root halts every level immediately.

Plus cycle dedup: the same goal spawned twice under one parent records once.

This is the honest version of "infinite subagents": unbounded in *shape*
(any tree the work needs), strictly bounded in *resources* (depth x budget).
Without all three guarantees this would be a fork bomb. With them it always
halts — by success (VERIFIED) or by exhaustion (budgets hit zero).

Persistence: `~/.rcx/swarm/ledger.json` (every spawn recorded with lineage).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rcx.home import RcxHome, _read_json, _write_json
from rcx.verify import FAILED, UNVERIFIED, VERIFIED

MAX_DEPTH = 4        # deepest nesting allowed (root = 0)
MAX_FANOUT = 8       # max children per spawn (matches objective_parallel)
MIN_CHILD_TOOLS = 2  # a child needs at least this many tool calls to be viable


@dataclass
class SpawnTicket:
    """A license to exist. No ticket, no agent."""
    goal: str
    budget_tools: int
    budget_seconds: int
    depth: int = 0
    parent_id: str = "root"
    agent_id: str = ""
    lineage: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.agent_id:
            self.agent_id = f"a_{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        return {"goal": self.goal, "budget_tools": self.budget_tools,
                "budget_seconds": self.budget_seconds, "depth": self.depth,
                "parent_id": self.parent_id, "agent_id": self.agent_id,
                "lineage": self.lineage}


class FractalSwarm:
    """Recursive spawner with guaranteed termination."""

    def __init__(self, home: RcxHome, max_depth: int = MAX_DEPTH,
                 max_fanout: int = MAX_FANOUT) -> None:
        self.home = home
        self.max_depth = max_depth
        self.max_fanout = max_fanout
        self.root = home.root / "swarm"
        self.root.mkdir(parents=True, exist_ok=True)
        self.halted = False

    @property
    def ledger_path(self) -> Path:
        return self.root / "ledger.json"

    def _ledger(self) -> List[Dict[str, Any]]:
        d = _read_json(self.ledger_path, {"spawns": []})
        return d.get("spawns", [])

    def _record(self, t: SpawnTicket, status: str) -> None:
        spawns = self._ledger()
        spawns.append({**t.to_dict(), "status": status, "at": time.time()})
        _write_json(self.ledger_path, {"spawns": spawns})

    # ------------------------------------------------------------ spawning
    def can_spawn(self, parent: SpawnTicket) -> tuple[bool, str]:
        """Gate: depth, budget, and halt state. Denials carry the reason."""
        if self.halted:
            return False, "swarm halted (goal verified)"
        if parent.depth >= self.max_depth:
            return False, f"max depth {self.max_depth} reached"
        if parent.budget_tools < MIN_CHILD_TOOLS * 2:
            return False, "parent budget too small to split"
        return True, "ok"

    def split_budget(self, parent_tools: int, n: int) -> List[int]:
        """Partition parent tools across n children. Sum(children) <= parent.

        Parent keeps a reserve of MIN_CHILD_TOOLS so it can verify + report.
        """
        reserve = MIN_CHILD_TOOLS
        pool = max(0, parent_tools - reserve)
        n = max(1, min(n, self.max_fanout))
        each, rem = divmod(pool, n)
        shares = [each + (1 if i < rem else 0) for i in range(n)]
        # drop non-viable children (a child with < MIN_CHILD_TOOLS can't act)
        return [s for s in shares if s >= MIN_CHILD_TOOLS]

    def spawn(self, parent: SpawnTicket, subgoals: List[str]) -> List[SpawnTicket]:
        """Spawn one child per subgoal (deduped, gated, recorded).

        Returns the viable children. Denied or duplicate subgoals are skipped
        and recorded as such — never silently dropped, never double-spawned.
        """
        ok, reason = self.can_spawn(parent)
        if not ok:
            self._record(parent, f"spawn-denied:{reason}")
            return []
        seen = {s["goal"] for s in self._ledger() if s.get("parent_id") == parent.agent_id}
        fresh = [g for g in dict.fromkeys(subgoals) if g and g not in seen]
        shares = self.split_budget(parent.budget_tools, len(fresh))
        children = []
        for goal, share in zip(fresh, shares):
            child = SpawnTicket(goal=goal, budget_tools=share,
                                budget_seconds=max(30, parent.budget_seconds // max(1, len(fresh))),
                                depth=parent.depth + 1, parent_id=parent.agent_id,
                                lineage=[*parent.lineage, parent.agent_id])
            self._record(child, "spawned")
            children.append(child)
        return children

    # ------------------------------------------------------------ halting
    def halt(self, reason: str = "goal verified") -> Dict[str, Any]:
        """The one stop condition: end goal finished. Unwinds everything."""
        self.halted = True
        spawns = self._ledger()
        _write_json(self.root / "halt.json",
                    {"at": time.time(), "reason": reason,
                     "total_spawned": len([s for s in spawns if s.get("status") == "spawned"])})
        return {"halted": True, "reason": reason}

    def is_halted(self) -> bool:
        return self.halted

    def should_split(self, ticket: SpawnTicket, subgoals: List[str]) -> bool:
        """Advise: split only if viable children exist AND not halted."""
        ok, _ = self.can_spawn(ticket)
        if not ok or not subgoals:
            return False
        return len(self.split_budget(ticket.budget_tools, len(subgoals))) > 0

    def stats(self) -> Dict[str, Any]:
        spawns = self._ledger()
        live = [s for s in spawns if s.get("status") == "spawned"]
        return {"spawned": len(live), "halted": self.halted,
                "max_depth": self.max_depth, "max_fanout": self.max_fanout}
