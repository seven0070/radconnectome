"""ARC-style battery — novel-task skill-acquisition tests."""
from __future__ import annotations

from rcx.arc import (FAMILIES, ArcTask, generate, random_baseline, rule_solver,
                     run)


def test_generate_novel_and_reproducible():
    a = generate(n_per_family=2, seed=7)
    b = generate(n_per_family=2, seed=7)
    c = generate(n_per_family=2, seed=8)
    assert len(a) == 2 * len(FAMILIES)
    assert [t.heldout_out for t in a] == [t.heldout_out for t in b]
    assert [t.heldout_out for t in a] != [t.heldout_out for t in c]
    assert {t.family for t in a} == set(FAMILIES)


def test_six_families():
    assert set(FAMILIES) == {"shift", "recolor", "mirror", "rotate",
                             "invert", "border"}


def test_random_baseline_scores_zero():
    tasks = generate(n_per_family=4, seed=0)
    rep = run(tasks, random_baseline)
    assert rep.rate < 0.2  # ~0: proves the battery measures something
    assert rep.total == 4 * len(FAMILIES)


def test_rule_solver_scores_high():
    tasks = generate(n_per_family=4, seed=1)
    rep = run(tasks, rule_solver)
    assert rep.rate == 1.0
    assert rep.efficient == rep.total  # 2 steps, inside every 5x budget
    assert set(rep.by_family) == set(FAMILIES)


def test_rule_solver_across_seeds():
    for seed in (0, 2, 3, 42):
        rep = run(generate(n_per_family=2, seed=seed), rule_solver)
        assert rep.rate == 1.0, f"seed {seed}: {rep.to_dict()}"


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


def test_rotate_rule():
    from rcx.arc import RULES
    g = [[1, 2, 3], [4, 5, 6]]
    assert RULES["rotate"](g) == [[4, 1], [5, 2], [6, 3]]


def test_invert_rule():
    from rcx.arc import RULES
    assert RULES["invert"]([[1, 0], [0, 3]]) == [[0, 1], [1, 0]]


def test_border_rule():
    from rcx.arc import RULES
    g = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    out = RULES["border"](g)
    assert out[0] == [4, 4, 4] and out[2] == [4, 4, 4]
    assert out[1] == [4, 5, 4]


def test_grids_up_to_8():
    big = [t for t in generate(n_per_family=8, seed=9)
           if len(t.heldout_in) > 6 or len(t.heldout_in[0]) > 6]
    assert big, "harder seeds must include >6 grids"
