"""Plan graph — the plan IS a node DAG, not a task list.

Nodes carry machine checks. Edges carry weights (connectome synapses).
The executor walks topo order; the verifier scores per node.
Renders to FlowCanvas via to_flow().
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rcx.home import RcxHome, _read_json, _write_json

STATUS = ("pending", "running", "done", "failed", "skipped")


@dataclass
class PlanNode:
    id: str
    text: str
    checks: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    attempts: int = 0
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "text": self.text, "checks": self.checks,
                "status": self.status, "attempts": self.attempts, "note": self.note}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlanNode":
        return cls(id=str(d["id"]), text=str(d.get("text", "")),
                   checks=list(d.get("checks", [])),
                   status=str(d.get("status", "pending")),
                   attempts=int(d.get("attempts", 0)),
                   note=str(d.get("note", "")))


@dataclass
class PlanEdge:
    frm: str
    to: str
    weight: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {"from": self.frm, "to": self.to, "weight": self.weight}


class PlanGraph:
    """A DAG of check-carrying nodes. Cycles refused at the edge."""

    def __init__(self, goal: str = "") -> None:
        self.goal = goal
        self.nodes: Dict[str, PlanNode] = {}
        self.edges: List[PlanEdge] = []
        self.created = time.time()

    # ------------------------------------------------------------ structure
    def add_node(self, text: str, checks: Optional[List[Dict[str, Any]]] = None,
                 node_id: str = "") -> PlanNode:
        nid = node_id or f"n_{uuid.uuid4().hex[:6]}"
        n = PlanNode(id=nid, text=text, checks=checks or [])
        self.nodes[nid] = n
        return n

    def add_edge(self, frm: str, to: str, weight: float = 0.5) -> PlanEdge:
        if frm not in self.nodes or to not in self.nodes:
            raise KeyError(f"edge to unknown node: {frm} -> {to}")
        if frm == to:
            raise ValueError("self-edge refused")
        if self._reaches(to, frm):
            raise ValueError(f"edge {frm} -> {to} would close a cycle")
        e = PlanEdge(frm, to, weight)
        self.edges.append(e)
        return e

    def _reaches(self, src: str, dst: str) -> bool:
        seen, stack = set(), [src]
        while stack:
            cur = stack.pop()
            if cur == dst:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(e.to for e in self.edges if e.frm == cur)
        return False

    def predecessors(self, nid: str) -> List[str]:
        return [e.frm for e in self.edges if e.to == nid]

    def successors(self, nid: str) -> List[str]:
        return [e.to for e in self.edges if e.frm == nid]

    def topo(self) -> List[str]:
        """Kahn's algorithm. Raises on cycle (should be unreachable)."""
        incoming = {nid: 0 for nid in self.nodes}
        for e in self.edges:
            incoming[e.to] += 1
        queue = sorted(n for n, d in incoming.items() if d == 0)
        order = []
        while queue:
            cur = queue.pop(0)
            order.append(cur)
            for nxt in sorted(self.successors(cur)):
                incoming[nxt] -= 1
                if incoming[nxt] == 0:
                    queue.append(nxt)
        if len(order) != len(self.nodes):
            raise ValueError("cycle detected in plan graph")
        return order

    def ready(self) -> List[str]:
        """Pending nodes whose predecessors are all done."""
        return [nid for nid in self.topo()
                if self.nodes[nid].status == "pending"
                and all(self.nodes[p].status == "done" for p in self.predecessors(nid))]

    def is_complete(self) -> bool:
        return all(n.status in ("done", "skipped") for n in self.nodes.values())

    def has_failed(self) -> bool:
        return any(n.status == "failed" for n in self.nodes.values())

    # ------------------------------------------------------------ flow render
    def to_flow(self) -> Dict[str, Any]:
        """FlowCanvas-compatible render: deterministic grid layout."""
        order = self.topo()
        cols = 3
        nodes = []
        for i, nid in enumerate(order):
            n = self.nodes[nid]
            nodes.append({"id": nid, "position": {"x": (i % cols) * 220, "y": (i // cols) * 140},
                          "data": {"label": n.text[:60], "status": n.status,
                                   "checks": len(n.checks), "depends_on": self.predecessors(nid)},
                          "style": {"status": n.status}})
        edges = [{"id": f"e{i}", "source": e.frm, "target": e.to,
                  "label": f"{e.weight:.2f}"} for i, e in enumerate(self.edges)]
        return {"nodes": nodes, "edges": edges, "goal": self.goal}

    # ------------------------------------------------------------ persistence
    def to_dict(self) -> Dict[str, Any]:
        return {"goal": self.goal, "created": self.created,
                "nodes": [n.to_dict() for n in self.nodes.values()],
                "edges": [e.to_dict() for e in self.edges]}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlanGraph":
        g = cls(goal=str(d.get("goal", "")))
        g.created = float(d.get("created", time.time()))
        for nd in d.get("nodes", []):
            n = PlanNode.from_dict(nd)
            g.nodes[n.id] = n
        for ed in d.get("edges", []):
            g.edges.append(PlanEdge(ed["from"], ed["to"], float(ed.get("weight", 0.5))))
        return g

    def save(self, path: Path) -> None:
        _write_json(path, self.to_dict())

    @classmethod
    def load(cls, path: Path) -> "PlanGraph":
        return cls.from_dict(_read_json(path, {"goal": "", "nodes": [], "edges": []}))
