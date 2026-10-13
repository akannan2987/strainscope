"""
src/strainscope/mcp_server.py (StrainScope Phase 7b): the MCP server.
======================================================================

WHAT THIS FILE IS
-----------------
A small server that speaks the Model Context Protocol (MCP), the common
"socket" through which AI assistant apps (Claude Desktop, Claude Code and
many others) can use another program's tools. Connect an assistant to it, and
you can ask in plain words "Why does STRAIN_0485 rank first?" or "Which
compounds are in DIABLO's signature?": the assistant decides which StrainScope
tool to call, the tool answers from this computer's results, and the
assistant writes the reply.

Nothing new is computed here. Every tool is a thin door onto a function the
terminal and the app already use (src/strainscope/service.py and the
assistants of Phases 6b and 7), so the answers are the same everywhere. The
guide is docs/08b-mcp-server.md.

THE TOOLS (all read-only)
-------------------------
    ask_docs(question)            Ask StrainScope: passages from the documents, with links
    ask_data(question)            Ask the data: a tested Query Cookbook recipe and its table
    ask_graph(question)           Ask the graph: walks through the knowledge graph, numbered facts
    describe_database()           every table, its columns and row count, and notes on what they hold
    query_database(sql, max_rows) one read-only SQL query behind five guards
    get_signature()               Phase 3's multi-omics signature (DIABLO) and its report card
    rank_strain(strain_id)        one strain's rank, chance and band
    explain_strain(strain_id)     why a strain ranks where it does, in plain words, with its routes
    shortlist(n)                  what testing the n best-ranked strains would bring

WHAT KEEPS IT SAFE
------------------
1. Read-only: no tool writes anything, and every SQL query goes through the
   fifth guard of Ask the data (one SELECT or WITH statement) and the SQL
   console's four (read-only database, no file access, a time limit, a row
   cap). Each tool also tells the assistant app it's read-only (MCP "tool
   annotations"), so apps can skip asking you to approve every call.
2. Checked input: a question has at most MAX_QUESTION characters, a strain id
   looks like STRAIN_0485 and exists, numbers stay within their limits.
   Anything else is refused with a sentence saying why.
3. A call log: every call is written as one line to data/processed/mcp_calls.log
   (tool, arguments, outcome, time taken; never the results). Git never
   commits it, and it never leaves this computer. (STRAINSCOPE_MCP_LOG can
   point it elsewhere; the tests use that.)
4. Local only: the server talks to the app that started it through stdin and
   stdout ("stdio"). It opens no network port. Uploads and keys are out of
   reach: no tool can read a file.
What a tool returns goes to the assistant you connected, and from there to
whatever model that assistant uses. The data is simulated; docs/08b-mcp-server.md
section 1 says what each tool can show.

THE COMMAND LINE
----------------
    python src/strainscope/mcp_server.py              run the server (what an assistant app starts)
    python src/strainscope/mcp_server.py tools        list the tools and their inputs
    python src/strainscope/mcp_server.py call rank_strain strain_id=STRAIN_0485
                                                      run one tool here, without an assistant
    python src/strainscope/mcp_server.py check        start the server the way an app does, list
                                                      its tools and call two of them
    python src/strainscope/mcp_server.py config       the settings to paste into an assistant app,
                                                      with this computer's paths filled in
    python src/strainscope/mcp_server.py config --write    add the strainscope entry to Claude
                                                      Desktop's settings file (Phase 8; a backup first)
    python src/strainscope/mcp_server.py config --remove   take it out again (docs/UNINSTALL.md)

"tools", "call" and "config" work without the mcp package; running the
server and "check" need it (it's in requirements.txt).
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import functools
import inspect
import json
import math
import os
import re
import sys
import time
from pathlib import Path

# Make `strainscope` importable no matter where the script is run from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strainscope import service as sv  # noqa: E402  (after the path fix)

SERVER_NAME = "strainscope"
LOG_PATH = Path(os.environ.get("STRAINSCOPE_MCP_LOG") or sv.ROOT / "data" / "processed" / "mcp_calls.log")
MAX_QUESTION = 300          # characters in a question
MAX_SQL = 4_000             # characters in a query
MAX_ROWS = 200              # rows a tool returns at most (the assistant has to read them)
STRAIN_ID = re.compile(r"^STRAIN_\d{4}$")

INSTRUCTIONS = (
    "StrainScope ranks a library of 600 beneficial microbe strains (bacteria, fungi, yeasts, oomycetes) by "
    "their chance of suppressing a plant disease, and explains each rank with a knowledge graph. The data is "
    "SIMULATED, so say so when you report results. All tools are read-only. For questions about the project "
    "or how to do something, use ask_docs. For numbers, try ask_data first (tested recipes); if no recipe fits, "
    "call describe_database and then query_database with one SELECT. For how things connect (genes, "
    "compounds, modes of action), use ask_graph. For one strain, use rank_strain and explain_strain. Quote the "
    "sources and links the tools return.")


class Refused(ValueError):
    """An input a tool won't accept, with the reason in plain words."""


# =============================================================================
# 1. Checking input, and the call log
# =============================================================================

def _question(text: str) -> str:
    text = " ".join(str(text or "").split())
    if not text:
        raise Refused("The question is empty. Ask something, for example: How does iturin suppress disease?")
    if len(text) > MAX_QUESTION:
        raise Refused(f"The question has {len(text)} characters; the limit is {MAX_QUESTION}. Ask a shorter one.")
    return text


def _whole(value, name: str, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise Refused(f"{name} must be a whole number from {low} to {high}; got {value!r}.") from None
    if not low <= number <= high or (isinstance(value, float) and value != number):
        raise Refused(f"{name} must be a whole number from {low} to {high}; got {value!r}.")
    return number


def _strain(strain_id: str) -> tuple[str, dict, int]:
    """The strain id in its proper form, its row of the ranking, and the number of strains."""
    sid = str(strain_id or "").strip().upper()
    if not STRAIN_ID.match(sid):
        raise Refused(f"{strain_id!r} isn't a strain id. They look like STRAIN_0485 (STRAIN_, then four digits).")
    pred = sv.read_artifact("model/predictions.csv")
    if pred is None:
        raise Refused("The ranking isn't there yet. Build it with: python src/strainscope/model.py all")
    row = pred[pred["strain_id"] == sid]
    if row.empty:
        raise Refused(f"There's no {sid} in the library (STRAIN_0001 to STRAIN_{len(pred):04d}).")
    return sid, row.iloc[0].to_dict(), len(pred)


def _plain(value):
    """The same value in plain JSON terms: numpy numbers become Python
    numbers, NaN becomes null, tuples become lists."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (ValueError, TypeError):
            return str(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _log(tool: str, arguments: dict, outcome: str, seconds: float, note: str = "", rows: int | None = None) -> None:
    """One line per call in data/processed/mcp_calls.log. Arguments are cut
    at 300 characters; results are never written. A log that can't be
    written never stops a tool."""
    entry = {"time": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "tool": tool,
             "arguments": {k: (str(v)[:300] if isinstance(v, str) else v) for k, v in arguments.items()},
             "outcome": outcome, "seconds": round(seconds, 3)}
    if rows is not None:
        entry["rows"] = rows
    if note:
        entry["note"] = note[:300]
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _run(tool: str, arguments: dict, work) -> dict:
    """Run one tool: time it, keep anything it prints off stdout (which
    carries the protocol), log the outcome, and hand back plain JSON."""
    start = time.time()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = _plain(work())
    except Refused as why:
        _log(tool, arguments, "refused", time.time() - start, str(why))
        raise
    except Exception as err:                        # a failure the assistant should hear about, in one line
        _log(tool, arguments, "error", time.time() - start, f"{type(err).__name__}: {err}")
        raise Refused(f"{tool} failed: {err}") from err
    rows = len(result["rows"]) if isinstance(result, dict) and isinstance(result.get("rows"), list) else None
    _log(tool, arguments, "ok", time.time() - start, rows=rows)
    return result


# =============================================================================
# 2. The tools
# =============================================================================

def ask_docs(question: str) -> dict:
    """Search StrainScope's own documentation (guides, Handbook, glossary, code
    docstrings) and return the best passages word for word, each with a link.
    The verdict is 'answered', 'closest' (the documents touch on it but don't
    answer it) or 'refused' (they don't cover it). Use it for how-to and
    what-is questions about the project."""
    def work():
        return sv.ask_docs(_question(question), write=False)
    return _run("ask_docs", {"question": question}, work)


def ask_data(question: str) -> dict:
    """Answer a question about the data with a tested SQL recipe from the
    project's Query Cookbook: the recipe it used, the SQL, and up to 50 rows.
    If no recipe fits, the verdict says so and lists the closest recipes; then
    use describe_database and query_database."""
    def work():
        out = sv.ask_data(_question(question), write=False, max_rows=50)
        out.pop("note", None)                      # a note about switching on a model doesn't apply here
        return out
    return _run("ask_data", {"question": question}, work)


def ask_graph(question: str) -> dict:
    """Answer how things connect (genes, compounds, modes of action, outcomes,
    pathways, strains) by walking StrainScope's knowledge graph. Returns the
    route and numbered facts, each with its source. A question about one strain
    gets that strain's explanation."""
    def work():
        return sv.ask_graph(_question(question), write=False)
    return _run("ask_graph", {"question": question}, work)


def describe_database() -> dict:
    """List every table in StrainScope's database with its columns and row
    count, plus notes on what the main tables hold. Call it before writing SQL
    for query_database."""
    def work():
        from strainscope import ask_data as data
        if not sv.DB_PATH.exists():
            raise Refused("There's no database yet. Build it with the five commands in docs/07-app.md section 5, "
                          "or press Build the database in the app.")
        counts = {r.table: int(r.rows) for r in sv.database_tables().itertuples(index=False)}
        tables = []
        for line in data.schema().splitlines():
            m = re.match(r"- (\w+)\((.*)\)$", line)
            if m:
                tables.append({"table": m.group(1), "rows": counts.get(m.group(1)),
                               "columns": [c.strip() for c in m.group(2).split(",")]})
        return {"tables": tables, "notes": data.SCHEMA_NOTES,
                "rules": "One read-only SELECT (or WITH) per call; at most 200 rows come back."}
    return _run("describe_database", {}, work)


def query_database(sql: str, max_rows: int = 50) -> dict:
    """Run one read-only SQL query (DuckDB dialect) on StrainScope's database
    and return the columns and up to max_rows rows (1 to 200). Only a single
    SELECT or WITH statement is accepted; anything that could change the
    database or read a file is refused. Use describe_database first."""
    def work():
        from strainscope import ask_data as data
        text = str(sql or "").strip()
        if len(text) > MAX_SQL:
            raise Refused(f"The query has {len(text)} characters; the limit is {MAX_SQL}.")
        problem = data.sql_problem(text)
        if problem:
            raise Refused(f"The query wasn't run: {problem}. Only one SELECT (or WITH) statement is allowed.")
        limit = _whole(max_rows, "max_rows", 1, MAX_ROWS)
        result = sv.query_database(text, max_rows=limit)
        if result.error:
            raise Refused(f"The database couldn't run it: {result.error}")
        table = result.table
        return {"columns": list(table.columns), "rows": table.to_dict("records"), "row_count": int(len(table)),
                "truncated": bool(result.truncated), "seconds": round(result.seconds, 3)}
    return _run("query_database", {"sql": sql, "max_rows": max_rows}, work)


# What the results describe. The server reads the library, or a dataset when
# STRAINSCOPE_DATASET names one (src/strainscope/paths.py, Phase 9).
DATA_KIND = "your own data" if sv.paths.info()["kind"] == "yours" else "simulated"


def get_signature() -> dict:
    """Phase 3's multi-omics signature: the genes and compounds DIABLO picked
    as telling one shared story about disease suppression, with their loading
    and stability (share of re-fits that picked them), and the report card
    that grades the signature against the planted truth of the simulated data."""
    def work():
        sig = sv.read_artifact("integration/diablo_signature.csv")
        card = sv.read_artifact("integration/signature_report_card.csv")
        if sig is None:
            raise Refused("The signature isn't there yet. Build it with Phase 3: docs/04-integration.md")
        sig = sig.sort_values(["component", "block", "stability", "loading"], ascending=[True, True, False, False])
        return {"signature": sig.to_dict("records"),
                "report_card": card.to_dict("records") if card is not None else [],
                "how_to_read": "stability 1 means picked in every re-fit; the robust signature keeps features "
                               "picked in at least 80 % of re-fits. The data is simulated, so the planted truth "
                               "is known and the report card can grade the picks."}
    return _run("get_signature", {}, work)


def rank_strain(strain_id: str) -> dict:
    """One library strain's place in the ranking: rank (1 is best), the
    model's calibrated chance of being effective, its band (likely above 70 %,
    borderline 30 to 70 %, unlikely below 30 %), and what the simulated trial
    measured. strain_id looks like STRAIN_0485."""
    def work():
        sid, row, total = _strain(strain_id)
        p = float(row["probability"])
        return {"strain_id": sid, "rank": int(row["rank"]), "of": total, "kingdom": row["kingdom"],
                "probability": round(p, 4), "band": sv.confidence_band(p),
                "trial": {"suppression_score": row["suppression_score"], "is_effective": bool(row["is_effective"])},
                "data": DATA_KIND}
    return _run("rank_strain", {"strain_id": strain_id}, work)


def explain_strain(strain_id: str) -> dict:
    """Why a library strain ranks where it does: a short explanation in plain
    words (written by rules, every number from the results) and its reasons as
    routes through the knowledge graph, each with its sources. strain_id looks
    like STRAIN_0485."""
    def work():
        sid, row, total = _strain(strain_id)
        words = sv.explain_in_words(sid)
        reasons = sv.read_artifact("graph/explanations.csv")
        mine = reasons[reasons["strain_id"] == sid].sort_values("order") if reasons is not None else None
        routes = [] if mine is None else [
            {"kind": r["kind"], "text": r["text"], "route": r["path"], "sources": r["provenance"]}
            for _, r in mine.iterrows()]
        return {"strain_id": sid, "rank": int(row["rank"]), "of": total, "in_plain_words": words["text"],
                "reasons": routes, "data": DATA_KIND}
    return _run("explain_strain", {"strain_id": strain_id}, work)


def shortlist(n: int = 50) -> dict:
    """What testing the n best-ranked strains would bring (n from 1 to 600):
    the strains, how many the model expects to be effective (its calibrated
    chances added up), and how many were effective in the simulated trial."""
    def work():
        from strainscope import narrate
        pred = sv.read_artifact("model/predictions.csv")
        if pred is None:
            raise Refused("The ranking isn't there yet. Build it with: python src/strainscope/model.py all")
        k = _whole(n, "n", 1, len(pred))
        top = pred.nsmallest(k, "rank")
        return {"n": k, "expected_effective": round(float(top["probability"].sum()), 1),
                "effective_in_trial": int(top["is_effective"].sum()),
                "in_plain_words": narrate.shortlist(pred, k, place=sv.paths.info()).text,
                "strains": top[["rank", "strain_id", "kingdom", "probability"]].head(MAX_ROWS).to_dict("records"),
                "data": DATA_KIND}
    return _run("shortlist", {"n": n}, work)


TOOLS = [ask_docs, ask_data, ask_graph, describe_database, query_database, get_signature,
         rank_strain, explain_strain, shortlist]


# =============================================================================
# 3. The server
# =============================================================================

def need_mcp() -> None:
    """Stop with a sentence (not a traceback) when the mcp package is missing."""
    import importlib.util
    if importlib.util.find_spec("mcp") is None:
        sys.exit("The mcp package isn't installed in this environment. With (.venv) active, run:\n"
                 "    python -m pip install -r requirements.txt")


def version() -> str:
    info = sv.release_info()
    return info["version"] + ("+unreleased" if info.get("unreleased") else "")


def build_server(quiet: bool = False):
    """The MCP server with every tool registered, each marked read-only. A
    refusal reaches the assistant as a tool error with its sentence (the
    SDK's ToolError), so the assistant can tell you why and try again."""
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.types import ToolAnnotations

    def as_mcp_tool(tool):
        @functools.wraps(tool)              # keeps the name, the docstring and the inputs the SDK reads
        def door(*args, **kwargs):
            try:
                return tool(*args, **kwargs)
            except Refused as why:
                raise ToolError(str(why)) from None
        return door

    server = MCPServer(SERVER_NAME, version=version(), instructions=INSTRUCTIONS,
                       website_url="https://github.com/akannan2987/strainscope",
                       log_level="ERROR" if quiet else "WARNING")
    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    for tool in TOOLS:
        server.tool(annotations=read_only)(as_mcp_tool(tool))
    return server


def serve() -> None:
    """Run the server on stdio until the app that started it closes it. The
    note goes to stderr: stdout belongs to the protocol. `check` starts the
    server with STRAINSCOPE_MCP_QUIET=1, which keeps its stderr quiet."""
    need_mcp()
    quiet = os.environ.get("STRAINSCOPE_MCP_QUIET") == "1"
    if not quiet:
        print(f"StrainScope MCP server {version()}: {len(TOOLS)} read-only tools on stdio. An assistant app "
              "normally starts this for you; press Ctrl+C to stop.", file=sys.stderr)
    build_server(quiet).run(transport="stdio")


# =============================================================================
# 4. The command line: list, call, check, config
# =============================================================================

def describe(tool) -> tuple[str, str]:
    """A tool's inputs as text ('strain_id: str', 'n: int = 50') and its first sentence."""
    parts = []
    for p in inspect.signature(tool).parameters.values():
        kind = p.annotation if isinstance(p.annotation, str) else getattr(p.annotation, "__name__", "")
        parts.append(f"{p.name}: {kind}" + (f" = {p.default}" if p.default is not inspect.Parameter.empty else ""))
    first = " ".join(inspect.getdoc(tool).split()).split(". ")[0].rstrip(".") + "."
    return ", ".join(parts), first


def print_tools() -> None:
    print(f"  ── StrainScope MCP server {version()}: {len(TOOLS)} tools, all read-only ──")
    for tool in TOOLS:
        args, first = describe(tool)
        print(f"\n  {tool.__name__}({args})")
        for line in _wrap(first, 88):
            print(f"      {line}")


def _wrap(text: str, width: int) -> list[str]:
    import textwrap
    return textwrap.wrap(text, width, break_on_hyphens=False) or [""]


def call(name: str, pairs: list[str]) -> int:
    """Run one tool from the terminal: `call rank_strain strain_id=STRAIN_0485`."""
    tools = {t.__name__: t for t in TOOLS}
    if name not in tools:
        print(f"  No tool called {name!r}. The tools are: {', '.join(tools)}.", file=sys.stderr)
        return 2
    kwargs = {}
    params = inspect.signature(tools[name]).parameters
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or key not in params:
            print(f"  {pair!r} isn't one of {name}'s inputs ({', '.join(params) or 'none'}), written as name=value.",
                  file=sys.stderr)
            return 2
        kwargs[key] = value
    try:
        result = tools[name](**kwargs)
    except Refused as why:
        print(f"  Refused: {why}")
        return 1
    except TypeError as err:
        print(f"  {err}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def check() -> int:
    """Start this server as a separate program, the way an assistant app
    does, and talk to it over stdio: list the tools, rank one strain, and
    send a query that must be refused."""
    need_mcp()
    import anyio
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async def run() -> int:
        params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).resolve())],
                                       env={"STRAINSCOPE_MCP_QUIET": "1", "STRAINSCOPE_MCP_LOG": str(LOG_PATH)})
        async with Client(params, mode="legacy") as client:         # the handshake most apps use today
            info = client.server_info
            print(f"  ✓ connected to {info.name} {info.version} (protocol {client.protocol_version})")
            tools = (await client.list_tools()).tools
            names = [t.name for t in tools]
            read_only = all(t.annotations and t.annotations.read_only_hint for t in tools)
            print(f"  ✓ {len(tools)} tools, all marked read-only: {', '.join(names)}" if read_only
                  else f"  ✗ {len(tools)} tools, not all marked read-only")
            ok = await client.call_tool("rank_strain", {"strain_id": "STRAIN_0485"})
            ranked = json.loads(ok.content[0].text) if not ok.is_error else {}
            print(f"  ✓ rank_strain STRAIN_0485: rank {ranked.get('rank')} of {ranked.get('of')}, "
                  f"band {ranked.get('band')}" if ranked else "  ✗ rank_strain failed")
            bad = await client.call_tool("query_database", {"sql": "DELETE FROM phenotype"})
            why = bad.content[0].text if bad.content else ""
            print(f"  ✓ query_database refused DELETE FROM phenotype:\n      {why}" if bad.is_error
                  else "  ✗ query_database ran a DELETE")
            passed = read_only and bool(ranked) and bad.is_error and len(tools) == len(TOOLS)
            where = LOG_PATH.relative_to(sv.ROOT).as_posix() if LOG_PATH.is_relative_to(sv.ROOT) else LOG_PATH
            print(f"\n  {'MCP check passed.' if passed else 'MCP check FAILED (see the lines above).'} "
                  f"Calls are logged in {where}.")
            return 0 if passed else 1

    print("  ── StrainScope: talking to the MCP server the way an assistant app does ──")
    return anyio.run(run)


def config() -> None:
    """The settings an assistant app needs, with this computer's paths."""
    python, script = str(Path(sys.executable)), str(Path(__file__).resolve())
    block = {"mcpServers": {SERVER_NAME: {"command": python, "args": [script]}}}
    print("  ── Connect an assistant app to StrainScope (docs/08b-mcp-server.md, section 9) ──\n")
    print("  Claude Desktop and most other apps: add this to the app's MCP settings file")
    print("  (inside an existing \"mcpServers\" block, add only the \"strainscope\" part):\n")
    for line in json.dumps(block, indent=2).splitlines():
        print(f"  {line}")
    print("\n  For Claude Desktop, this command can add it for you (it keeps a backup of the file):\n")
    print("  python src/strainscope/mcp_server.py config --write")
    quote = (lambda s: f'"{s}"') if " " in python + script else (lambda s: s)
    print("\n  Claude Code: run this once in a terminal:\n")
    print(f"  claude mcp add --transport stdio --scope user {SERVER_NAME} -- {quote(python)} {quote(script)}")


def desktop_settings_file() -> Path:
    """Where Claude Desktop keeps its settings file for this user (docs/08b-mcp-server.md
    section 9). On Linux this is a guess (~/.config/Claude); --file overrides it."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")) / "Claude" / "claude_desktop_config.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "Claude" / "claude_desktop_config.json"


def store_copies() -> list[Path]:
    """Windows: the second settings file some versions of Claude Desktop read
    (the copy installed as an MSIX package, section 9 of the guide)."""
    base = os.environ.get("LOCALAPPDATA")
    if sys.platform != "win32" or not base:
        return []
    return sorted(Path(base, "Packages").glob("Claude_*/LocalCache/Roaming/Claude/claude_desktop_config.json"))


def edit_desktop_settings(action: str, path: Path | None = None) -> int:
    """config --write / --remove: add or remove the strainscope entry in Claude
    Desktop's settings file, keeping every other setting as it is. A dated
    backup is saved next to the file first, and a file that isn't valid JSON is
    left untouched. Returns 0 when the file is as asked, 1 when nothing could
    be done."""
    path = Path(path) if path else desktop_settings_file()
    entry = {"command": str(Path(sys.executable)), "args": [str(Path(__file__).resolve())]}
    verb = {"write": "add", "remove": "remove"}[action]
    print(f"  ── Claude Desktop's settings file: {verb} the strainscope entry ──")
    print(f"  {path}")
    if not path.parent.is_dir():
        print(f"\n  The folder {path.parent} doesn't exist, so Claude Desktop seems not to be installed for this")
        print("  user (or keeps its settings elsewhere). Install it and open it once, then run this again,")
        print("  or give the file's place with --file. Nothing was changed.")
        return 1
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    try:
        settings = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError as err:
        print(f"\n  The file isn't valid JSON (line {err.lineno}, column {err.colno}: {err.msg}).")
        print("  Nothing was changed. Fix that line (often a missing comma or quote) and run this again.")
        return 1
    servers = settings.get("mcpServers", {}) if isinstance(settings, dict) else None
    if not isinstance(servers, dict):
        print("\n  The file doesn't have the expected shape (an object with an \"mcpServers\" object inside).")
        print("  Nothing was changed. Add the entry by hand, as section 9 of docs/08b-mcp-server.md shows.")
        return 1
    if action == "write" and servers.get(SERVER_NAME) == entry:
        print("\n  The strainscope entry is already there, with these paths. Nothing to change.")
        return 0
    if action == "remove" and SERVER_NAME not in servers:
        print("\n  There's no strainscope entry in the file. Nothing to remove.")
        return 0
    if path.exists():
        backup = path.with_name(f"{path.stem}.backup-{dt.datetime.now():%Y%m%d-%H%M%S}{path.suffix}")
        backup.write_text(text, encoding="utf-8")
        print(f"\n  backup → {backup.name} (next to it)")
    if action == "write":
        settings.setdefault("mcpServers", servers)[SERVER_NAME] = entry
    else:
        del servers[SERVER_NAME]
        if not servers:
            settings.pop("mcpServers")
    kept = sorted(k for k in settings if k != "mcpServers")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)                 # all at once: never a half-written settings file
    did = "added" if action == "write" else "removed"
    print(f"  ✓ strainscope entry {did}" + (f"; other settings kept: {', '.join(kept)}" if kept else ""))
    others = [p for p in store_copies() if p != path]
    if others:
        print("\n  This computer also has the Store version's settings file, which some versions read:")
        for p in others:
            print(f"    {p}")
        print(f"  If strainscope doesn't {'appear' if action == 'write' else 'go away'}, run this again "
              "with --file and that path.")
    print("\n  Quit Claude Desktop completely and start it again: it reads the file only when it starts.")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="StrainScope's MCP server: read-only tools for AI assistant apps. "
                                                 "Without a command it runs the server on stdio.")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the server on stdio (the default)")
    sub.add_parser("tools", help="list the tools and their inputs")
    c = sub.add_parser("call", help="run one tool here: call rank_strain strain_id=STRAIN_0485")
    c.add_argument("tool")
    c.add_argument("inputs", nargs="*", help="name=value pairs")
    sub.add_parser("check", help="start the server as an app would and test it over stdio")
    g = sub.add_parser("config", help="print the settings for an assistant app, with this computer's paths")
    act = g.add_mutually_exclusive_group()
    act.add_argument("--write", action="store_true",
                     help="add the strainscope entry to Claude Desktop's settings file (with a backup)")
    act.add_argument("--remove", action="store_true",
                     help="remove the strainscope entry from Claude Desktop's settings file (with a backup)")
    g.add_argument("--file", type=Path, default=None,
                   help="the settings file to change, if it isn't in Claude Desktop's usual place")
    args = parser.parse_args(argv)
    if args.command == "tools":
        print_tools()
        return 0
    if args.command == "call":
        return call(args.tool, args.inputs)
    if args.command == "check":
        return check()
    if args.command == "config":
        if args.write or args.remove:
            return edit_desktop_settings("write" if args.write else "remove", args.file)
        if args.file:
            parser.error("--file goes with --write or --remove")
        config()
        return 0
    serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
