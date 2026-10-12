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
