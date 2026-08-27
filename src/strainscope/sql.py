"""
sql.py — the StrainScope SQL console: ask the database questions, directly.
===========================================================================

WHAT THIS IS
------------
The missing piece between "here is SQL to read" and "here is SQL running".
Three ways to use it (from the project root, venv active):

1. ONE QUERY, straight from the shell (note the double quotes around it):

       python src/strainscope/sql.py "SELECT COUNT(*) FROM phenotype"

2. INTERACTIVE — a prompt where you paste queries one after another:

       python src/strainscope/sql.py
       sql> SELECT kingdom, COUNT(*) FROM phenotype GROUP BY kingdom;
       sql> .tables          (list every table)
       sql> exit

3. A FILE of SQL (handy for saving favourite cookbook queries):

       python src/strainscope/sql.py --file my_queries.sql

SAFE BY DEFAULT
---------------
The console opens the database READ-ONLY. You can look at anything and break
nothing — and it can't collide with a pipeline run holding the file. (This is
also why the "database is locked" worry doesn't apply here.)

If the database file doesn't exist yet, the console says so and tells you the
one command that builds it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "processed" / "strainscope.duckdb"

BANNER = """StrainScope SQL console — read-only, break-nothing mode.
Multi-line statements welcome: keep typing (or paste), and the query runs when
a line ends with ';' — or just press Enter on an empty line to run what's there.
Helpers: .tables   .schema TABLE   exit
Recipes to paste: docs/QUERY_COOKBOOK.md
"""


def run_query(sql: str, db_path: Path = DB_PATH):
    """Run one query read-only and return the result as a DataFrame.
    (Factored out so the tests can call it directly.)"""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute(sql).fetchdf()
    finally:
        con.close()


def _handle(sql: str, db_path: Path) -> None:
    """Run one statement (or a dot-helper) and print the result nicely."""
    sql = sql.strip().rstrip(";")
    if not sql:
        return
    if sql == ".tables":
        sql = ("SELECT table_name FROM information_schema.tables "
               "ORDER BY table_name")
    elif sql.startswith(".schema"):
        table = sql.split(maxsplit=1)[1] if " " in sql else ""
        sql = ("SELECT column_name, data_type FROM information_schema.columns "
               f"WHERE table_name = '{table}' ORDER BY ordinal_position")
    try:
        df = run_query(sql, db_path)
        # to_string keeps every row visible; pandas would otherwise fold
        # long results with "...". For very long results, LIMIT is your friend.
        print(df.to_string(index=False) if len(df) else "(no rows)")
    except Exception as err:                                   # noqa: BLE001
        # One bad query should never end your session — print and continue.
        print(f"  ! {err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the StrainScope database.")
    parser.add_argument("query", nargs="?", help="one SQL statement (in quotes)")
    parser.add_argument("--file", help="a .sql file of statements, ';'-separated")
    parser.add_argument("--db", default=str(DB_PATH),
                        help="path to the database (default: the project's)")
    args = parser.parse_args()
    db_path = Path(args.db)

    if not db_path.exists():
        sys.exit(f"No database at {db_path}.\n"
                 f"Build it first:  python src/strainscope/harmonize.py")

    if args.query:                                   # mode 1: one query
        _handle(args.query, db_path)
    elif args.file:                                  # mode 3: a file of SQL
        for stmt in Path(args.file).read_text(encoding="utf-8").split(";"):
            if stmt.strip():
                print(f"\nsql> {stmt.strip()}")
                _handle(stmt, db_path)
    else:                                            # mode 2: interactive
        print(BANNER)
        # A STATEMENT BUFFER, because SQL doesn't fit on one line. Lines
        # accumulate here until the statement is complete — signalled by a
        # trailing ';' or by an empty line — and only then does it run. This is
        # how every serious SQL shell behaves, and it's what makes pasting the
        # multi-line cookbook recipes Just Work.
        buffer: list[str] = []
        while True:
            prompt = "sql> " if not buffer else "  -> "     # continuation prompt
            try:
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print(); break
            stripped = line.strip()
            if not buffer and stripped.lower() in {"exit", "quit", "q"}:
                break
            if not buffer and stripped.startswith("."):     # dot-helpers: instant
                _handle(stripped, db_path)
                continue
            if stripped == "" and buffer:                   # blank line = run it
                _handle(" ".join(buffer), db_path)
                buffer = []
                continue
            if stripped == "":
                continue
            buffer.append(line)
            if stripped.endswith(";"):                      # ';' = statement done
                _handle(" ".join(buffer), db_path)
                buffer = []


if __name__ == "__main__":
    main()
