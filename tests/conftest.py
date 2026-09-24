"""Shared fixtures — isolated home per test (RCX_HOME)."""
from __future__ import annotations

import pytest

from rcx.home import RcxHome


@pytest.fixture
def home(tmp_path, monkeypatch):
    d = tmp_path / "rcxhome"
    monkeypatch.setenv("RCX_HOME", str(d))
    return RcxHome(str(d))
