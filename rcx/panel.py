"""Panel — state dashboard snapshot (Appsmith pattern, static edition).

`export_dashboard()` reads live state (connectome stats, tribe weights, cost
rollup, ARC baseline) and bakes one self-contained HTML page. No server.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict

from rcx.home import RcxHome

TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>RadConnectome Panel</title>
<style>
body {{ font-family: system-ui, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; }}
header {{ padding: 12px 16px; border-bottom: 1px solid #30363d; }}
.snapshot {{ font-size: 11px; opacity: .6; }}
section {{ border: 1px solid #30363d; border-radius: 8px; margin: 12px 16px; padding: 10px 14px; }}
h2 {{ font-size: 13px; margin: 0 0 6px; }}
pre {{ font-size: 12px; white-space: pre-wrap; }}
</style></head><body>
<header><strong>RadConnectome Panel</strong>
<span class="snapshot">static snapshot (no live server in P3) — {at}</span></header>
{sections}
</body></html>
"""

_SECTION = "<section><h2>{title}</h2><pre>{body}</pre></section>"


def collect(home: RcxHome) -> Dict[str, Any]:
    """Gather live state. Every section best-effort; failures record, never raise."""
    out: Dict[str, Any] = {}
    try:
        from rcx.connectome import Connectome
        out["connectome"] = Connectome(home).stats()
    except Exception as e:
        out["connectome"] = {"error": str(e)[:120]}
    try:
        from rcx.tribe import TribeEncoder
        out["tribe"] = TribeEncoder(home).stats()
    except Exception as e:
        out["tribe"] = {"error": str(e)[:120]}
    try:
        from rcx.cost import CostLog
        out["cost"] = CostLog(home).rollup()
    except Exception as e:
        out["cost"] = {"error": str(e)[:120]}
    try:
        from rcx.hive import Hive
        out["hive"] = {"bots": [b.name for b in Hive(home).roster()],
                       "swarm": Hive(home).swarm.stats()}
    except Exception as e:
        out["hive"] = {"error": str(e)[:120]}
    try:
        from rcx.arc import generate, rule_solver, run
        rep = run(generate(n_per_family=2, seed=0), rule_solver)
        out["arc_baseline"] = rep.to_dict()
    except Exception as e:
        out["arc_baseline"] = {"error": str(e)[:120]}
    return out


def render(state: Dict[str, Any], at: str = "") -> str:
    sections = []
    for title in ("connectome", "tribe", "cost", "hive", "arc_baseline"):
        body = html.escape(json.dumps(state.get(title, {}), indent=2)[:2000])
        sections.append(_SECTION.format(title=html.escape(title), body=body))
    return TEMPLATE.format(at=html.escape(at), sections="\n".join(sections))


def export_dashboard(home: RcxHome, path: str | Path, at: str = "") -> Path:
    """Write the snapshot page. Returns the path. Creates parents."""
    import time
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(collect(home), at or time.strftime("%Y-%m-%d %H:%M")),
                 encoding="utf-8")
    return p
