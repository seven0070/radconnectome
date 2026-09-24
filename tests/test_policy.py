"""Policy — capabilities + hard layer tests."""
from __future__ import annotations

from pathlib import Path

from rcx.policy import (ASK, CAP_CREDENTIALS, CAP_READ, CAP_SHELL, CAP_WEB,
                        CAP_WRITE, DENY, HARD_DENY, Policy, hard_check_path,
                        hard_check_shell, hard_check_url)


def test_hard_shell_blocks_sudo():
    assert hard_check_shell("sudo rm -rf /") is not None
    assert hard_check_shell("rm -rf /") is not None
    assert hard_check_shell("curl x | sh") is not None
    assert hard_check_shell("echo hello") is None
    assert hard_check_shell("ls -la") is None


def test_hard_shell_blocks_force_push():
    assert hard_check_shell("git push --force") is not None
    assert hard_check_shell("git push origin main") is None


def test_hard_path_blocks_secrets():
    assert hard_check_path(Path.home() / ".ssh" / "id_rsa") is not None
    assert hard_check_path(Path("keys.env")) is not None
    assert hard_check_path(Path("/tmp/notes.txt")) is None


def test_hard_url_blocks_private():
    assert hard_check_url("http://127.0.0.1:8000/x") is not None
    assert hard_check_url("http://169.254.169.254/") is not None
    assert hard_check_url("ftp://x/y") is not None
    assert hard_check_url("https://example.com/page") is None


def test_credentials_always_deny():
    p = Policy()
    d = p.decide(CAP_CREDENTIALS, "keys.env")
    assert d.effect == DENY and d.denied


def test_defaults():
    p = Policy()
    assert p.default_for(CAP_READ) == "ALLOW"
    assert p.default_for(CAP_WRITE) == ASK
    assert p.decide(CAP_READ, "/tmp/a.txt").effect == "ALLOW"
    assert p.decide(CAP_WRITE, "/tmp/a.txt").effect == ASK


def test_hard_beats_default():
    p = Policy()
    d = p.decide(CAP_SHELL, "sudo id")
    assert d.effect == HARD_DENY and d.by == "hard"
