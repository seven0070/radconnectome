"""Hygiene — repo-wide invariants that must never regress."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_no_bare_typing_imports():
    """`from typing X` (without import) is a SyntaxError — caught here, not in CI."""
    bad = []
    for p in list((ROOT / "rcx").glob("*.py")) + list((ROOT / "tests").glob("*.py")):
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^from typing [A-Z]", ln):
                bad.append(f"{p.name}:{i}: {ln}")
    assert not bad, "\n".join(bad)


def test_no_fetch_outside_api():
    """Desktop security surface analogue: no raw network calls in rcx/ core."""
    bad = []
    for p in (ROOT / "rcx").glob("*.py"):
        text = p.read_text(encoding="utf-8")
        if re.search(r"\brequests\.(get|post)\b|\burllib\.request\.urlopen\b", text):
            bad.append(p.name)
    assert not bad, bad
