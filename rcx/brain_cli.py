"""CLI-driver brain — Unclaw take: drive a subscription CLI, pay $0 API.

Any CLI agent (Claude Code, etc.) becomes one more brain behind the provider
socket. The prompt goes in (argv or stdin), text comes out, calls count
against a budget. The hard shell layer refuses dangerous commands — driving
a CLI never bypasses policy.

The runner is injectable so tests never spawn processes.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from rcx.policy import hard_check_shell


@dataclass
class CliResult:
    ok: bool
    text: str
    code: int = 0
    detail: str = ""


RunnerFn = Callable[[List[str], str, int], CliResult]


def default_runner(argv: List[str], prompt: str, timeout: int) -> CliResult:
    """Run argv with prompt on stdin. Refuses hard-blocked commands."""
    cmd = " ".join(argv)
    hit = hard_check_shell(cmd)
    if hit:
        return CliResult(ok=False, text="", code=126, detail=f"refused: {hit}")
    try:
        pr = subprocess.run(argv, input=prompt, capture_output=True, text=True,
                            timeout=timeout)
        return CliResult(ok=pr.returncode == 0, text=pr.stdout or "",
                         code=pr.returncode, detail=(pr.stderr or "")[-200:])
    except subprocess.TimeoutExpired:
        return CliResult(ok=False, text="", code=124, detail="timeout")
    except FileNotFoundError:
        return CliResult(ok=False, text="", code=127, detail=f"not found: {argv[0]}")
    except Exception as e:
        return CliResult(ok=False, text="", code=1, detail=str(e)[:200])


class CliDriver:
    """A subscription CLI as a brain. Budget counts calls, not tokens."""

    def __init__(self, argv: List[str], timeout: int = 120, max_calls: int = 20,
                 runner: Optional[RunnerFn] = None) -> None:
        if not argv:
            raise ValueError("cli driver needs an argv (e.g. ['claude', '-p'])")
        self.argv = argv
        self.timeout = timeout
        self.max_calls = max_calls
        self.runner = runner or default_runner
        self.calls = 0

    @property
    def exhausted(self) -> bool:
        return self.calls >= self.max_calls

    def ask(self, prompt: str) -> CliResult:
        if self.exhausted:
            return CliResult(ok=False, text="", code=429,
                             detail="call budget exhausted")
        self.calls += 1
        return self.runner(self.argv, prompt, self.timeout)

    def stats(self) -> Dict[str, object]:
        return {"argv": self.argv, "calls": self.calls,
                "max_calls": self.max_calls, "exhausted": self.exhausted}
