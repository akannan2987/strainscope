"""
tests/conftest.py: what several test files share (pytest reads this file first).
================================================================================
  * model: a stand-in language-model server on this computer. It answers
    POST /v1/chat/completions the way an OpenAI-compatible service does,
    with whatever reply the test sets (server.reply), and remembers every
    request it got (server.calls), so a test can check exactly what would
    have been sent. Used by tests/test_ask.py, tests/test_ask_data.py and
    tests/test_ask_graph.py. No test needs the network, a real model or a key.
  * a fresh daily cap for every test (src/strainscope/llm.py keeps one per
    running copy, and a test must not use up another test's requests).
  * workflow_dataset: one small dataset of "your own" data (120 simulated
    strains saved as three tables, quick settings), with every phase run on
    it once for the whole test session (about a minute), in a folder of its
    own under pytest's temporary folder. tests/test_datasets.py and
    tests/test_app.py read it (Phase 9).
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strainscope import llm  # noqa: E402


class StandIn(BaseHTTPRequestHandler):
    """Answers like an OpenAI-compatible service and remembers every request."""

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.calls.append({"path": self.path, "body": body, "headers": dict(self.headers)})
        data = json.dumps({"choices": [{"message": {"role": "assistant", "content": self.server.reply}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture()
def model():
    server = HTTPServer(("127.0.0.1", 0), StandIn)
    server.calls, server.reply = [], "A balanced error rate averages the error on each group [1]."
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def stand_in(server, backend: str = "local", key: str = "") -> llm.Settings:
    """Settings that point at the stand-in server."""
    return llm.Settings(backend, f"http://127.0.0.1:{server.server_port}/v1", "stand-in", key)


@pytest.fixture(autouse=True)
def fresh_daily_cap():
    llm._CAP = None
    yield
    llm._CAP = None


@pytest.fixture(scope="session")
def workflow_dataset(tmp_path_factory):
    """A dataset of your own with every phase run on it: (folder, run output)."""
    import subprocess
    from strainscope import datasets as ds
    base = tmp_path_factory.mktemp("datasets")
    files = ds.write_tables(ds.example(120, 7), base.parent / "example_tables")    # as a person would have them
    check = ds.check_tables(*(ds.read_table(f)[0] for f in files))
    assert check.ok, check.errors
    home = ds.create("trial", check.tables, "yours", "tests/conftest.py", quick=True, base=base)
    before = _library_files()
    run = subprocess.run([sys.executable, str(ROOT / "src" / "strainscope" / "pipeline.py"),
                          "--dataset", str(home), "--quiet"], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", env={**__import__("os").environ, "PYTHONUTF8": "1",
                                                "STRAINSCOPE_RSCRIPT": "none"})
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    LIBRARY_FILES.update(before=before, after=_library_files())
    return home, run.stdout


LIBRARY_FILES: dict = {}        # the library's files before and after the run above


def _library_files() -> dict:
    """Every file of the library's results and pictures, with its size and time of change."""
    out = {}
    for folder in ("artifacts", "figures", "data/raw"):
        for f in (ROOT / folder).rglob("*"):
            if f.is_file():
                out[f.relative_to(ROOT).as_posix()] = (f.stat().st_size, f.stat().st_mtime_ns)
    return out
