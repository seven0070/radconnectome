# RadConnectome — Manual (the spec; code follows this, not the reverse)

> *The agent with a wiring diagram. Every tool a synapse. Every agent a
> neuron. Every goal a behavior. Every claim a proof.*

## 1. Thesis

Frontier models score <1%→30% on ARC-AGI-3 (interactive skill-acquisition);
frameworks ship unverified action traces, evaporating sessions, and surprise
bills. RadConnectome is the **harness-first, graph-native, verification-first**
answer: any brain, one wiring diagram, machine proof for every claim.

## 2. Non-negotiable laws

1. **VERIFIED-only.** No machine check → never VERIFIED. LLM opinion is never
   a check. (`rcx/verify.py`)
2. **Budgets.** 16 plan tasks / 60 tool calls default. Exhaustion → NEEDS_USER,
   never fake success.
3. **Needle OFF.** No experimental routers in the sovereign path.
4. **Loopback + Bearer.** Local servers bind 127.0.0.1 only, token 0600.
5. **Human-readable truth.** `~/.rcx/` is JSON/Markdown. Nothing opaque.
6. **Observed, never invented.** Graph edges come from real runs. No edge
   without evidence.

## 3. Architecture (graph is the plan format)

```
brain/     providers + magnitude profiler + adaptive thinking budget
wiring/    rcx/connectome.py (neurons/synapses/STDP/rich-club) +
           rcx/tribe.py (text/vision/audio fusion, lag, ROI)
world/     entities + causal simulate (masked prediction) + history
skills/    Voyager library: code-as-skills, auto-curriculum proposes
swarm/     hive roster + blackboard relay + Docker isolation + x402
graph/     plan = node DAG (nodes carry checks; edges carry weights)
verify/    rcx/verify.py + rcx/arc.py (ARC-style held-out battery)
face/      CLI first, canvas second, auto admin panel third
sleep/     consolidation: memory + connectome replay + dream gym
```

## 4. P0 scope (this tag: v0.1)

- `rcx/home.py` — minimal home (root, config, JSON helpers)
- `rcx/connectome.py` — ported, proven (21 tests)
- `rcx/tribe.py` — ported, proven (17 tests)
- `rcx/policy.py` — capability constants + hard shell/path/URL layer + defaults
- `rcx/verify.py` — check kinds (file/shell/json) + VERIFIED/FAILED/UNVERIFIED
- `rcx/arc.py` — ARC-style novel-task battery stub (novel by construction)
- Gates: ported 38 tests + new policy/verify/arc tests, all green.

## 5. Later (explicitly NOT P0)

P1 graph planner + skills · P2 world simulate + sleep · P3 face + hive.
No new features until gates are live — the mistake every framework made.

## 6. Scoreboard

| Tag | Tests | ARC rule_solver | ARC random | E2E |
|---|---|---|---|---|
| v0.1 | 58 | — | — | — |
| v0.2 | 110 | 12/12 efficient | 0/12 (measures something) | CLI brain → graph → VERIFIED artifact |
| v0.3 | 132 | 12/12 efficient | counterfactual 2/2 (1.0), dream transfer 1.0 | world simulate + masked + practice + vote |
| v1.0 | 164 | 12/12 efficient | CLI 11/11, hive no-leak, panel snapshot, clean venv install | CLI face + canvas + hive + panel + CI |
| v1.1 | 170 | 24/24 efficient (6 families) | rule 5 seeds × 100%, random 0/24, grids to 8×8 | ARC expansion: rotate/invert/border |
| v1.2 | 177 | 24/24 efficient | good-actor promotes, bad-actor gated, 2nd night repeats | auto-curriculum: propose→dream→practice→promote + CLI |
| v1.3 | 186 | 24/24 efficient | bands order, adapt +1 on failure (capped), tools/verified tracked | adaptive thinking: bands→budget→adapt + CLI |
