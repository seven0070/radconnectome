"""ARC-style battery — novel-task skill-acquisition tests."""
from __future__ import annotations

from rcx.arc import (ArcTask, generate, random_baseline, rule_solver, run)


def test_generate_novel_and_reproducible():
    a = generate(n_per_family=2, seed=7)
    b = generate(n_per_family=2, seed=7)
    c = generate(n_per_family=2, seed=8)
    assert len(a) == 6
    assert [t.heldout_out for t in a] == [t.heldout_out for t in b]
    assert [t.heldout_out for t in a] != [t.heldout_out for t in c]
    assert {t.family for t in a} == {"shift", "recolor", "mirror"}


def test_random_baseline_scores_zero():
    tasks = generate(n_per_family=4, seed=0)
    rep = run(tasks, random_baseline)
    assert rep.rate < 0.2  # ~0: proves the battery measures something
    assert rep.total == 12


def test_rule_solver_scores_high():
    tasks = generate(n_per_family=4, seed=1)
    rep = run(tasks, rule_solver)
    assert rep.rate == 1.0
    assert rep.efficient == rep.total  # 2 steps, inside every 5x budget
    assert set(rep.by_family) == {"shift", "recolor", "mirror"}


def test_efficiency_cutoff():
    def slow_solver(examples, heldin):
        out, _ = rule_solver(examples, heldin)
        return (out, 10 ** 9)  # correct but wildly over budget

    tasks = generate(n_per_family=1, seed=2)
    rep = run(tasks, slow_solver)
    assert rep.passed == rep.total
    assert rep.efficient == 0  # ARC-AGI-3 rule: over 5x human = not efficient


def test_task_shape():
    t = generate(n_per_family=1, seed=3)[0]
    assert isinstance(t, ArcTask)
    assert len(t.examples) == 3
    assert len(t.heldout_in) >= 3 and len(t.heldout_in[0]) >= 3
