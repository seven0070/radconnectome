"""Skill library — add/retrieve/strengthen/curriculum."""
from __future__ import annotations

import pytest

from rcx.skills import SkillLibrary


def test_add_and_get(home):
    lib = SkillLibrary(home)
    s = lib.add("greet", "print('hi')", "say hello")
    assert lib.get("greet").code == "print('hi')"
    assert s.strength == 0.5  # unused: neutral prior


def test_add_rejects_empty(home):
    lib = SkillLibrary(home)
    with pytest.raises(ValueError):
        lib.add("", "x = 1")
    with pytest.raises(ValueError):
        lib.add("empty", "   ")


def test_retrieve_ranks(home):
    lib = SkillLibrary(home)
    lib.add("json_writer", "json.dump(obj, f)", "write JSON files to disk")
    lib.add("csv_reader", "csv.reader(f)", "read CSV rows")
    hits = lib.retrieve("write json output file")
    assert hits and hits[0].name == "json_writer"
    assert lib.retrieve("quantum teleportation") == []
    assert lib.retrieve("") == []


def test_strength_tracks(home):
    lib = SkillLibrary(home)
    lib.add("s", "x", "d")
    lib.record_use("s", True)
    lib.record_use("s", True)
    lib.record_use("s", False)
    s = lib.get("s")
    assert s.uses == 3 and s.successes == 2
    assert abs(s.strength - 2 / 3) < 1e-9


def test_record_use_missing(home):
    lib = SkillLibrary(home)
    assert lib.record_use("ghost", True) is None


def test_remove(home):
    lib = SkillLibrary(home)
    lib.add("tmp", "x")
    assert lib.remove("tmp") is True
    assert lib.get("tmp") is None
    assert lib.remove("tmp") is False


def test_curriculum_no_history(home):
    lib = SkillLibrary(home)
    res = lib.propose_curriculum()
    assert res["proposed"] is False


def test_curriculum_from_verified_weakness(home):
    from rcx.connectome import Connectome
    cx = Connectome(home)
    for _ in range(3):
        cx.fire("coder", "flaky_tool", verified=True, success=False)
    cx.fire("coder", "solid_tool", verified=True, success=True)
    cx.save()
    lib = SkillLibrary(home)
    res = lib.propose_curriculum()
    assert res["proposed"] is True
    assert "flaky_tool" in res["rationale"]
    assert res["suggested_interface"].startswith("def ")
