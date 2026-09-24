"""Nightly refinement — replay, propose, lab-gate."""
from __future__ import annotations

from rcx.sleep import lab_gate, propose, replay, run_sleep


def test_replay_empty(home):
    res = replay(home)
    assert res["pruned"] == 0 and res["synapses"] == 0


def test_replay_prunes(home):
    from rcx.connectome import Connectome, PRUNE_BELOW
    cx = Connectome(home)
    cx.fire("a", "b")
    cx.synapses[("a", "b")].weight = PRUNE_BELOW
    cx.save()
    res = replay(home)  # re-ingests (no objectives) + replays
    assert res["pruned"] == 1


def test_propose_nothing_without_history(home):
    assert propose(home)["proposed"] is False


def test_propose_weakest_path(home):
    from rcx.connectome import Connectome
    cx = Connectome(home)
    for _ in range(2):
        cx.fire("coder", "flaky", verified=True, success=False)
    cx.fire("coder", "solid", verified=True, success=True)
    cx.save()
    p = propose(home)
    assert p["proposed"] is True and "flaky" in p["path"]


def test_lab_gate_passes(home):
    g = lab_gate(home, {"proposed": True, "path": "x->y"})
    assert g["passed"] is True and g["rate"] == 1.0


def test_lab_gate_skips_empty(home):
    g = lab_gate(home, {"proposed": False})
    assert g["passed"] is True


def test_run_sleep_report_shape(home):
    rep = run_sleep(home)
    assert set(rep) >= {"at", "replay", "proposal", "gate"}
    assert (home.root / "sleep.jsonl").exists()
