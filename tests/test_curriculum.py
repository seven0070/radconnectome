"""Auto-curriculum — full loop: propose → dream → practice → promote."""
from __future__ import annotations

import re
from pathlib import Path

from rcx.curriculum import PROMOTE_TRANSFER, history, run_cycle


def _good_act(text, ws):
    m = re.search(r"Write (\S+) containing '(.*)'", text)
    if not m:
        return ("DONE: nothing to do", [])
    p = Path(ws) / m.group(1)
    p.write_text(m.group(2), encoding="utf-8")
    return (f"DONE: wrote {m.group(1)}", [m.group(1)])


def _bad_act(text, ws):
    return ("DONE: definitely did it (lies)", [])


def _seed_weakness(home):
    from rcx.connectome import Connectome
    cx = Connectome(home)
    cx.fire("coder", "flaky_tool", verified=True, success=False)
    cx.save()


def test_no_history_no_promote(home, tmp_path):
    rep = run_cycle(home, _good_act, n=2, workspace=str(tmp_path / "c"))
    assert rep["proposed"] is False and rep["promoted"] is False
    assert history(home) and history(home)[0]["promoted"] is False


def test_good_actor_promotes(home, tmp_path):
    _seed_weakness(home)
    rep = run_cycle(home, _good_act, n=2, workspace=str(tmp_path / "c"))
    assert rep["proposed"] is True
    assert rep["transfer"] == 1.0 >= PROMOTE_TRANSFER
    assert rep["promoted"] is True
    from rcx.skills import SkillLibrary
    assert SkillLibrary(home).get(rep["skill"]) is not None


def test_bad_actor_no_promote(home, tmp_path):
    _seed_weakness(home)
    rep = run_cycle(home, _bad_act, n=2, workspace=str(tmp_path / "c"))
    assert rep["proposed"] is True
    assert rep["transfer"] == 0.0
    assert rep["promoted"] is False
    assert "skill" not in rep


def test_second_night_reuses(home, tmp_path):
    _seed_weakness(home)
    run_cycle(home, _good_act, n=1, workspace=str(tmp_path / "c1"))
    rep2 = run_cycle(home, _good_act, n=1, workspace=str(tmp_path / "c2"))
    assert rep2["promoted"] is True  # loop is repeatable, gate re-checks
    assert len(history(home)) == 2


def test_threshold_constant_sane():
    assert 0.5 <= PROMOTE_TRANSFER <= 1.0
