"""Canvas — static snapshot renderer structural tests."""
from __future__ import annotations

from rcx.canvas import STATUS_COLORS, export_html, render
from rcx.graph import PlanGraph


def _flow():
    g = PlanGraph(goal="demo flow")
    a = g.add_node("write a.txt")
    b = g.add_node("verify a.txt")
    g.add_edge(a.id, b.id, weight=0.8)
    g.nodes[a.id].status = "done"
    return g.to_flow()


def test_render_has_nodes_edges_minimap():
    html = render(_flow())
    assert html.count('data-testid="flow-node"') == 2
    assert html.count('data-testid="flow-edge"') == 1
    assert "nodes: 2" in html and "edges: 1" in html
    assert "done 1/2" in html
    assert "static snapshot" in html  # honesty label present


def test_status_colors_applied():
    html = render(_flow())
    assert STATUS_COLORS["done"] in html
    assert STATUS_COLORS["pending"] in html
    assert "write a.txt" in html


def test_labels_escaped():
    g = PlanGraph()
    g.add_node("<script>alert(1)</script>")
    html = render(g.to_flow())
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_empty_flow():
    html = render({"nodes": [], "edges": [], "goal": ""})
    assert "nodes: 0" in html


def test_export_writes_file(tmp_path):
    p = export_html(_flow(), tmp_path / "sub" / "flow.html")
    assert p.exists()
    assert "demo flow" in p.read_text(encoding="utf-8")
