"""
tests/test_safety_gate.py: offline tests for the pre-push safety gate.
======================================================================
The safety gate (check-public-safe.sh, in the project folder) is the last
line of defence before something becomes public, so it gets tests of its own.
Each test builds a tiny throw-away Git repository in a temporary folder,
copies the gate into it, sets up one situation, runs the gate and checks its
verdict (exit code 0 = safe, 1 = not safe).

The situations come from real events in this project:
  * a NEW file holding a key must be caught even before `git add`, because the
    gate runs before staging and an earlier version only looked at tracked files
    (fixed in v0.1.1; story in docs/01-setup.md, Part H);
  * a key in an ignored file (.env) is fine, since Git will never publish it;
  * a key in a FORCE-added ignored file must be caught;
  * a link anchor such as "#ask-strainscope-..." contains the letters "sk-"
    followed by many letters (the shape of a key) and must NOT raise a
    false alarm (fixed in v0.1.0; story in docs/04-integration.md, §12).

Key-shaped values are assembled while the test runs (for example
"sk-" + "a" * 24), so this file itself never contains one. The gate scans
this file too, every time you run it on the real repository.

Needs `bash` and `git`; skipped on Windows, where `bash` may belong to a
different system (WSL). There, run the gate from Git Bash, as the setup guide
shows.

Run:  pytest -q tests/test_safety_gate.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "check-public-safe.sh"
FAKE_KEY = "sk-" + "a" * 24          # shaped like a real key; built at run time

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None or shutil.which("git") is None,
    reason="needs bash and git on macOS or Linux (on Windows, run the gate from Git Bash)")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A fresh repository with one committed file, the gate, and a .gitignore."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.org")
    _git(tmp_path, "config", "user.name", "test")
    shutil.copy(GATE, tmp_path / "check-public-safe.sh")
    (tmp_path / ".gitignore").write_text(".env\ndata/*\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "start")
    return tmp_path


def _gate(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "check-public-safe.sh"], cwd=repo,
                          capture_output=True, text=True)


def test_clean_repository_is_safe(repo):
    result = _gate(repo)
    assert result.returncode == 0, result.stdout
    assert "SAFE TO PUSH" in result.stdout


def test_new_file_with_key_is_caught_before_git_add(repo):
    (repo / "notes.txt").write_text(f"OPENAI_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    result = _gate(repo)                       # note: no `git add` happened
    assert result.returncode == 1, result.stdout
    assert "notes.txt" in result.stdout


def test_key_in_ignored_env_file_is_not_publishable(repo):
    (repo / ".env").write_text(f"OPENAI_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    result = _gate(repo)
    assert result.returncode == 0, result.stdout


def test_force_added_ignored_file_is_caught(repo):
    (repo / ".env").write_text(f"OPENAI_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    _git(repo, "add", "-f", ".env")
    result = _gate(repo)
    assert result.returncode == 1, result.stdout
    assert ".env" in result.stdout


def test_link_anchor_is_not_mistaken_for_a_key(repo):
    (repo / "guide.md").write_text(
        "See [the assistant](ROADMAP.md#ask-strainscope--the-documentation-assistant-in-detail).\n",
        encoding="utf-8")
    result = _gate(repo)
    assert result.returncode == 0, result.stdout


# =============================================================================
# The optional pre-push hook (.githooks/pre-push, Phase 8): the same gate,
# run by Git itself just before a push.
# =============================================================================

HOOK = ROOT / ".githooks" / "pre-push"


@pytest.fixture
def hooked(repo: Path, tmp_path_factory) -> Path:
    """The throw-away repository with the hook switched on and a remote to push to."""
    (repo / ".githooks").mkdir()
    shutil.copy(HOOK, repo / ".githooks" / "pre-push")
    (repo / ".githooks" / "pre-push").chmod(0o755)
    _git(repo, "config", "core.hooksPath", ".githooks")
    remote = tmp_path_factory.mktemp("remote")
    _git(remote, "init", "-q", "--bare")
    _git(repo, "remote", "add", "origin", str(remote))
    return repo


def _push(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "push", "-q", "origin", "HEAD:master"], cwd=repo,
                          capture_output=True, text=True)


def test_the_hook_lets_a_clean_push_through(hooked):
    result = _push(hooked)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SAFE TO PUSH" in result.stdout + result.stderr


def test_the_hook_stops_a_push_when_the_gate_finds_a_key(hooked):
    (hooked / "notes.txt").write_text(f"OPENAI_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    result = _push(hooked)
    assert result.returncode != 0
    assert "NOT SAFE TO PUSH" in result.stdout + result.stderr


def test_the_hook_is_marked_runnable():
    """Git runs a hook only if it's marked runnable. Before the first commit
    that's the file's own mark; once committed, it's the mode Git recorded."""
    import os
    staged = subprocess.run(["git", "ls-files", "-s", ".githooks/pre-push"], cwd=ROOT,
                            capture_output=True, text=True).stdout.split()
    if staged:
        assert staged[0] == "100755", "run: chmod +x .githooks/pre-push, then git add it again"
    else:
        assert os.access(HOOK, os.X_OK), "run: chmod +x .githooks/pre-push"
