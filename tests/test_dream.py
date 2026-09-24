"""Dream Gym — synthetic practice, real verification."""
from __future__ import annotations

from pathlib import Path

from rcx.dream import generate, practice


def _good_act(text, ws):
    # a competent dream actor: writes what the step asks for
    import re
    m = re.search(r"Write (\S+) containing '(.*)'", text)
    if not m:
        return ("DONE: nothing to do", [])
    p = Path(ws) / m.group(1)
    p.write_text(m.group(2), encoding="utf-8")
    return (f"DONE: wrote {m.group(1)}", [m.group(1)])


def _bad_act(text, ws):
    return ("DONE: definitely did it (lies)", [])


def test_generate_fallback_without_history(home):
    tasks = generate(home, n=3)
    assert len(tasks) == 3
    assert all(t.filename.startswith("dream_") for t in tasks)
    assert all(t.source_path for t in tasks)


def test_generate_from_weakness(home):
    from rcx.connectome import Connectome
    cx = Connectome(home)
    cx.fire("coder", "flaky", verified=True, success=False)
    cx.save()
    tasks = generate(home, n=2)
    assert any("flaky" in t.source_path for t in tasks)


def test_practice_transfer_good_actor(home, tmp_path):
    tasks = generate(home, n=2)
    res = practice(home, tasks, _good_act, workspace=str(tmp_path / "d"))
    assert res["transfer"] == 1.0
    assert res["verified"] == 2


def test_practice_transfer_bad_actor(home, tmp_path):
    tasks = generate(home, n=2)
    res = practice(home, tasks, _bad_act, workspace=str(tmp_path / "d"))
    assert res["transfer"] == 0.0
    assert res["failed"] == 2


def test_practice_empty(home, tmp_path):
    res = practice(home, [], _good_act, workspace=str(tmp_path / "d"))
    assert res == {"verified": 0, "failed": 0, "total": 0, "transfer": 0.0,
                   "at": res["at"]}
