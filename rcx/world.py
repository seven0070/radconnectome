"""World model — entities, relations, causal simulate, masked prediction.

Entities + relations form the world graph (persisted `~/.rcx/world/graph.json`).
Two inference modes, both labeled as predictions, never facts:

  simulate(action)      — given an action on an entity, predict affected
                          entities via relation traversal (causal fan-out).
  predict_masked(name)  — C-JEPA analogue: hide one entity's attrs, infer them
                          from its neighbors. Counterfactual substrate.
  what_if(name, attr, value) — set an attr hypothetically, re-derive predictions.

Accuracy is tracked: every prediction gets an id; record_outcome() marks it
matched or not. The scoreboard reports prediction accuracy on held-out checks.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rcx.home import RcxHome, _read_json, _write_json


@dataclass
class Entity:
    name: str
    kind: str = "thing"
    attrs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "attrs": self.attrs}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Entity":
        return cls(name=str(d["name"]), kind=str(d.get("kind", "thing")),
                   attrs=dict(d.get("attrs", {})))


@dataclass
class Relation:
    frm: str
    rel: str
    to: str
    status: str = "current"   # current | superseded | disputed
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {"from": self.frm, "rel": self.rel, "to": self.to,
                "status": self.status, "confidence": self.confidence}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Relation":
        return cls(frm=str(d["from"]), rel=str(d["rel"]), to=str(d["to"]),
                   status=str(d.get("status", "current")),
                   confidence=float(d.get("confidence", 0.5)))


@dataclass
class Prediction:
    pid: str
    kind: str          # simulate | masked | what_if
    detail: str
    predicted: List[str]
    at: float = 0.0
    matched: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"pid": self.pid, "kind": self.kind, "detail": self.detail,
                "predicted": self.predicted, "at": self.at, "matched": self.matched}


class WorldModel:
    def __init__(self, home: RcxHome) -> None:
        self.home = home
        self.root = home.root / "world"
        self.root.mkdir(parents=True, exist_ok=True)
        self.entities: Dict[str, Entity] = {}
        self.relations: List[Relation] = []
        self.predictions: Dict[str, Prediction] = {}
        self._load()

    # ------------------------------------------------------------ persistence
    @property
    def graph_path(self):
        return self.root / "graph.json"

    @property
    def preds_path(self):
        return self.root / "predictions.jsonl"

    def _load(self) -> None:
        d = _read_json(self.graph_path, {})
        for ed in d.get("entities", []):
            try:
                e = Entity.from_dict(ed)
                self.entities[e.name] = e
            except Exception:
                continue
        for rd in d.get("relations", []):
            try:
                self.relations.append(Relation.from_dict(rd))
            except Exception:
                continue

    def save(self) -> None:
        _write_json(self.graph_path, {
            "updated": time.time(),
            "entities": [e.to_dict() for e in self.entities.values()],
            "relations": [r.to_dict() for r in self.relations]})

    # ------------------------------------------------------------ CRUD
    def add_entity(self, name: str, kind: str = "thing",
                   attrs: Optional[Dict[str, Any]] = None) -> Entity:
        e = self.entities.get(name)
        if e is None:
            e = Entity(name=name, kind=kind, attrs=attrs or {})
            self.entities[name] = e
        else:
            e.attrs.update(attrs or {})
        self.save()
        return e

    def add_relation(self, frm: str, rel: str, to: str,
                     confidence: float = 0.5) -> Relation:
        self.add_entity(frm)
        self.add_entity(to)
        for r in self.relations:
            if r.frm == frm and r.rel == rel and r.to == to and r.status == "current":
                r.confidence = max(r.confidence, confidence)
                self.save()
                return r
        r = Relation(frm, rel, to, confidence=confidence)
        self.relations.append(r)
        self.save()
        return r

    def retract(self, frm: str, rel: str, to: str) -> bool:
        for r in self.relations:
            if r.frm == frm and r.rel == rel and r.to == to and r.status == "current":
                r.status = "superseded"
                self.save()
                return True
        return False

    def query(self, term: str) -> List[Dict[str, Any]]:
        low = term.lower()
        out = []
        for e in self.entities.values():
            if low in e.name.lower() or low in e.kind.lower():
                out.append({"type": "entity", **e.to_dict()})
        for r in self.relations:
            if r.status != "current":
                continue
            if low in f"{r.frm} {r.rel} {r.to}".lower():
                out.append({"type": "relation", **r.to_dict()})
        return out

    def neighbors(self, name: str) -> List[str]:
        out = []
        for r in self.relations:
            if r.status != "current":
                continue
            if r.frm == name and r.to not in out:
                out.append(r.to)
            elif r.to == name and r.frm not in out:
                out.append(r.frm)
        return out

    # ------------------------------------------------------------ inference
    def _record_pred(self, kind: str, detail: str, predicted: List[str]) -> Prediction:
        p = Prediction(pid=f"p_{uuid.uuid4().hex[:8]}", kind=kind,
                       detail=detail, predicted=predicted, at=time.time())
        self.predictions[p.pid] = p
        try:
            with open(self.preds_path, "a", encoding="utf-8") as f:
                import json
                f.write(json.dumps(p.to_dict()) + "\n")
        except Exception:
            pass
        return p

    def simulate(self, action: str, target: str, hops: int = 2) -> Prediction:
        """Predict entities affected by acting on target (causal fan-out).

        Breadth-first over current relations up to `hops`. The prediction is
        labeled as such — call record_outcome() when reality arrives.
        """
        seen = {target}
        frontier = [target]
        for _ in range(max(1, hops)):
            nxt = []
            for n in frontier:
                for m in self.neighbors(n):
                    if m not in seen:
                        seen.add(m)
                        nxt.append(m)
            frontier = nxt
        seen.discard(target)
        return self._record_pred("simulate", f"{action} on {target}",
                                 sorted(seen))

    def predict_masked(self, name: str) -> Prediction:
        """C-JEPA analogue: hide `name`'s attrs, infer them from neighbors.

        For each neighbor, borrow attrs the masked entity lacks (tagged with
        provenance `inferred-from:<neighbor>` in the detail, not written).
        """
        ent = self.entities.get(name)
        if ent is None:
            return self._record_pred("masked", f"{name} unknown", [])
        inferred: Dict[str, str] = {}
        for nb in self.neighbors(name):
            other = self.entities.get(nb)
            if other is None:
                continue
            for k, v in other.attrs.items():
                if k not in ent.attrs and k not in inferred:
                    inferred[k] = f"{v} (from {nb})"
        detail = "; ".join(f"{k}={v}" for k, v in sorted(inferred.items())) or "nothing inferable"
        return self._record_pred("masked", f"{name}: {detail}", sorted(inferred))

    def what_if(self, name: str, attr: str, value: Any) -> Prediction:
        """Hypothetical: set attr, re-run simulate over affected subgraph."""
        ent = self.entities.get(name)
        old = ent.attrs.get(attr) if ent else None
        changed = [m for m in self.neighbors(name)
                   if (self.entities.get(m) or Entity(m)).attrs.get(attr) != value]
        detail = f"{name}.{attr}: {old!r} -> {value!r}; would affect {len(changed)} neighbor(s)"
        return self._record_pred("what_if", detail, sorted(changed))

    # ------------------------------------------------------------ scoring
    def record_outcome(self, pid: str, matched: bool) -> bool:
        p = self.predictions.get(pid)
        if p is None:
            return False
        p.matched = bool(matched)
        try:
            with open(self.preds_path, "a", encoding="utf-8") as f:
                import json
                f.write(json.dumps({"pid": pid, "matched": p.matched,
                                    "at": time.time()}) + "\n")
        except Exception:
            pass
        return True

    def accuracy(self) -> Dict[str, Any]:
        scored = [p for p in self.predictions.values() if p.matched is not None]
        if not scored:
            return {"scored": 0, "accuracy": None}
        hits = sum(1 for p in scored if p.matched)
        return {"scored": len(scored), "hits": hits, "accuracy": hits / len(scored)}
