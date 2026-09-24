"""Hive — roster, relay, parallel fan-out, redaction."""
from __future__ import annotations

import pytest

from rcx.hive import Bot, Hive, redact
from rcx.policy import CAP_READ, CAP_SHELL, CAP_WRITE


def test_register_and_roster(home):
    h = Hive(home)
    h.register("coder", "writes code", caps=[CAP_READ, CAP_WRITE])
    h.register("watcher", "reads only")
    assert [b.name for b in h.roster()] == ["coder", "watcher"]
    assert Hive(home).roster()[0].name == "coder"  # persisted


def test_register_rejects_empty(home):
    with pytest.raises(ValueError):
        Hive(home).register("   ", "x")


def test_unregister(home):
    h = Hive(home)
    h.register("tmp", "x")
    assert h.unregister("tmp") is True
    assert h.unregister("tmp") is False


def test_bot_caps(home):
    from rcx.policy import Policy
    h = Hive(home)
    b = h.register("c", "x", caps=[CAP_READ])
    assert b.can(CAP_READ, h.policy) is True
    assert b.can(CAP_SHELL, h.policy) is False
    assert Bot("z", "x", caps=[CAP_SHELL]).can(CAP_SHELL, Policy()) is True


def test_redact_secrets():
    assert redact("key sk-abcdefgh12345678 here") == "key REDACTED here"
    assert redact("token=abcdefgh1234") == "REDACTED"
    assert redact("clean text") == "clean text"
    assert redact("") == ""


def test_relay_roundtrip_and_redaction(home):
    h = Hive(home)
    h.post("ops", "coder", "deployed with sk-abcdefgh12345678")
    msgs = h.read("ops")
    assert len(msgs) == 1
    assert "sk-abcdefgh12345678" not in msgs[0]["text"]
    assert "REDACTED" in msgs[0]["text"]
    assert h.read("empty-scope") == []


def _backend(bot, task):
    return {"reply": f"{bot.name} did {task}", "tools_used": 2}


def test_parallel_run(home):
    h = Hive(home, max_workers=4)
    h.register("a", "x")
    h.register("b", "y")
    res = h.run("do the thing", ["a", "b"], _backend, scope="t1")
    assert res["ok"] == 2 and res["total"] == 2
    assert h.read("t1") and len(h.read("t1")) == 2


def test_run_unknown_bots(home):
    h = Hive(home)
    res = h.run("x", ["ghost"], _backend)
    assert res["results"] == {} and "note" in res


def test_run_no_secret_leak(home):
    h = Hive(home)
    h.register("leaky", "x")

    def bad_backend(bot, task):
        return {"reply": "here is sk-abcdefgh12345678 oops", "tools_used": 1}

    res = h.run("x", ["leaky"], bad_backend, scope="leak")
    assert "sk-abcdefgh12345678" not in res["results"]["leaky"]["reply"]
    stored = h.read("leak")[0]["text"]
    assert "sk-abcdefgh12345678" not in stored


def test_backend_error_recorded(home):
    h = Hive(home)
    h.register("b", "x")

    def boom(bot, task):
        raise RuntimeError("kaput")

    res = h.run("x", ["b"], boom)
    assert res["results"]["b"]["ok"] is False
    assert "kaput" in res["results"]["b"]["error"]
