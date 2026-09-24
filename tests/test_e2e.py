"""End-to-end exit criterion: CLI brain → graph plan → verified artifact.

A fake CLI brain proposes node actions; the executor walks the graph;
the verifier confirms the artifact. No real processes, no network.
"""
from __future__ import annotations

from rcx.brain_cli import CliDriver, CliResult
from rcx.planner import Executor, decompose
from rcx.verify import VERIFIED


def test_e2e_cli_brain_to_verified_artifact(home, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()

    def fake_runner(argv, prompt, timeout):
        # the "brain": writes the file the plan asks for, reports DONE
        (ws / "hello.txt").write_text("hello radconnectome")
        return CliResult(ok=True, text="DONE: wrote hello.txt", code=0)

    brain = CliDriver(["fake-cli"], runner=fake_runner)
    graph = decompose("Write hello.txt")
    assert len(graph.nodes) >= 1

    def act(nid, text):
        r = brain.ask(f"do this step: {text}")
        assert r.ok
        return (r.text, ["hello.txt"])

    ex = Executor(ws)
    res = ex.run(graph, act)
    assert res["status"] == VERIFIED
    assert (ws / "hello.txt").read_text() == "hello radconnectome"
    assert brain.calls >= 1
