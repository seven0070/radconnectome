"""CLI face — command tree wiring (exit codes + key output)."""
from __future__ import annotations

import json
import os

import pytest

from rcx.cli import main


@pytest.fixture
def argv_home(home, monkeypatch):
    monkeypatch.setenv("RCX_HOME", str(home.root))
    return home


def run(argv, capsys):
    rc = main(argv)
    out, err = capsys.readouterr()
    return rc, out, err


def test_version(capsys):
    rc, out, _ = run(["version"], capsys)
    assert rc == 0 and "rcx v" in out


def test_no_args_prints_help(capsys):
    assert run([], capsys)[0] == 1


def test_connectome_show_empty(argv_home, capsys):
    rc, out, _ = run(["connectome", "show"], capsys)
    assert rc == 0 and "RadConnectome" in out


def test_connectome_query_missing(argv_home, capsys):
    rc, out, _ = run(["connectome", "query"], capsys)
    assert rc == 1


def test_connectome_hubs_replay(argv_home, capsys):
    assert run(["connectome", "hubs"], capsys)[0] == 0
    rc, out, _ = run(["connectome", "replay"], capsys)
    assert rc == 0 and "replay" in out


def test_tribe_show_predict(argv_home, capsys):
    assert run(["tribe", "show"], capsys)[0] == 0
    rc, out, _ = run(["tribe", "predict", "plan it", "--image"], capsys)
    assert rc == 0 and "activation" in out
    assert run(["tribe", "predict"], capsys)[0] == 1


def test_arc_run_and_json(argv_home, capsys):
    rc, out, _ = run(["arc", "run", "--seed", "0", "--n", "1"], capsys)
    assert rc == 0 and "3/3" in out
    rc, out, _ = run(["--json", "arc", "run", "--seed", "0", "--n", "1"], capsys)
    assert rc == 0 and json.loads(out)["total"] == 3


def test_graph_author_inspect(argv_home, capsys, home):
    assert run(["graph", "new", "demo goal"], capsys)[0] == 0
    rc, out, _ = run(["graph", "add-node", "write a.txt"], capsys)
    assert rc == 0
    rc, out, _ = run(["graph", "show"], capsys)
    assert rc == 0 and "demo goal" in out and "write a.txt" in out
    assert (home.root / "graph.json").exists()


def test_graph_bad_edge(argv_home, capsys):
    assert run(["graph", "add-edge"], capsys)[0] == 1
    assert run(["graph", "bogus"], capsys)[0] == 2  # argparse choice error


def test_skills_world_dream_evolve(argv_home, capsys):
    assert run(["skills", "list"], capsys)[0] == 0
    assert run(["skills", "get", "ghost"], capsys)[0] == 1
    assert run(["world", "add", "a", "likes", "b"], capsys)[0] == 0
    rc, out, _ = run(["world", "query", "likes"], capsys)
    assert rc == 0 and "likes" in out
    assert run(["world", "simulate", "restart", "a"], capsys)[0] == 0
    assert run(["dream", "generate", "--n", "2"], capsys)[0] == 0
    rc, out, _ = run(["evolve", "vote", "q?", "--opts", "a", "a", "b"], capsys)
    assert rc == 0 and "a" in out
    assert run(["evolve", "history"], capsys)[0] == 0


def test_sleep_cost(argv_home, capsys):
    assert run(["sleep"], capsys)[0] == 0
    rc, out, _ = run(["cost"], capsys)
    assert rc == 0 and "today" in out
