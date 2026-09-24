"""Dream Gym — synthetic-failure practice with real verification.

At night the agent dreams up file tasks derived from its weakest verified
paths, runs them through the Executor with an injected `act`, and reports a
transfer rate: fraction VERIFIED. Synthetic tasks, real checks — practice
that can only promote what verifies.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

from rcx.home import RcxHome

# act(step_text, workspace) -> (reply, artifact_paths)
DreamAct = Callable[[str, str], Tuple[str, List[str]]]


@dataclass
class DreamTask:
    text: str
    filename: str
    content: str
    source_path: str = ""  # weakest verified path it came from (provenance)

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "filename": self.filename,
                "content": self.content, "source_path": self.source_path}


def generate(home: RcxHome, n: int = 4) -> List[DreamTask]:
    """Dream up file tasks from the weakest verified connectome paths.

    Falls back to generic drills when there is no verified history yet —
    dreaming requires something to dream *about*, but the gym stays open.
    """
    sources: List[str] = []
    try:
        from rcx.connectome import Connectome
        cx = Connectome(home)
        cands = [(s.failures / max(1, s.successes + s.failures), f"{s.pre}->{s.post}")
                 for s in cx.synapses.values() if s.verified]
        cands.sort(key=lambda x: -x[0])
        sources = [p for _, p in cands[:n]]
    except Exception:
        pass
    while len(sources) < n:
        sources.append(f"drill:{len(sources)}")
    tasks = []
    for i, src in enumerate(sources[:n]):
        fn = f"dream_{i}.txt"
        body = f"dream drill {i} from {src}"
        tasks.append(DreamTask(text=f"Write {fn} containing {body!r}",
                               filename=fn, content=body, source_path=src))
    return tasks


def write_actor(step_text: str, workspace: str) -> Tuple[str, List[str]]:
    """Built-in dream actor: fulfills `Write X containing 'Y'` steps for real.

    Anything else returns a no-op (never lies about doing work).
    """
    import re
    from pathlib import Path
    m = re.search(r"Write (\S+) containing '(.*)'", step_text)
    if not m:
        return ("DONE: nothing to do", [])
    p = Path(workspace) / m.group(1)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(m.group(2), encoding="utf-8")
    return (f"DONE: wrote {m.group(1)}", [m.group(1)])


def practice(home: RcxHome, tasks: List[DreamTask],
             act: DreamAct, workspace: str = "") -> Dict[str, Any]:
    """Run dream tasks through the verifying executor. Returns transfer rate."""
    from pathlib import Path
    from rcx.planner import Executor, decompose
    ws = Path(workspace) if workspace else home.workspace() / "dreams"
    ws.mkdir(parents=True, exist_ok=True)
    verified = failed = 0
    for t in tasks:
        graph = decompose(t.text)
        ex = Executor(ws)

        def _act(nid: str, text: str, _t=t) -> Tuple[str, List[str]]:
            return act(text, str(ws))

        res = ex.run(graph, _act)
        if res["status"] == "VERIFIED":
            verified += 1
        else:
            failed += 1
    total = verified + failed
    return {"verified": verified, "failed": failed, "total": total,
            "transfer": verified / total if total else 0.0, "at": time.time()}
