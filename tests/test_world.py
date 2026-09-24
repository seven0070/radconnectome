"""World model — CRUD, simulate, masked prediction, what-if, scoring."""
from __future__ import annotations

from rcx.world import WorldModel


def _seed(home) -> WorldModel:
    w = WorldModel(home)
    w.add_entity("server", kind="machine", attrs={"os": "linux", "ram_gb": 16})
    w.add_entity("deploy", kind="task")
    w.add_entity("db", kind="service", attrs={"os": "linux"})
    w.add_relation("deploy", "targets", "server", confidence=0.9)
    w.add_relation("server", "hosts", "db", confidence=0.8)
    return w


def test_crud_and_query(home):
    w = _seed(home)
    assert w.query("server")
    assert w.query("nothing-here") == []
    assert w.retract("deploy", "targets", "server") is True
    assert w.retract("deploy", "targets", "server") is False  # already superseded
    assert all(r["status"] != "current" or r["to"] != "server"
               for r in w.query("targets") if r["type"] == "relation")


def test_neighbors(home):
    w = _seed(home)
    assert set(w.neighbors("server")) == {"deploy", "db"}


def test_simulate_fanout(home):
    w = _seed(home)
    p = w.simulate("restart", "server", hops=2)
    assert p.kind == "simulate"
    assert set(p.predicted) == {"deploy", "db"}
    assert p.matched is None  # prediction, not fact


def test_simulate_hops_bounded(home):
    w = _seed(home)
    p1 = w.simulate("x", "server", hops=1)
    assert set(p1.predicted) == {"deploy", "db"}
    p0 = w.simulate("x", "lonely-unknown-entity", hops=2)
    assert p0.predicted == []


def test_predict_masked_infers(home):
    w = _seed(home)
    w.add_entity("cache", kind="service")  # no attrs
    w.add_relation("cache", "runs_on", "server")
    p = w.predict_masked("cache")
    assert p.kind == "masked"
    assert "os=linux (from server)" in p.detail
    assert "os" in p.predicted


def test_predict_masked_unknown(home):
    w = WorldModel(home)
    p = w.predict_masked("ghost")
    assert p.predicted == []


def test_what_if(home):
    w = _seed(home)
    p = w.what_if("server", "os", "windows")
    assert p.kind == "what_if"
    assert "db" in p.predicted  # db still says linux
    assert "windows" in p.detail


def test_record_outcome_and_accuracy(home):
    w = _seed(home)
    p1 = w.simulate("restart", "server")
    p2 = w.simulate("restart", "db")
    assert w.record_outcome(p1.pid, True) is True
    assert w.record_outcome(p2.pid, False) is True
    assert w.record_outcome("nope", True) is False
    acc = w.accuracy()
    assert acc == {"scored": 2, "hits": 1, "accuracy": 0.5}


def test_accuracy_empty(home):
    assert WorldModel(home).accuracy() == {"scored": 0, "accuracy": None}


def test_persistence(home):
    w = _seed(home)
    w2 = WorldModel(home)
    assert "server" in w2.entities
    assert any(r.to == "db" for r in w2.relations)
