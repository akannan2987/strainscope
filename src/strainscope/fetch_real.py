"""
fetch_real.py — the one command for real-data ingestion.
========================================================

WHAT THIS IS
------------
The front door to StrainScope's real-data framework. It drives the source
adapters in src/strainscope/sources/ through their three verbs:
probe (count what's out there), fetch (download raw + log provenance),
tidy (raw -> clean CSV tables).

HOW TO USE IT (from the project root, venv active)
--------------------------------------------------
    python src/strainscope/fetch_real.py --probe
        -> ask every source "what would a fetch bring back?" (cheap, no download)

    python src/strainscope/fetch_real.py
        -> fetch + tidy ALL sources (a few minutes; polite pauses dominate)

    python src/strainscope/fetch_real.py --source bacdive --limit 25
        -> just one source; --limit caps strains per genus (BacDive only)

Everything downloaded lands under data/raw/real/<source>/ untouched, every
action is logged to data/raw/real/fetch_log.csv, and the clean tables appear
in data/processed/real/. Re-running is safe (idempotent): it refetches and
rewrites the same files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `strainscope` importable no matter where the script is run from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strainscope.sources import SOURCES  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch real data from public scientific databases.")
    parser.add_argument("--probe", action="store_true",
                        help="only count what a fetch would bring back")
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="all",
                        help="which source to use (default: all)")
    parser.add_argument("--limit", type=int, default=25,
                        help="max strains per genus for BacDive (default 25)")
    args = parser.parse_args()

    chosen = list(SOURCES) if args.source == "all" else [args.source]
    print(f"Real-data ingestion — sources: {', '.join(chosen)}"
          f"{'  (probe only)' if args.probe else ''}")

    for key in chosen:
        source = SOURCES[key]()          # instantiate the adapter
        if args.probe:
            source.probe()
        else:
            source.fetch(limit=args.limit)
            source.tidy()

    if not args.probe:
        print("\nDone. Evidence locker: data/raw/real/   "
              "Provenance log: data/raw/real/fetch_log.csv   "
              "Clean tables: data/processed/real/")
        print("Reminder: real tables COMPLEMENT the synthetic library — no "
              "public source provides matched multi-omics with an outcome.")


if __name__ == "__main__":
    main()
