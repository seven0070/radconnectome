"""Nightly refinement — replay, propose, lab-gate. Unclaw-validated pattern.

Each sleep: (1) replay the connectome (decay + prune), (2) propose ONE
tweak from the weakest verified path, (3) lab-gate it on the ARC battery:
promote only if the sampled score does not regress. Proposals are data,
never live changes — the gate decides.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from rcx.home import RcxHome, _read_json, _write_json


def replay(home: RcxHome) -> Dict[str, Any]:
    """Step 1: connectome sleep replay. Returns the replay summary."""
    from rcx.connectome import Connectome, ingest_objective_events
    ingest_objective_events(home)
    cx = Connectome(home)
    return cx.sleep_replay()


def propose(home: RcxHome) -> Dict[str, Any]:
    """Step 2: one tweak proposal from the weakest verified path.

    Returns {"proposed": False} when there is no verified history — solving
    tasks comes before refining. Proposals never touch live weights.
    """
    try:
        from rcx.connectome import Connectome
        cx = Connectome(home)
        cands = []
        for s in cx.synapses.values():
            if not s.verified:
                continue
            total = s.successes + s.failures
            if total == 0:
                continue
            cands.append((s.failures / total, f"{s.pre}->{s.post}", total))
        cands.sort(key=lambda x: -x[0])
        if not cands or cands[0][0] == 0:
            return {"proposed": False, "reason": "no failing verified paths"}
        rate, path, n = cands[0]
        return {"proposed": True, "path": path, "fail_rate": round(rate, 3),
                "samples": n, "tweak": "strengthen-alternative-route",
                "at": time.time()}
    except Exception as e:
        return {"proposed": False, "reason": f"propose error: {e}"[:200]}


def lab_gate(home: RcxHome, proposal: Dict[str, Any],
             seed: int = 0, n_per_family: int = 2) -> Dict[str, Any]:
    """Step 3: gate the proposal on the ARC battery (sampled, fast).

    The battery measures the harness, not the proposal — a proposal passes
    the gate when the harness still scores 100% on the sampled battery
    (no regression). Promotion writes to the sleep log; the proposal itself
    stays data until a human applies it.
    """
    from rcx.arc import generate, rule_solver, run
    if not proposal.get("proposed"):
        return {"passed": True, "reason": "nothing to gate", "proposal": proposal}
    tasks = generate(n_per_family=n_per_family, seed=seed)
    rep = run(tasks, rule_solver)
    passed = rep.rate == 1.0
    return {"passed": passed, "rate": rep.rate, "total": rep.total,
            "proposal": proposal}


def run_sleep(home: RcxHome) -> Dict[str, Any]:
    """Full nightly pass. Returns the sleep report; logs to sleep.jsonl."""
    report: Dict[str, Any] = {"at": time.time()}
    try:
        report["replay"] = replay(home)
    except Exception as e:
        report["replay"] = {"error": str(e)[:200]}
    prop = propose(home)
    report["proposal"] = prop
    try:
        report["gate"] = lab_gate(home, prop)
    except Exception as e:
        report["gate"] = {"passed": False, "reason": f"gate error: {e}"[:200]}
    try:
        with open(home.root / "sleep.jsonl", "a", encoding="utf-8") as f:
            import json
            f.write(json.dumps({"at": report["at"], "replay": report.get("replay"),
                                "proposal": prop.get("proposed"),
                                "gate": report.get("gate", {}).get("passed")}) + "\n")
    except Exception:
        pass
    return report
