"""Planner + executor — goal in, verified graph out.

Planner decomposes a goal into a check-carrying DAG (heuristic, honest:
keyword-proposed checks, empty checks stay UNVERIFIED — never invented).
Executor walks topo order with an injected `act` callback, verifies every
node, stops on FAILED. Model-agnostic: the brain is a callback, not a vendor.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from rcx.graph import PlanGraph
from rcx.verify import FAILED, UNVERIFIED, VERIFIED, Check, Verifier

# act(node) -> (reply_text, artifact_paths)
ActFn = Callable[[str, str], Tuple[str, List[str]]]

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\s+then\s+|\s+and then\s+", re.I)
_STEP_PREFIX = re.compile(r"^\s*(?:step\s*\d+[\.:)]?|[-*•\d]+[.)\]]\s+)", re.I)


def propose_checks(text: str) -> List[Dict[str, Any]]:
    """Keyword-proposed machine checks. Conservative: only what the text names.

    `write X` / `create X` / `file X` -> file_exists on X. Nothing else guessed.
    """
    checks = []
    m = re.search(r"(?:write|create|make|generate|save)\s+(?:file\s+)?[`\"']?([\w\-./]+\.\w+)[`\"']?", text, re.I)
    if m:
        checks.append({"kind": "file_exists", "path": m.group(1)})
    m = re.search(r"file\s+[`\"']?([\w\-./]+\.\w+)[`\"']?\s+(?:exists|with|containing)", text, re.I)
    if m and not checks:
        checks.append({"kind": "file_exists", "path": m.group(1)})
    return checks


def decompose(goal: str, max_tasks: int = 16) -> PlanGraph:
    """Split a goal into an ordered DAG. One node per step, chained."""
    g = PlanGraph(goal=goal)
    parts = [p.strip(" .") for p in _SENT_SPLIT.split(goal) if p.strip(" .")]
    # numbered/bulleted lists split further
    steps: List[str] = []
    for p in parts:
        lines = [ln.strip() for ln in p.splitlines() if ln.strip()]
        if len(lines) > 1 and all(_STEP_PREFIX.match(ln) for ln in lines):
            steps.extend(_STEP_PREFIX.sub("", ln).strip(" .") for ln in lines)
        else:
            steps.append(p)
    steps = [s for s in steps if s][:max_tasks] or [goal.strip()]
    prev = None
    for s in steps:
        n = g.add_node(s, checks=propose_checks(s))
        if prev is not None:
            g.add_edge(prev, n.id)
        prev = n.id
    return g


class Executor:
    """Walks the graph in topo order. Verifies every node. Stops on FAILED."""

    def __init__(self, workspace: Path, max_attempts: int = 2) -> None:
        self.verifier = Verifier(workspace)
        self.max_attempts = max_attempts

    def run(self, graph: PlanGraph, act: ActFn) -> Dict[str, Any]:
        for nid in graph.topo():
            node = graph.nodes[nid]
            if node.status != "pending":
                continue
            if any(graph.nodes[p].status != "done" for p in graph.predecessors(nid)):
                node.status = "skipped"
                node.note = "predecessor not done"
                continue
            node.status = "running"
            node.attempts += 1
            try:
                reply, artifacts = act(nid, node.text)
            except Exception as e:
                node.status = "failed"
                node.note = f"act error: {e}"[:200]
                break
            checks = [Check(c["kind"], {k: v for k, v in c.items() if k != "kind"})
                      for c in node.checks]
            verdict = self.verifier.verify(checks, reply=reply, artifacts=artifacts)
            node.note = verdict["summary"][:300]
            if verdict["status"] == VERIFIED:
                node.status = "done"
            elif verdict["status"] == FAILED:
                node.status = "failed"
                break  # stop: retry is the caller's job (re-run), not a silent loop
            elif not checks:
                node.status = "done"  # no checks: done-but-unverified (graph stays UNVERIFIED)
            else:
                node.status = "pending"
                break  # UNVERIFIED with checks: stop, don't fake it
        if graph.has_failed():
            status = FAILED
        elif graph.is_complete():
            status = VERIFIED if any(n.checks for n in graph.nodes.values()) else UNVERIFIED
        else:
            status = FAILED if graph.has_failed() else UNVERIFIED
        return {"status": status,
                "nodes": {nid: n.status for nid, n in graph.nodes.items()}}
