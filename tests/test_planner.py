"""Planner + executor — decompose, propose checks, walk, verify."""
from __future__ import annotations

from rcx.planner import Executor, decompose, propose_checks
from rcx.verify import FAILED, UNVERIFIED, VERIFIED


def test_propose_checks_names_files():
    assert propose_checks("write report.txt with findings") == [
        {"kind": "file_exists", "path": "report.txt"}]
    assert propose_checks("just think about it") == []


def test_decompose_chains():
    g = decompose("Write a.txt then write b.txt then verify both")
    assert len(g.nodes) == 3
    assert len(g.edges) == 2
    assert g.topo() == list(g.nodes)  # chain order preserved


def test_decompose_caps():
    g = decompose("do " + " then ".join(f"thing{i}" for i in range(50)), max_tasks=16)
    assert len(g.nodes) == 16


def test_decompose_empty_goal():
    g = decompose("   ")
    assert len(g.nodes) == 1


def test_executor_all_verified(tmp_path):
    g = decompose("Write a.txt")
    (tmp_path / "a.txt").write_text("hi")

    def act(nid, text):
        return ("DONE: wrote it", [])

    ex = Executor(tmp_path)
    res = ex.run(g, act)
    assert res["status"] == VERIFIED
    assert all(s == "done" for s in res["nodes"].values())


def test_executor_stops_on_failed(tmp_path):
    g = decompose("Write missing.txt")
    calls = []

    def act(nid, text):
        calls.append(nid)
        return ("DONE: totally wrote it", [])  # lies; file absent

    ex = Executor(tmp_path)
    res = ex.run(g, act)
    assert res["status"] == FAILED
    assert len(calls) == 1  # stopped, no silent continuation


def test_executor_unverified_no_checks(tmp_path):
    from rcx.graph import PlanGraph
    g = PlanGraph(goal="think")
    g.add_node("ponder")  # no checks at all

    def act(nid, text):
        return ("DONE: pondered", [])

    ex = Executor(tmp_path)
    res = ex.run(g, act)
    assert res["status"] == UNVERIFIED  # done-but-unverified, never VERIFIED


def test_executor_act_error_fails(tmp_path):
    from rcx.graph import PlanGraph
    g = PlanGraph()
    g.add_node("boom")

    def act(nid, text):
        raise RuntimeError("brain exploded")

    ex = Executor(tmp_path)
    res = ex.run(g, act)
    assert res["status"] == FAILED
