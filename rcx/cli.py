"""CLI face — full command tree. Thin wrappers; modules decide.

    python -m rcx <command> [args]

Every command prints human text by default, --json for machines.
Exit codes: 0 ok, 1 usage/validation, 2 a check failed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rcx import __version__
from rcx.home import RcxHome


def _home(args) -> RcxHome:
    return RcxHome(getattr(args, "home", None))


def _out(args, payload: Dict[str, Any], lines: List[str]) -> int:
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        for ln in lines:
            print(ln)
    return 0


# ------------------------------------------------------------ connectome
def cmd_connectome(args) -> int:
    from rcx.connectome import Connectome, ingest_objective_events
    home = _home(args)
    cx = Connectome(home)
    act = args.action
    if act == "show":
        st = cx.stats()
        return _out(args, st, [
            f"RadConnectome — {st['neurons']} neurons, {st['synapses']} synapses "
            f"({st['verified_edges']} verified)",
            f"rich club: {', '.join(st['rich_club'][:8]) or '(empty)'}"])
    if act == "ingest":
        res = ingest_objective_events(home)
        return _out(args, res, [
            f"ingested {res['tasks']} task(s) → {res['edges']} edge(s)"])
    if act == "query":
        if not args.term:
            print("usage: rcx connectome query <neuron>", file=sys.stderr)
            return 1
        name = " ".join(args.term)
        outs = cx.neighbors(name, "out")
        lines = [f"{name}"] + [
            f"  → {s.post} w={s.weight:.2f} {'VERIFIED' if s.verified else ''}"
            for s in outs]
        return _out(args, {"neuron": name, "out": [s.to_dict() for s in outs]},
                    lines or [f"{name} (no synapses)"])
    if act == "path":
        if len(args.term) < 2:
            print("usage: rcx connectome path <from> <to>", file=sys.stderr)
            return 1
        p = cx.path(args.term[0], args.term[1])
        return _out(args, {"path": p}, [" → ".join(p)] if p else ["no path"])
    if act == "hubs":
        hubs = cx.rich_club()
        return _out(args, {"hubs": hubs}, ["rich club:"] + [f"  • {h}" for h in hubs])
    if act == "replay":
        res = cx.sleep_replay()
        return _out(args, res, [
            f"replay: {res['decayed']} decayed, {res['pruned']} pruned"])
    print(f"unknown connectome action: {act}", file=sys.stderr)
    return 1


# ------------------------------------------------------------ tribe
def cmd_tribe(args) -> int:
    from rcx.tribe import MultimodalEvent, TribeEncoder
    home = _home(args)
    enc = TribeEncoder(home)
    act = args.action
    if act == "show":
        st = enc.stats()
        lines = ["RadTribe — multimodal encoder"]
        lines += [f"  {m}: {w:.3f}" for m, w in sorted(st["weights"].items())]
        return _out(args, st, lines)
    if act == "predict":
        text = " ".join(args.term)
        if not text and not args.image and not args.audio:
            print("usage: rcx tribe predict <text...> [--image] [--audio]",
                  file=sys.stderr)
            return 1
        ev = MultimodalEvent(text=text, has_image=args.image,
                             has_audio=args.audio, at=time.time())
        energy = enc.activation_energy(ev)
        roi = enc.roi_map(ev)
        lines = [f"activation: {energy:.2f}"]
        lines += [f"  • {r} {roi[r]:.2f}" for r in enc.suggest_regions(ev)]
        return _out(args, {"energy": energy, "roi": roi}, lines)
    if act == "calibrate":
        res = enc.calibrate_from_connectome()
        return _out(args, res, [f"calibrated: {res['weights']}"])
    print(f"unknown tribe action: {act}", file=sys.stderr)
    return 1


# ------------------------------------------------------------ arc
def cmd_arc(args) -> int:
    from rcx.arc import generate, random_baseline, rule_solver, run
    tasks = generate(n_per_family=args.n, seed=args.seed)
    solver = random_baseline if args.solver == "random" else rule_solver
    rep = run(tasks, solver)
    d = rep.to_dict()
    lines = [f"ARC battery ({args.solver}, seed {args.seed}): "
             f"{rep.passed}/{rep.total} passed, {rep.efficient} efficient "
             f"(rate {rep.rate:.2f})"]
    rc = 0 if rep.rate == 1.0 else 2
    return _out(args, d, lines) or rc


# ------------------------------------------------------------ graph
_GRAPH: Dict[str, Any] = {}


def cmd_graph(args) -> int:
    from rcx.graph import PlanGraph
    home = _home(args)
    path = home.root / "graph.json"
    act = args.action
    if act == "new":
        g = PlanGraph(goal=" ".join(args.term))
        g.save(path)
        return _out(args, {"goal": g.goal}, [f"new graph: {g.goal or '(empty goal)'}"])
    g = PlanGraph.load(path) if path.exists() else PlanGraph()
    if act == "add-node":
        n = g.add_node(" ".join(args.term) or "step")
        g.save(path)
        return _out(args, {"id": n.id}, [f"node {n.id}: {n.text}"])
    if act == "add-edge":
        if len(args.term) < 2:
            print("usage: rcx graph add-edge <from> <to>", file=sys.stderr)
            return 1
        try:
            g.add_edge(args.term[0], args.term[1])
        except (KeyError, ValueError) as e:
            print(f"refused: {e}", file=sys.stderr)
            return 1
        g.save(path)
        return _out(args, {"edge": args.term[:2]}, ["edge added"])
    if act == "show":
        lines = [f"goal: {g.goal}"]
        for nid in g.topo():
            n = g.nodes[nid]
            deps = ",".join(g.predecessors(nid)) or "-"
            lines.append(f"  [{n.status}] {nid} {n.text[:60]} (deps {deps})")
        return _out(args, g.to_dict(), lines)
    if act == "flow":
        return _out(args, g.to_flow(), [json.dumps(g.to_flow())])
    print(f"unknown graph action: {act}", file=sys.stderr)
    return 1


# ------------------------------------------------------------ skills
def cmd_skills(args) -> int:
    from rcx.skills import SkillLibrary
    lib = SkillLibrary(_home(args))
    act = args.action
    if act == "list":
        skills = lib.all()
        return _out(args, {"skills": [s.to_dict() for s in skills]},
                    [f"{s.name} (strength {s.strength:.2f}, uses {s.uses})" for s in skills]
                    or ["(no skills — solve tasks first)"])
    if act == "get":
        s = lib.get(" ".join(args.term))
        if s is None:
            print("no such skill", file=sys.stderr)
            return 1
        return _out(args, s.to_dict(), [s.code])
    if act == "curriculum":
        res = lib.propose_curriculum()
        return _out(args, res, [str(res)])
    print(f"unknown skills action: {act}", file=sys.stderr)
    return 1


# ------------------------------------------------------------ world / dream / evolve / sleep / cost
def cmd_world(args) -> int:
    from rcx.world import WorldModel
    w = WorldModel(_home(args))
    act = args.action
    if act == "query":
        hits = w.query(" ".join(args.term))
        return _out(args, {"hits": hits},
                    [str(h) for h in hits] or ["(no matches)"])
    if act == "add":
        if len(args.term) < 3:
            print("usage: rcx world add <from> <rel> <to>", file=sys.stderr)
            return 1
        r = w.add_relation(args.term[0], args.term[1], " ".join(args.term[2:]))
        return _out(args, r.to_dict(), [f"{r.frm} –{r.rel}–> {r.to}"])
    if act == "simulate":
        if len(args.term) < 2:
            print("usage: rcx world simulate <action> <target>", file=sys.stderr)
            return 1
        p = w.simulate(args.term[0], args.term[1])
        return _out(args, p.to_dict(), [f"predicted: {', '.join(p.predicted) or '(none)'}"[:200]])
    print(f"unknown world action: {act}", file=sys.stderr)
    return 1


def cmd_dream(args) -> int:
    from rcx.dream import generate
    home = _home(args)
    tasks = generate(home, n=args.n)
    lines = [f"dreamed {len(tasks)} task(s):"]
    lines += [f"  • {t.filename} (from {t.source_path})" for t in tasks]
    return _out(args, {"tasks": [t.to_dict() for t in tasks]}, lines)


def cmd_evolve(args) -> int:
    from rcx.evolve import Evolver
    ev = Evolver(_home(args))
    act = args.action
    if act == "vote":
        r = ev.refine(" ".join(args.term) or "?", args.opts)
        verdict = "DECISIVE" if r["decisive"] else "ABSTAIN"
        return _out(args, r, [f"{verdict}: {r['winner']}"])
    if act == "history":
        hist = ev.history()
        return _out(args, {"history": hist},
                    [f"{h['winner']} ({h['n']} votes)" for h in hist] or ["(empty)"])
    print(f"unknown evolve action: {act}", file=sys.stderr)
    return 1


def cmd_curriculum(args) -> int:
    from rcx import curriculum as _cu
    from rcx import dream as _dream
    home = _home(args)
    act = args.action
    if act == "history":
        hist = _cu.history(home)
        return _out(args, {"history": hist},
                    [f"promoted={h.get('promoted')} transfer={h.get('transfer')}"
                     for h in hist] or ["(no cycles yet)"])
    if act == "run":
        rep = _cu.run_cycle(home, _dream.write_actor, n=args.n)
        lines = [f"proposed: {rep['proposed']}, transfer: {rep['transfer']:.2f}, "
                 f"promoted: {rep['promoted']}"
                 + (f" ({rep['skill']})" if rep.get("skill") else "")]
        return _out(args, rep, lines)
    print(f"unknown curriculum action: {act}", file=sys.stderr)
    return 1


def cmd_thinking(args) -> int:
    from rcx.thinking import ThinkingBudget
    tb = ThinkingBudget(_home(args))
    act = args.action
    if act == "report":
        r = tb.report()
        lines = ["tools-per-verified (down is better):"]
        for b, s in r["bands"].items():
            cpv = s["tools_per_verified"]
            lines.append(f"  {b:<8} {s['verified']}/{s['tasks']} verified · "
                         f"{'—' if cpv is None else f'{cpv:.1f}'} tools/verified · "
                         f"{s['attempts']} attempts")
        lines.append(f"overall: {r['overall_tools_per_verified']}")
        return _out(args, r, lines)
    if act == "budget":
        text = " ".join(args.term) or "task"
        b = tb.allocate(text)
        return _out(args, b, [f"{b['band']}: {b['attempts']} attempts, "
                              f"{b['tools']} tools (cap {b['cap']})"])
    print(f"unknown thinking action: {act}", file=sys.stderr)
    return 1


def cmd_sleep(args) -> int:
    from rcx.sleep import run_sleep
    rep = run_sleep(_home(args))
    gate = rep.get("gate", {})
    lines = [f"sleep: replay {rep.get('replay', {})}",
             f"proposal: {rep.get('proposal', {}).get('proposed')}",
             f"gate passed: {gate.get('passed')}"]
    return _out(args, rep, lines)


def cmd_cost(args) -> int:
    from rcx.cost import CostLog
    c = CostLog(_home(args))
    if args.csv:
        print(c.to_csv(), end="")
        return 0
    r = c.rollup()
    return _out(args, r, [f"today: ${r['total']:.4f} ({r['tin']} in / {r['tout']} out)"])


def cmd_version(args) -> int:
    print(f"rcx v{__version__}")
    return 0


# ------------------------------------------------------------ parser
def build_parser() -> "argparse.ArgumentParser":
    import argparse
    p = argparse.ArgumentParser(prog="rcx", description="RadConnectome CLI")
    p.add_argument("--home", default=None)
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    def add(name: str, actions: List[str], help: str, fn, extra=None):
        c = sub.add_parser(name, help=help)
        c.add_argument("action", nargs="?", default=actions[0], choices=actions)
        c.add_argument("term", nargs="*")
        if extra:
            extra(c)
        c.set_defaults(fn=fn)
        return c

    add("connectome", ["show", "ingest", "query", "path", "hubs", "replay"],
        "wiring diagram (neuPrint for agents)", cmd_connectome)
    add("tribe", ["show", "predict", "calibrate"], "multimodal prior", cmd_tribe,
        lambda c: (c.add_argument("--image", action="store_true"),
                   c.add_argument("--audio", action="store_true")))
    ac = add("arc", ["run"], "novel-task battery", cmd_arc,
             lambda c: (c.add_argument("--seed", type=int, default=0),
                        c.add_argument("--n", type=int, default=4),
                        c.add_argument("--solver", default="rule",
                                       choices=["rule", "random"])))
    ac.set_defaults(action="run")
    add("graph", ["show", "new", "add-node", "add-edge", "flow"],
        "plan DAG authoring", cmd_graph)
    add("skills", ["list", "get", "curriculum"], "skill library", cmd_skills)
    add("world", ["query", "add", "simulate"], "world model", cmd_world)
    add("dream", ["generate"], "dream gym", cmd_dream,
        lambda c: c.add_argument("--n", type=int, default=4))
    ev = add("evolve", ["vote", "history"], "majority vote", cmd_evolve,
             lambda c: c.add_argument("--opts", nargs="*", default=[]))
    cu = add("curriculum", ["run", "history"], "nightly auto-curriculum", cmd_curriculum,
             lambda c: c.add_argument("--n", type=int, default=4))
    th = add("thinking", ["report", "budget"], "adaptive thinking budget", cmd_thinking)
    sl = sub.add_parser("sleep", help="nightly refinement")
    sl.set_defaults(fn=cmd_sleep)
    co = sub.add_parser("cost", help="spend rollup")
    co.add_argument("--csv", action="store_true")
    co.set_defaults(fn=cmd_cost)
    v = sub.add_parser("version", help="version")
    v.set_defaults(fn=cmd_version)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    fn = getattr(args, "fn", None)
    if fn is None:
        build_parser().print_help()
        return 1
    return fn(args)
