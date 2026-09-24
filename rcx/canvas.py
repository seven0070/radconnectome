"""Canvas export — static snapshot renderer for plan DAGs.

P3 honesty note: no live server, no node toolchain here. `export_html()`
takes a `PlanGraph.to_flow()` dict and bakes it into a self-contained
SVG page (nodes, bezier edges, status colors, minimap counts). Open the
file in any browser. A snapshot, not a studio — labeled as such.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict

STATUS_COLORS = {
    "pending": "#9aa4b2",
    "running": "#4da3ff",
    "done": "#3fb950",
    "failed": "#f85149",
    "skipped": "#6e7681",
}

TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>RadConnectome Flow — {goal}</title>
<style>
body {{ font-family: system-ui, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; }}
header {{ padding: 12px 16px; border-bottom: 1px solid #30363d; }}
.snapshot {{ font-size: 11px; opacity: .6; }}
svg {{ display: block; width: 100%; height: auto; background: #0d1117; }}
.node rect {{ stroke-width: 2; }}
.node text {{ fill: #e6edf3; font-size: 11px; }}
.edge {{ fill: none; stroke: #8b949e; stroke-width: 1.5; opacity: .8; }}
.minimap {{ font-size: 11px; opacity: .7; padding: 8px 16px; }}
</style></head><body>
<header><strong>RadConnectome Flow</strong> — {goal}
<span class="snapshot">static snapshot (no live server in P3)</span></header>
<div class="minimap">nodes: {n} · edges: {m} · done {done}/{n}</div>
<svg viewBox="0 0 720 480" role="img" aria-label="plan DAG">
{nodes_svg}
{edges_svg}
</svg>
</body></html>
"""

_NODE = ('<g class="node" data-testid="flow-node" data-id="{id}" data-status="{status}">'
         '<rect x="{x}" y="{y}" width="180" height="44" rx="6" fill="#161b22" stroke="{color}"/>'
         '<text x="{tx}" y="{ty}">{label}</text></g>')

_EDGE = ('<path class="edge" data-testid="flow-edge" d="M {x1} {y1} C {x1} {ym}, {x2} {ym}, {x2} {y2}"/>')


def render(flow: Dict[str, Any]) -> str:
    """Render a to_flow() dict to standalone HTML. Pure function, testable."""
    nodes = flow.get("nodes", [])
    edges = flow.get("edges", [])
    by_id = {n["id"]: n for n in nodes}
    parts = []
    for n in nodes:
        pos = n.get("position", {"x": 0, "y": 0})
        x, y = pos.get("x", 0), pos.get("y", 0)
        status = n.get("data", {}).get("status", "pending")
        label = html.escape(str(n.get("data", {}).get("label", n["id"]))[:28])
        parts.append(_NODE.format(id=html.escape(n["id"]), status=status,
                                  x=x, y=y, tx=x + 10, ty=y + 26,
                                  color=STATUS_COLORS.get(status, "#9aa4b2"),
                                  label=label))
    eparts = []
    for e in edges:
        a, b = by_id.get(e.get("source", "")), by_id.get(e.get("target", ""))
        if not a or not b:
            continue
        pa, pb = a.get("position", {"x": 0, "y": 0}), b.get("position", {"x": 0, "y": 0})
        x1, y1 = pa.get("x", 0) + 180, pa.get("y", 0) + 22
        x2, y2 = pb.get("x", 0), pb.get("y", 0) + 22
        eparts.append(_EDGE.format(x1=x1, y1=y1, ym=(y1 + y2) // 2, x2=x2, y2=y2))
    done = sum(1 for n in nodes if n.get("data", {}).get("status") == "done")
    return TEMPLATE.format(goal=html.escape(str(flow.get("goal", ""))),
                           n=len(nodes), m=len(edges), done=done,
                           nodes_svg="\n".join(parts), edges_svg="\n".join(eparts))


def export_html(flow: Dict[str, Any], path: str | Path) -> Path:
    """Write the snapshot page. Returns the path. Creates parents."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(flow), encoding="utf-8")
    return p
