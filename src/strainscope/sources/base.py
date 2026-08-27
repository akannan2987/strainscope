"""
base.py — the contract every real-data source follows.
=======================================================

THE BIG IDEA (read this first)
------------------------------
StrainScope can pull real data from several public scientific databases. Rather
than writing a separate, tangled script for each one, we define ONE common
"shape" — a contract — that every source must follow, and then each source is a
small "adapter" that fills in the details.

Everyday analogy: a wall socket. Your house has one standard socket shape; every
appliance (kettle, laptop, lamp) brings its own plug that fits that shape. Here,
`Source` is the socket. Each adapter (BacDive, PubChem, KEGG, ...) is a plug.
The rest of the project — and later the app — only ever talks to the socket, so
adding source #8 one day means writing one new small file, nothing else changes.

THE CONTRACT — three verbs every source implements
--------------------------------------------------
* probe()  — "what's out there?" A few cheap requests that COUNT what a real
             fetch would bring back, without downloading it. You always probe
             before you fetch (measure twice, cut once).
* fetch()  — download the raw responses EXACTLY as the API sent them, into
             data/raw/real/<source>/ — the untouched "evidence locker" — and
             append one row per action to the PROVENANCE LOG (fetch_log.csv):
             what was asked, when, from which URL, how much came back. That log
             is the answer to the auditor's question: "where did this number
             come from?"
* tidy()   — turn the saved raw responses into small, clean CSV tables in
             data/processed/real/. (Next phase, these join the project database
             alongside the synthetic tables.)

Note the separation: fetch() TALKS TO THE INTERNET, tidy() only reads files
already on disk. That means you can re-run tidy() endlessly — to fix a parsing
bug, say — without hammering anyone's servers or needing a connection.

POLITENESS — how to be a good API citizen
-----------------------------------------
Public scientific APIs are shared, free resources. Every adapter here:
  * pauses between requests (each source declares its own polite delay),
  * sends an identifying User-Agent (who is calling, and why),
  * retries a few times with growing pauses if a request fails,
  * and gives up with a clear, human-readable error instead of hammering away.
"""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# --- Where everything lives (relative to this file => works on any machine) ---
ROOT = Path(__file__).resolve().parents[3]          # the repo root
RAW_REAL = ROOT / "data" / "raw" / "real"           # untouched API responses
PROCESSED_REAL = ROOT / "data" / "processed" / "real"  # tidy CSV tables
FETCH_LOG = RAW_REAL / "fetch_log.csv"              # the provenance log

# Identify ourselves politely on every request.
USER_AGENT = "StrainScope/1.0 (educational multi-omics portfolio project)"


class Source:
    """The socket every adapter plugs into. Subclasses set `name`, `delay_s`,
    and implement probe(), fetch(), tidy()."""

    name: str = "base"          # short id, e.g. "bacdive"
    delay_s: float = 0.5        # polite pause between requests (seconds)

    # ---------------------------------------------------------------- helpers
    def raw_dir(self) -> Path:
        """This source's corner of the evidence locker (created on demand)."""
        d = RAW_REAL / self.name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get(self, url: str, *, as_json: bool = True, tries: int = 3):
        """One polite, retrying HTTP GET.

        * Waits `delay_s` BEFORE every request (politeness by default).
        * On failure (network hiccup, HTTP 5xx), waits longer and retries.
        * Raises a clear error after the last failed try.
        Returns parsed JSON (as_json=True) or raw text (as_json=False).
        """
        last_err: Exception | None = None
        for attempt in range(1, tries + 1):
            time.sleep(self.delay_s)                       # be polite, always
            try:
                resp = requests.get(url, headers={"User-Agent": USER_AGENT},
                                    timeout=30)
                if resp.status_code in (400, 404):
                    # 404 = "not found"; 400 = "I reject that question" (e.g.
                    # a character the server won't accept). Both are
                    # DETERMINISTIC — retrying the identical request cannot
                    # help — so hand back None as a *result* for the adapter
                    # to record, and keep the rest of the run alive.
                    return None
                resp.raise_for_status()                    # error on other 4xx/5xx
                return resp.json() if as_json else resp.text
            except Exception as err:                       # noqa: BLE001
                last_err = err
                if attempt < tries:
                    wait = 2 * attempt                     # 2s, then 4s ...
                    print(f"    ! request failed ({err}); retrying in {wait}s")
                    time.sleep(wait)
        raise RuntimeError(
            f"[{self.name}] could not reach {url} after {tries} tries: {last_err}\n"
            f"  Are you online? If you're behind a corporate proxy/VPN, try a "
            f"normal network. The API's status page may also help."
        )

    def save_raw(self, filename: str, payload) -> Path:
        """File a response in the evidence locker, exactly as received."""
        path = self.raw_dir() / filename
        if isinstance(payload, (dict, list)):
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        else:
            path.write_text(str(payload), encoding="utf-8")
        return path

    def log(self, action: str, query: str, url: str, n_results, status: str,
            note: str = "") -> None:
        """Append one row to the provenance log — the project's paper trail."""
        RAW_REAL.mkdir(parents=True, exist_ok=True)
        new_file = not FETCH_LOG.exists()
        with FETCH_LOG.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if new_file:
                writer.writerow(["timestamp_utc", "source", "action", "query",
                                 "url", "n_results", "status", "note"])
            writer.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             self.name, action, query, url, n_results, status, note])

    def write_table(self, filename: str, rows: list[dict]) -> Path:
        """Write a tidy list-of-dicts as a CSV into data/processed/real/."""
        PROCESSED_REAL.mkdir(parents=True, exist_ok=True)
        path = PROCESSED_REAL / filename
        if not rows:
            path.write_text("", encoding="utf-8")
            return path
        # Union of keys across rows, first-seen order => stable, complete header.
        cols: list[str] = []
        for r in rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=cols)
            writer.writeheader()
            writer.writerows(rows)
        return path

    # ------------------------------------------------------------ the contract
    def probe(self) -> None:
        raise NotImplementedError

    def fetch(self, limit: int = 25) -> None:
        raise NotImplementedError

    def tidy(self) -> None:
        raise NotImplementedError
