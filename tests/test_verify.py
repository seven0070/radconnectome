"""Verifier — check kinds + verdict tests."""
from __future__ import annotations

from pathlib import Path

from rcx.verify import FAILED, UNVERIFIED, VERIFIED, Check, Verifier


def _v(tmp_path) -> Verifier:
    return Verifier(tmp_path)


def test_file_exists(tmp_path):
    v = _v(tmp_path)
    assert v.run_check(Check("file_exists", {"path": "nope.txt"}))["ok"] is False
    (tmp_path / "a.txt").write_text("x")
    assert v.run_check(Check("file_exists", {"path": "a.txt"}))["ok"] is True


def test_file_contains_and_equals(tmp_path):
    v = _v(tmp_path)
    (tmp_path / "a.txt").write_text("hello world")
    assert v.run_check(Check("file_contains", {"path": "a.txt", "text": "world"}))["ok"] is True
    assert v.run_check(Check("file_contains", {"path": "a.txt", "text": "zzz"}))["ok"] is False
    assert v.run_check(Check("file_equals", {"path": "a.txt", "text": "hello world"}))["ok"] is True


def test_file_absent_and_dir(tmp_path):
    v = _v(tmp_path)
    assert v.run_check(Check("file_absent", {"path": "nope.txt"}))["ok"] is True
    assert v.run_check(Check("dir_exists", {"path": "."}))["ok"] is True


def test_json_valid_and_field(tmp_path):
    v = _v(tmp_path)
    (tmp_path / "d.json").write_text('{"a": {"b": 1}}')
    assert v.run_check(Check("json_valid", {"path": "d.json"}))["ok"] is True
    assert v.run_check(Check("json_field", {"path": "d.json", "key": "a.b", "equals": 1}))["ok"] is True
    assert v.run_check(Check("json_field", {"path": "d.json", "key": "a.zzz"}))["ok"] is False
    (tmp_path / "bad.json").write_text("{nope")
    assert v.run_check(Check("json_valid", {"path": "bad.json"}))["ok"] is False


def test_shell_ok(tmp_path):
    v = _v(tmp_path)
    assert v.run_check(Check("shell_ok", {"command": "echo hi"}))["ok"] is True


def test_unknown_kind_fails():
    v = _v(Path("."))
    r = v.run_check(Check("teleport", {}))
    assert r["ok"] is False


def test_verdict_verified_failed_unverified(tmp_path):
    v = _v(tmp_path)
    (tmp_path / "a.txt").write_text("x")
    r = v.verify([Check("file_exists", {"path": "a.txt"})])
    assert r["status"] == VERIFIED
    r = v.verify([Check("file_exists", {"path": "missing.txt"})])
    assert r["status"] == FAILED
    r = v.verify([])
    assert r["status"] == UNVERIFIED


def test_artifacts_count(tmp_path):
    v = _v(tmp_path)
    (tmp_path / "out.txt").write_text("data")
    r = v.verify([], artifacts=["out.txt"])
    assert r["status"] == VERIFIED
