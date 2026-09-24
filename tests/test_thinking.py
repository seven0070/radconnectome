"""Adaptive thinking budget — bands, allocator, tracker, adaptation."""
from __future__ import annotations

from rcx.thinking import (BASE_BUDGETS, MAX_ATTEMPTS_CAP, ThinkingBudget,
                          estimate)


def test_estimate_bands():
    assert estimate("write hi.txt") == "trivial"
    assert estimate("list files") == "trivial"
    assert estimate("") == "trivial"
    assert estimate("refactor the distributed cache for race safety") == "hard"
    assert estimate("word " * 50) == "hard"  # long = hard
    assert estimate("review the quarterly plan draft") == "normal"


def test_allocator_ordering_and_caps(home):
    tb = ThinkingBudget(home)
    t, n, h = (tb.allocate(x) for x in ("write a", "review plan draft", "refactor cache"))
    assert (t["band"], n["band"], h["band"]) == ("trivial", "normal", "hard")
    assert t["attempts"] <= n["attempts"] <= h["attempts"] <= MAX_ATTEMPTS_CAP
    assert t["tools"] <= n["tools"] <= h["tools"]


def test_record_and_report(home):
    tb = ThinkingBudget(home)
    tb.record("write a", tools_used=2, verified=True)
    tb.record("write b", tools_used=4, verified=True)
    r = tb.report()
    assert r["bands"]["trivial"]["verified"] == 2
    assert r["bands"]["trivial"]["tools_per_verified"] == 3.0
    assert r["overall_tools_per_verified"] == 3.0


def test_no_verified_no_ratio(home):
    tb = ThinkingBudget(home)
    tb.record("write a", tools_used=2, verified=False)
    assert tb.report()["bands"]["trivial"]["tools_per_verified"] is None
    assert tb.report()["overall_tools_per_verified"] is None


def test_adaptation_earns_attempt_on_failure(home):
    tb = ThinkingBudget(home)
    for _ in range(3):
        tb.record("refactor the cache layer twice", tools_used=9, verified=False)
    assert tb.allocate("refactor the cache layer twice")["attempts"] == \
        BASE_BUDGETS["hard"]["attempts"] + 1


def test_adaptation_capped_and_needs_samples(home):
    tb = ThinkingBudget(home)
    tb.record("refactor x y", tools_used=9, verified=False)  # only 1 sample
    assert tb.allocate("refactor x y")["attempts"] == BASE_BUDGETS["hard"]["attempts"]
    for _ in range(20):
        tb.record("refactor x y", tools_used=9, verified=False)
    assert tb.allocate("refactor x y")["attempts"] <= MAX_ATTEMPTS_CAP


def test_success_keeps_base(home):
    tb = ThinkingBudget(home)
    for _ in range(5):
        tb.record("write file number", tools_used=1, verified=True)
    assert tb.allocate("write file number")["attempts"] == 1


def test_persistence(home):
    tb = ThinkingBudget(home)
    tb.record("write a", tools_used=2, verified=True)
    tb2 = ThinkingBudget(home)
    assert tb2.report()["bands"]["trivial"]["tasks"] == 1
