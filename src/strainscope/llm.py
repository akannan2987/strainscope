"""
src/strainscope/llm.py (StrainScope Phase 7): the one connection to a language model.
=====================================================================================

WHAT THIS FILE IS
-----------------
Three features can ask a language model for a few sentences: Ask StrainScope
(src/strainscope/ask.py, Phase 6b), Ask the data (src/strainscope/ask_data.py)
and Ask the graph (src/strainscope/ask_graph.py), both Phase 7. They share one
connection, and this file holds it: reading the settings, sending one request,
checking that an answer cites what it was given, and a daily cap for a copy
that other people use.

Every feature works without a model. With STRAINSCOPE_ASK_BACKEND unset (or
"none"), nothing is ever sent anywhere and the features answer by search and
by rules alone.

THE SETTINGS (from the shell, the git-ignored .env file, or a host's secrets)
----------------------------------------------------------------------------
    STRAINSCOPE_ASK_BACKEND     none | local | hosted          (default none)
    STRAINSCOPE_ASK_MODEL       local default llama3.2:3b; hosted: required
    STRAINSCOPE_ASK_URL         local default http://localhost:11434/v1; hosted: required
    STRAINSCOPE_ASK_KEY         hosted only; never in Git, never in a request body
    STRAINSCOPE_AI_DAILY_LIMIT  requests to the model per day for this copy
                                (default: 200 in shared mode, no cap otherwise;
                                0 means none at all)

"local" is Ollama on the same computer; "hosted" is any provider with an
OpenAI-compatible interface. docs/07b-docs-assistant.md (sections 8 and 9)
and docs/08-deployment-ai.md (section 10) show both.

WHAT A MODEL MAY SEE
--------------------
Only text that is already public in the repository: documentation passages
(Ask StrainScope), the database's table and column names with tested example
queries (Ask the data), and facts from the knowledge layer of the graph, which
come from the domain model and public references (Ask the graph). Never a
row of data, a strain's measurements, an upload or a key. The callers build
their messages; the tests check each one.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
from dataclasses import dataclass

LOCAL_URL = "http://localhost:11434/v1"
LOCAL_MODEL = "llama3.2:3b"
SHARED_DAILY_LIMIT = 200     # requests per day when STRAINSCOPE_MODE=public and no limit is set
TIMEOUT_S = 120              # seconds to wait for an answer


@dataclass
class Settings:
    """Which model to ask, and where. `key` is never printed and never sent in a request body."""
    backend: str = "none"               # none | local | hosted
    url: str = ""
    model: str = ""
    key: str = ""

    @property
    def on(self) -> bool:
        return self.backend != "none"

    def describe(self) -> str:
        if self.backend == "none":
            return "off (search only; nothing leaves this computer)"
        where = "on this computer" if self.backend == "local" else "hosted"
        return f"{self.backend}: {self.model} at {self.url} ({where})"


def settings(env: dict | None = None) -> Settings:
    """The settings from the shell, or from the git-ignored .env file (the
    shell wins, as everywhere in StrainScope). An unknown backend counts as none."""
    if env is None:
        from strainscope.sources.base import load_env
        load_env()
        env = os.environ
    backend = env.get("STRAINSCOPE_ASK_BACKEND", "none").strip().lower() or "none"
    if backend not in ("none", "local", "hosted"):
        backend = "none"
    url = env.get("STRAINSCOPE_ASK_URL", "").strip() or (LOCAL_URL if backend == "local" else "")
    model = env.get("STRAINSCOPE_ASK_MODEL", "").strip() or (LOCAL_MODEL if backend == "local" else "")
    return Settings(backend, url.rstrip("/"), model, env.get("STRAINSCOPE_ASK_KEY", "").strip())


# =============================================================================
# The daily cap: a shared copy can't spend a hosted key without limit
# =============================================================================

class DailyCap:
    """Counts requests to the model per day (UTC) for this running copy.
    `limit=None` means no cap. The count lives in memory: a restart starts
    again from zero, which is fine for a cap meant to stop runaway use."""

    def __init__(self, limit: int | None):
        self.limit = limit
        self.day = dt.datetime.now(dt.timezone.utc).date()
        self.used = 0
        self._lock = threading.Lock()

    def take(self) -> bool:
        """Count one request. False when today's requests are used up."""
        with self._lock:
            today = dt.datetime.now(dt.timezone.utc).date()
            if today != self.day:
                self.day, self.used = today, 0
            if self.limit is not None and self.used >= self.limit:
                return False
            self.used += 1
            return True

    def describe(self) -> str:
        if self.limit is None:
            return f"{self.used} model request(s) today, no daily cap"
        return f"{self.used} of {self.limit} model requests used today (UTC)"


def daily_limit(env: dict | None = None) -> int | None:
    """STRAINSCOPE_AI_DAILY_LIMIT as a number; unset means 200 in shared
    mode and no cap otherwise. Something that isn't a whole number counts
    as unset."""
    env = os.environ if env is None else env
    raw = env.get("STRAINSCOPE_AI_DAILY_LIMIT", "").strip()
    if raw.isdigit():
        return int(raw)
    shared = env.get("STRAINSCOPE_MODE", "local").strip().lower() == "public"
    return SHARED_DAILY_LIMIT if shared else None


_CAP: DailyCap | None = None
_CAP_LOCK = threading.Lock()


def daily_cap() -> DailyCap:
    """The cap for this running copy, made on first use (after the settings
    have been read, so a host's secrets count)."""
    global _CAP
    with _CAP_LOCK:
        if _CAP is None:
            _CAP = DailyCap(daily_limit())
        return _CAP


# =============================================================================
# One request
# =============================================================================

def chat(messages: list[dict], cfg: Settings, timeout: float = TIMEOUT_S,
         cap: DailyCap | None = None) -> tuple[str | None, str | None]:
    """Send one chat request and return (text, None), or (None, a sentence
    saying what went wrong and what to do). Never raises: the feature that
    asked carries on without a written answer."""
    if not cfg.on:
        return None, None
    if not cfg.url or not cfg.model:
        return None, "Written answers need STRAINSCOPE_ASK_URL and STRAINSCOPE_ASK_MODEL (see .env.example)."
    if cfg.backend == "hosted" and not cfg.key:
        return None, "The hosted backend needs STRAINSCOPE_ASK_KEY in your .env file (see .env.example)."
    cap = cap or daily_cap()
    if not cap.take():
        return None, (f"This copy has used its {cap.limit} model requests for today, so there's no written "
                      "answer until tomorrow (UTC).")
    import requests
    headers = {"Content-Type": "application/json"}
    if cfg.key:
        headers["Authorization"] = f"Bearer {cfg.key}"           # the key goes where the provider expects it
    body = {"model": cfg.model, "messages": messages, "temperature": 0}
    session = requests.Session()
    session.trust_env = cfg.backend != "local"     # a model on this computer is never reached through a proxy
    try:
        r = session.post(f"{cfg.url}/chat/completions", headers=headers, data=json.dumps(body), timeout=timeout)
    except requests.Timeout:
        return None, (f"The model at {cfg.url} took longer than {timeout:.0f} seconds to answer. A smaller "
                      "model is quicker (see docs/07b-docs-assistant.md section 8).")
    except requests.RequestException:
        hint = " Is Ollama running? (ollama -v)" if cfg.backend == "local" else ""
        return None, f"Couldn't reach the model at {cfg.url}.{hint}"
    if r.status_code != 200:
        return None, (f"The model service answered with HTTP {r.status_code}. Check the model name "
                      f"({cfg.model}) and, for a hosted service, the key.")
    try:
        return r.json()["choices"][0]["message"]["content"].strip(), None
    except (ValueError, KeyError, IndexError, TypeError):
        return None, "The model service sent something that isn't a chat answer."


# =============================================================================
# Checking an answer before it's shown
# =============================================================================

NO_ANSWER = "doesn't cover this"      # the sentence every prompt asks for when the material has no answer


def citation_problem(text: str, given: int) -> str | None:
    """None when the answer cites at least one of the numbered items it was
    given ([1] to [given]) and nothing else; otherwise why it can't be shown."""
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    if not cited:
        return "it cites nothing"
    if not cited <= set(range(1, given + 1)):
        return "it cites something it wasn't given"
    return None


def numbers(text: str) -> set[str]:
    """The numbers written in a text, as they're written ('7.6', '22', '0.94').
    Citation marks such as [2] don't count."""
    text = re.sub(r"\[\d+\]", " ", text)
    return {m.rstrip(".") for m in re.findall(r"\d+(?:[.,]\d+)?", text)}


def invented_numbers(answer: str, source: str) -> set[str]:
    """Numbers in an answer that appear nowhere in the material it was given.
    A model that rephrases facts has no reason to add a number of its own."""
    return {n for n in numbers(answer) if n not in numbers(source) and n.replace(",", "") not in numbers(source)}
