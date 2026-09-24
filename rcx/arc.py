"""ARC-style novel-task battery — skill-acquisition efficiency, not recall.

Inspired by ARC-AGI-3 (explore → model → goal-set → plan in novel environments
with no instructions; frontier <1%→30%, humans 100%). P0 stub, honest by design:

* Tasks are generated at run time from a seed — novel by construction, so no
  training overlap is possible (there is no training).
* The harness under test is a callback: it receives examples + a held-out
  input and returns an output plus a step count.
* Score = pass rate + efficiency (steps vs a human-baseline budget).
* A random-guess baseline is included to prove the battery measures something
  (baseline must score ~0).

No numpy, no torch. Stdlib only. Grids are nested int lists.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

Grid = List[List[int]]

# Human baseline: steps a person needs per task family (generous).
HUMAN_BASELINE_STEPS = {"shift": 3, "recolor": 3, "mirror": 4}
MAX_STEPS_FACTOR = 5  # hard cutoff at 5x human baseline (ARC-AGI-3 rule)


@dataclass
class ArcTask:
    family: str
    examples: List[Tuple[Grid, Grid]]
    heldout_in: Grid
    heldout_out: Grid
    seed: int

    def to_dict(self) -> Dict[str, Any]:
        return {"family": self.family, "examples": self.examples,
                "heldout_in": self.heldout_in, "seed": self.seed}


def _shift(g: Grid, dx: int, dy: int, h: int, w: int) -> Grid:
    out = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                out[ny][nx] = g[y][x]
    return out


def _gen_task(family: str, rng: random.Random) -> ArcTask:
    h, w = rng.randint(3, 6), rng.randint(3, 6)
    colors = [1, 2, 3, 4]

    def rand_grid() -> Grid:
        return [[rng.choice([0] * 3 + colors) for _ in range(w)] for _ in range(h)]

    def rule(g: Grid) -> Grid:
        if family == "shift":
            return _shift(g, 1, 0, h, w)
        if family == "recolor":
            return [[(c + 1) if c else 0 for c in row] for row in g]
        # mirror
        return [row[::-1] for row in g]

    examples = [(g := rand_grid(), rule(g)) for _ in range(3)]
    hi = rand_grid()
    seed = rng.randint(0, 10 ** 9)
    return ArcTask(family, examples, hi, rule(hi), seed)


def generate(n_per_family: int = 4, seed: int = 0) -> List[ArcTask]:
    """Generate novel tasks. Same seed → same tasks (reproducible, still novel
    to any solver that never saw them)."""
    rng = random.Random(seed)
    tasks = []
    for fam in ("shift", "recolor", "mirror"):
        for _ in range(n_per_family):
            tasks.append(_gen_task(fam, rng))
    return tasks


# ---------------------------------------------------------------- harness API

Solver = Callable[[List[Tuple[Grid, Grid]], Grid], Tuple[Grid, int]]
"""Solver(examples, heldout_in) -> (predicted_out, steps_used)."""


def random_baseline(examples: List[Tuple[Grid, Grid]], heldin: Grid) -> Tuple[Grid, int]:
    """Guesses randomly. Must score ~0 — proves the battery measures something."""
    rng = random.Random()
    h, w = len(heldin), len(heldin[0])
    return ([[rng.randint(0, 4) for _ in range(w)] for _ in range(h)], 1)


def rule_solver(examples: List[Tuple[Grid, Grid]], heldin: Grid) -> Tuple[Grid, int]:
    """Infers the rule from examples (shift/recolor/mirror) and applies it.

    This is the reference solver a real agent harness must beat-or-match.
    Counts 2 steps (infer + apply) — inside every human baseline.
    """
    (a_in, a_out), (b_in, b_out) = examples[0], examples[1]
    h, w = len(heldin), len(heldin[0])
    if _shift(a_in, 1, 0, len(a_in), len(a_in[0])) == a_out:
        return (_shift(heldin, 1, 0, h, w), 2)
    recol_a = [[(c + 1) if c else 0 for c in row] for row in a_in]
    if recol_a == a_out:
        return ([[(c + 1) if c else 0 for c in row] for row in heldin], 2)
    return ([row[::-1] for row in heldin], 2)


@dataclass
class ArcReport:
    passed: int
    total: int
    efficient: int   # passed within 5x human baseline
    rate: float
    by_family: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "total": self.total,
                "efficient": self.efficient, "rate": self.rate,
                "by_family": self.by_family}


def run(tasks: List[ArcTask], solver: Solver) -> ArcReport:
    """Score a solver harness on novel tasks. Efficiency cutoff = 5x human."""
    passed = efficient = 0
    by_family: Dict[str, Dict[str, int]] = {}
    for t in tasks:
        pred, steps = solver(t.examples, t.heldout_in)
        ok = pred == t.heldout_out
        budget = HUMAN_BASELINE_STEPS[t.family] * MAX_STEPS_FACTOR
        eff = ok and steps <= budget
        passed += bool(ok)
        efficient += bool(eff)
        fam = by_family.setdefault(t.family, {"passed": 0, "total": 0})
        fam["total"] += 1
        fam["passed"] += bool(ok)
    return ArcReport(passed, len(tasks), efficient,
                     passed / len(tasks) if tasks else 0.0, by_family)
