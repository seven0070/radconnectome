"""CLI-driver brain — budget, refusal, injectable runner."""
from __future__ import annotations

import pytest

from rcx.brain_cli import CliDriver, CliResult, default_runner


def _fake_runner(argv, prompt, timeout):
    return CliResult(ok=True, text=f"echo:{prompt[:20]}", code=0)


def test_ask_counts_budget():
    d = CliDriver(["claude", "-p"], max_calls=2, runner=_fake_runner)
    assert d.ask("hi").ok is True
    assert d.ask("hi").ok is True
    assert d.exhausted is True
    r = d.ask("hi")
    assert r.ok is False and r.code == 429


def test_requires_argv():
    with pytest.raises(ValueError):
        CliDriver([])


def test_refuses_hard_blocked():
    d = CliDriver(["sudo", "id"], runner=_fake_runner)
    # default_runner refuses; fake runner would allow — refusal lives in default_runner
    r = default_runner(["sudo", "id"], "x", 5)
    assert r.ok is False and "refused" in r.detail
    assert d.ask("x").ok is True  # injected runner is the caller's responsibility


def test_missing_binary():
    r = default_runner(["definitely-not-a-real-binary-xyz"], "x", 5)
    assert r.ok is False and r.code == 127


def test_stats():
    d = CliDriver(["claude", "-p"], runner=_fake_runner)
    d.ask("a")
    st = d.stats()
    assert st["calls"] == 1 and st["exhausted"] is False
