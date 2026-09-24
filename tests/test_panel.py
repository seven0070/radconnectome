"""Panel — dashboard snapshot sections."""
from __future__ import annotations

from rcx.panel import collect, export_dashboard, render


def test_collect_sections(home):
    st = collect(home)
    assert set(st) == {"connectome", "tribe", "cost", "hive", "arc_baseline"}
    assert "neurons" in st["connectome"]
    assert "weights" in st["tribe"]


def test_arc_baseline_runs(home):
    st = collect(home)
    assert st["arc_baseline"]["rate"] == 1.0


def test_render_sections_present(home):
    html = render(collect(home), at="now")
    for title in ("connectome", "tribe", "cost", "hive", "arc_baseline"):
        assert title in html
    assert "static snapshot" in html


def test_export_writes_file(home, tmp_path):
    p = export_dashboard(home, tmp_path / "panel.html")
    assert p.exists()
    assert "RadConnectome Panel" in p.read_text(encoding="utf-8")
