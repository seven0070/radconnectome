"""Auto-curriculum — the full loop: propose → dream → practice → promote.

Each nightly cycle:
  1. propose  — weakest verified path becomes a drill area (skills module)
  2. dream    — synthetic file tasks from that area (dream module)
  3. practice — run them through the verifying executor (injected act)
  4. promote  — transfer >= threshold records the verified drill pattern as
                a skill; anything less only journals. The gate decides.

Promotion stores what verified (task texts + transfer), never invented code.
Journal: `~/.rcx/curriculum.jsonl`. One entry per cycle, pass or fail.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from rcx.home import RcxHome

# act(step_text, workspace) -> (reply, artifact_paths)
CurriculumAct = Callable[[str, str], Tuple[str, List[str]]]

PROMOTE_TRANSFER = 0.75  # gate: transfer at or above this promotes


def run_cycle(home: RcxHome, act: CurriculumAct, n: int = 4,
              workspace: str = "") -> Dict[str, Any]:
    """One full curriculum cycle. Returns the report (and journals it)."""
    from rcx import dream as _dream
    from rcx.skills import SkillLibrary

    report: Dict[str, Any] = {"at": time.time(), "proposed": False,
                              "transfer": 0.0, "promoted": False}
    lib = SkillLibrary(home)
    proposal = lib.propose_curriculum(home)
    report["proposal"] = proposal
    if not proposal.get("proposed"):
        _journal(home, report)
        return report
    report["proposed"] = True

    tasks = _dream.generate(home, n=n)
    ws = Path(workspace) if workspace else home.workspace() / "curriculum"
    res = _dream.practice(home, tasks, act, workspace=str(ws))
    report["transfer"] = res["transfer"]
    report["verified"] = res["verified"]
    report["total"] = res["total"]

    if res["transfer"] >= PROMOTE_TRANSFER and res["total"] > 0:
        area = str(proposal.get("area", "drill"))
        slug = re.sub(r"\W+", "_", area).strip("_")[:40] or "drill"
        code = json.dumps([t.to_dict() for t in tasks], indent=1)[:2000]
        skill = lib.add(f"drill_{slug}",
                        code=f"# verified drill pattern (transfer {res['transfer']:.2f})\n{code}",
                        description=f"nightly drill for {area} — verified, do not hand-edit")
        report["promoted"] = True
        report["skill"] = skill.name
    _journal(home, report)
    return report


def _journal(home: RcxHome, report: Dict[str, Any]) -> None:
    try:
        with open(home.root / "curriculum.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": report.get("at", time.time()),
                                "proposed": report.get("proposed", False),
                                "transfer": report.get("transfer", 0.0),
                                "promoted": report.get("promoted", False),
                                "skill": report.get("skill", "")}) + "\n")
    except OSError:
        pass


def history(home: RcxHome, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        lines = (home.root / "curriculum.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out
