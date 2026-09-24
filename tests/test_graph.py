"""Plan graph — DAG structure, topo, flow render, persistence."""
from __future__ import annotations

import pytest

from rcx.graph import PlanEdge, PlanGraph, PlanNode


def test_chain_topo_order():
    g = PlanGraph(goal="a then b then c")
    a = g.add_node("a")
    b = g.add_node("b")
    c = g.add_node("c")
    g.add_edge(a.id, b.id)
    g.add_edge(b.id, c.id)
    assert g.topo() == [a.id, b.id, c.id]


def test_diamond_topo():
    g = PlanGraph()
    a = g.add_node("a")
    b = g.add_node("b")
    c = g.add_node("c")
    d = g.add_node("d")
    g.add_edge(a.id, b.id)
    g.add_edge(a.id, c.id)
    g.add_edge(b.id, d.id)
    g.add_edge(c.id, d.id)
    order = g.topo()
    assert order[0] == a.id and order[-1] == d.id
    assert set(order) == {a.id, b.id, c.id, d.id}


def test_cycle_refused():
    g = PlanGraph()
    a = g.add_node("a")
    b = g.add_node("b")
    g.add_edge(a.id, b.id)
    with pytest.raises(ValueError):
        g.add_edge(b.id, a.id)


def test_self_edge_refused():
    g = PlanGraph()
    a = g.add_node("a")
    with pytest.raises(ValueError):
        g.add_edge(a.id, a.id)


def test_unknown_node_refused():
    g = PlanGraph()
    a = g.add_node("a")
    with pytest.raises(KeyError):
        g.add_edge(a.id, "ghost")


def test_ready_gating():
    g = PlanGraph()
    a = g.add_node("a")
    b = g.add_node("b")
    g.add_edge(a.id, b.id)
    assert g.ready() == [a.id]
    g.nodes[a.id].status = "done"
    assert g.ready() == [b.id]


def test_to_flow_shape():
    g = PlanGraph(goal="demo")
    a = g.add_node("write f.txt", checks=[{"kind": "file_exists", "path": "f.txt"}])
    b = g.add_node("check it")
    g.add_edge(a.id, b.id, weight=0.7)
    f = g.to_flow()
    assert f["goal"] == "demo"
    assert len(f["nodes"]) == 2 and len(f["edges"]) == 1
    n0 = f["nodes"][0]
    assert set(n0) >= {"id", "position", "data", "style"}
    assert n0["data"]["checks"] == 1
    assert f["edges"][0]["source"] == a.id


def test_persistence_roundtrip(tmp_path):
    g = PlanGraph(goal="x")
    a = g.add_node("a")
    b = g.add_node("b")
    g.add_edge(a.id, b.id)
    g.nodes[a.id].status = "done"
    p = tmp_path / "plan.json"
    g.save(p)
    g2 = PlanGraph.load(p)
    assert g2.goal == "x"
    assert g2.topo() == [a.id, b.id]
    assert g2.nodes[a.id].status == "done"
