"""Cost log — record, rollup, CSV."""
from __future__ import annotations

from rcx.cost import CostLog


def test_record_and_rollup(home):
    c = CostLog(home)
    c.record("groq", "llama-3.3", 100, 50, 0.001)
    c.record("groq", "llama-3.3", 100, 50, 0.001)
    r = c.rollup()
    assert r["tin"] == 200 and r["tout"] == 100
    assert abs(r["total"] - 0.002) < 1e-9
    assert r["providers"]["groq"]["models"]["llama-3.3"]["in"] == 200


def test_rollup_empty_day(home):
    c = CostLog(home)
    r = c.rollup(day="2099-01-01")
    assert r["total"] == 0.0 and r["providers"] == {}


def test_csv_shape(home):
    c = CostLog(home)
    c.record("nvidia", "llama-3.2", 10, 5, 0.0)
    csv_text = c.to_csv()
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    assert lines[0] == "day,provider,model,in,tout,cost_usd"
    assert len(lines) == 2 and "nvidia" in lines[1] and "llama-3.2" in lines[1]


def test_csv_empty(home):
    c = CostLog(home)
    assert c.to_csv().splitlines()[0].startswith("day,provider")


def test_persistence(home):
    c = CostLog(home)
    c.record("groq", "m", 1, 1, 0.5)
    assert CostLog(home).rollup()["total"] == 0.5
