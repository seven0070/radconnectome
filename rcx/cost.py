"""Cost log — per-request tracking + CSV export (unclaude pattern).

Every brain call records provider/model/tokens/price. Daily rollups,
CSV export for humans. Plain JSON on disk.
"""
from __future__ import annotations

import csv
import io
import time
from typing import Any, Dict, List

from rcx.home import RcxHome, _read_json, _write_json


class CostLog:
    def __init__(self, home: RcxHome) -> None:
        self.home = home

    @property
    def path(self):
        return self.home.root / "cost.json"

    def _data(self) -> Dict[str, Any]:
        return _read_json(self.path, {})

    def record(self, provider: str, model: str, tin: int, tout: int,
               price: float) -> Dict[str, Any]:
        data = self._data()
        day = time.strftime("%Y-%m-%d")
        cell = data.setdefault(day, {}).setdefault(
            provider, {"in": 0, "out": 0, "cost": 0.0, "models": {}})
        cell["in"] += tin
        cell["out"] += tout
        cell["cost"] = round(cell["cost"] + price, 6)
        m = cell["models"].setdefault(model, {"in": 0, "out": 0, "cost": 0.0})
        m["in"] += tin
        m["out"] += tout
        m["cost"] = round(m["cost"] + price, 6)
        _write_json(self.path, data)
        return cell

    def rollup(self, day: str = "") -> Dict[str, Any]:
        data = self._data()
        day = day or time.strftime("%Y-%m-%d")
        providers = data.get(day, {})
        return {"day": day, "providers": providers,
                "total": round(sum(p.get("cost", 0.0) for p in providers.values()), 6),
                "tin": sum(p.get("in", 0) for p in providers.values()),
                "tout": sum(p.get("out", 0) for p in providers.values())}

    def to_csv(self) -> str:
        """day,provider,model,in,out,cost — for humans and spreadsheets."""
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["day", "provider", "model", "in", "tout", "cost_usd"])
        for day in sorted(self._data()):
            for prov, cell in self._data()[day].items():
                for model, m in cell.get("models", {}).items():
                    w.writerow([day, prov, model, m["in"], m["out"], m["cost"]])
        return buf.getvalue()
