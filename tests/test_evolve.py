"""Evolution — majority vote without labels."""
from __future__ import annotations

from rcx.evolve import Evolver, majority


def test_majority_clear():
    v = majority(["a", "b", "a"])
    assert v["winner"] == "a" and v["decisive"] is True
    assert v["votes"] == {"a": 2, "b": 1}


def test_majority_tie_first_seen_wins_but_indecisive():
    v = majority(["a", "b"])
    assert v["winner"] == "a" and v["decisive"] is False


def test_majority_single():
    v = majority(["only"])
    assert v["winner"] == "only" and v["decisive"] is True


def test_majority_empty():
    v = majority([])
    assert v["winner"] is None and v["decisive"] is False


def test_majority_strips():
    v = majority(["  x  ", "x", "y"])
    assert v["winner"] == "x" and v["votes"]["x"] == 2


def test_refine_journals(home):
    ev = Evolver(home)
    r = ev.refine("which file?", ["a.txt", "b.txt", "a.txt"])
    assert r["winner"] == "a.txt" and r["decisive"] is True
    hist = ev.history()
    assert len(hist) == 1 and hist[0]["question"] == "which file?"


def test_refine_abstain_journaled(home):
    ev = Evolver(home)
    r = ev.refine("pick one", ["a", "b", "c"])
    assert r["decisive"] is False
    assert ev.history()[0]["decisive"] is False
