"""Fractal swarm — recursive spawning with guaranteed termination."""
from __future__ import annotations

from rcx.fractal import (MAX_DEPTH, MAX_FANOUT, MIN_CHILD_TOOLS, FractalSwarm,
                         SpawnTicket)


def _root(tools: int = 60) -> SpawnTicket:
    return SpawnTicket(goal="root goal", budget_tools=tools, budget_seconds=300)


def test_spawn_children_with_split_budget(home):
    sw = FractalSwarm(home)
    kids = sw.spawn(_root(), ["g1", "g2", "g3", "g4"])
    assert len(kids) == 4
    assert all(k.depth == 1 for k in kids)
    assert all(k.parent_id for k in kids)
    assert sum(k.budget_tools for k in kids) <= 60  # conservation


def test_parent_keeps_reserve(home):
    sw = FractalSwarm(home)
    kids = sw.spawn(_root(tools=10), ["g1", "g2"])
    assert sum(k.budget_tools for k in kids) <= 10 - MIN_CHILD_TOOLS


def test_depth_cap_denies(home):
    sw = FractalSwarm(home)
    deep = SpawnTicket(goal="x", budget_tools=60, budget_seconds=300, depth=MAX_DEPTH)
    ok, reason = sw.can_spawn(deep)
    assert ok is False and "depth" in reason
    assert sw.spawn(deep, ["g1"]) == []


def test_small_budget_denies(home):
    sw = FractalSwarm(home)
    poor = _root(tools=1)
    ok, _ = sw.can_spawn(poor)
    assert ok is False
    assert sw.spawn(poor, ["g1"]) == []


def test_fanout_capped(home):
    sw = FractalSwarm(home)
    kids = sw.spawn(_root(tools=500), [f"g{i}" for i in range(50)])
    assert len(kids) <= MAX_FANOUT


def test_cycle_dedup(home):
    sw = FractalSwarm(home)
    p = _root()
    k1 = sw.spawn(p, ["same", "same", "other"])
    assert [k.goal for k in k1] == ["same", "other"]  # dupes collapsed
    k2 = sw.spawn(p, ["same"])  # already spawned under this parent
    assert k2 == []


def test_halt_stops_spawning(home):
    sw = FractalSwarm(home)
    p = _root()
    assert sw.spawn(p, ["g1"])
    sw.halt("goal verified")
    assert sw.is_halted()
    assert sw.spawn(p, ["g2"]) == []
    ok, reason = sw.can_spawn(p)
    assert ok is False and "halted" in reason


def test_recursion_terminates(home):
    """Full depth chain: keep splitting until the cap. Must end."""
    sw = FractalSwarm(home)
    frontier = [_root(tools=200)]
    total = 0
    while frontier:
        nxt = []
        for t in frontier:
            kids = sw.spawn(t, [f"{t.goal}.{i}" for i in range(3)])
            total += len(kids)
            nxt.extend(kids)
        frontier = nxt
    assert total > 0
    # depth never exceeded, every ticket within budget law
    for s in sw._ledger():
        assert s.get("depth", 0) <= MAX_DEPTH or "denied" in s.get("status", "")


def test_should_split_advice(home):
    sw = FractalSwarm(home)
    assert sw.should_split(_root(), ["a", "b"]) is True
    assert sw.should_split(_root(tools=1), ["a"]) is False
    assert sw.should_split(_root(), []) is False
    sw.halt()
    assert sw.should_split(_root(), ["a"]) is False


def test_ledger_persists(home):
    sw = FractalSwarm(home)
    parent = _root()
    sw.spawn(parent, ["g1"])
    sw2 = FractalSwarm(home)  # reload from disk
    assert sw2.stats()["spawned"] == 1
    # same parent id → dedup survives reload
    assert sw2.spawn(parent, ["g1"]) == []
    # a *new* parent instance is a different lineage → allowed (not a cycle)
    assert sw2.spawn(_root(), ["g1"]) != []
