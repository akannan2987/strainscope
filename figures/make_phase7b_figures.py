"""
figures/make_phase7b_figures.py: the teaching figures for Phase 7b (the MCP server).
===================================================================================
  CONCEPTS (drawn; tool names are read from src/strainscope/mcp_server.py):
    figures/mcp_socket.png          MCP as one socket for many assistant apps: the app starts the
                                    server, they talk through stdin and stdout, the tools read
                                    StrainScope's results through the service layer
    figures/three_doors.png         one service layer, three doors: the terminal, the app and the
                                    MCP server give the same answers
    figures/mcp_tools.png           the nine read-only tools: what each reads and what it checks

  RESULTS (computed by calling the tools, never invented):
    figures/mcp_conversation.png    one question answered with two tool calls: what each call
                                    returned, and the two lines the call log kept
    docs/interactive/mcp_explorer.html
                                    every tool with its description, the input schema an app sees,
                                    a real example call and its result

Run (from the project root, venv active, database built, mcp installed):
    python figures/make_phase7b_figures.py

The drawing helpers are shared with figures/make_phase6_figures.py. The
example calls write their log lines to a temporary file, not to
data/processed/mcp_calls.log.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "figures"))

from make_phase6_figures import (BLUE, DARK_GREEN, GOLD, INK, PURPLE, RED, SOFT, TEAL,  # noqa: E402
                                 arrow, box, canvas, save, tint)
from strainscope import mcp_server as M  # noqa: E402
from strainscope import service as sv  # noqa: E402

INT = ROOT / "docs" / "interactive"
M.LOG_PATH = Path(tempfile.gettempdir()) / "strainscope_figures_mcp_calls.log"   # keep the real log clean


# =============================================================================
# 1. One socket, many assistant apps
# =============================================================================

def draw_socket():
    fig, ax = canvas(11.5, 6.2, "MCP: one socket, many assistant apps",
                     "The app starts StrainScope's server and talks to it through the server's input and "
                     "output. No network port is opened.")
    ax.text(1.95, 10.15, "assistant apps\n(MCP clients)", ha="center", fontsize=9, fontweight="bold", color=INK,
            linespacing=1.3)
    for i, name in enumerate(["Claude Desktop", "Claude Code", "another app\nthat speaks MCP"]):
        box(ax, 0.3, 7.9 - i * 2.25, 3.3, 1.6, BLUE, name, fs=8.8)
        arrow(ax, 3.65, 8.7 - i * 2.25, 4.75, 6.95, colour=BLUE)
    box(ax, 4.8, 5.5, 4.45, 2.9, GOLD, "MCP over stdio\n\nrequests in through stdin,\nanswers out through\nstdout, "
        "notes on stderr", fs=8.0)
    arrow(ax, 9.3, 6.95, 9.75, 6.95, colour=GOLD, text="")
    box(ax, 9.8, 1.4, 4.9, 9.4, PURPLE, "", fill=tint(PURPLE, 0.9))
    ax.text(12.25, 10.15, "StrainScope MCP server", ha="center", fontsize=9.6, fontweight="bold", color=INK)
    ax.text(12.25, 9.6, "src/strainscope/mcp_server.py", ha="center", fontsize=7.8, color=SOFT, family="monospace")
    for i, tool in enumerate(M.TOOLS):
        box(ax, 10.2, 8.55 - i * 0.8, 4.1, 0.62, PURPLE, tool.__name__ + "()", fs=8.0, fill="white")
    arrow(ax, 14.75, 6.95, 15.75, 6.95, colour=PURPLE, text="")
    box(ax, 15.8, 5.85, 3.2, 2.2, TEAL, "service layer\nsrc/strainscope/\nservice.py", fs=8.3)
    arrow(ax, 19.05, 6.95, 19.75, 6.95, colour=TEAL)
    box(ax, 19.8, 7.35, 2.95, 2.1, DARK_GREEN, "database\ndata/processed/\nstrainscope.duckdb", fs=7.8)
    box(ax, 19.8, 4.4, 2.95, 2.1, DARK_GREEN, "committed\nresults\nartifacts/", fs=7.8)
    ax.text(16.0, 3.9, "every tool is read-only:\nno writes, no files,\nSQL behind five guards", fontsize=8.1,
            color=SOFT, linespacing=1.35, va="top")
    ax.text(0.3, 0.45, "What a tool returns goes to the app, and from there to the model the app uses. Every call "
            "is logged in data/processed/mcp_calls.log (never the results).", fontsize=8.3, color=SOFT)
    save(fig, "mcp_socket.png")


# =============================================================================
# 2. One service layer, three doors
# =============================================================================

def draw_three_doors():
    fig, ax = canvas(11.5, 5.4, "One service layer, three doors",
                     "The terminal, the app and the MCP server call the same functions, so they give the same "
                     "answers.")
    doors = [("the terminal", "you, typing commands", "python src/strainscope/\nservice.py, ask.py, ...", BLUE),
             ("the app", "anyone with a browser", "11 pages, at home\nor online", GOLD),
             ("the MCP server", "an AI assistant app", f"{len(M.TOOLS)} read-only tools\n(Phase 7b)", PURPLE)]
    for i, (name, who, what, colour) in enumerate(doors):
        x = 0.6 + i * 7.6
        box(ax, x, 6.0, 6.4, 2.9, colour, "", fill=tint(colour, 0.85))
        ax.text(x + 3.2, 8.2, name, ha="center", fontsize=10.5, fontweight="bold", color=INK)
        ax.text(x + 3.2, 7.55, who, ha="center", fontsize=8.6, color=SOFT, style="italic")
        ax.text(x + 3.2, 6.65, what, ha="center", va="center", fontsize=8.3, color=INK, linespacing=1.3)
        arrow(ax, x + 3.2, 5.95, 11.5, 4.65, colour=colour)
    box(ax, 5.3, 3.0, 12.4, 1.6, TEAL, "the service layer: src/strainscope/service.py\nask_docs  ask_data  ask_graph  "
        "query_database  explain_in_words  ...", fs=8.5)
    arrow(ax, 11.5, 2.95, 11.5, 2.05, colour=TEAL)
    box(ax, 5.3, 0.45, 12.4, 1.55, DARK_GREEN, "the results of Phases 1 to 7: the database, artifacts/, the documents",
        fs=8.5)
    save(fig, "three_doors.png")


# =============================================================================
# 3. The nine tools
# =============================================================================

READS = {
    "ask_docs": ("the documents: guides, Handbook,\nglossary, docstrings", "question: 1 to 300 characters"),
    "ask_data": ("the Query Cookbook's tested recipes,\nrun read-only", "question: 1 to 300 characters"),
    "ask_graph": ("the knowledge graph (Phase 5)", "question: 1 to 300 characters"),
    "describe_database": ("table and column names, row counts", "no input"),
    "query_database": ("any table, read-only", "one SELECT or WITH; 1 to 200 rows"),
    "get_signature": ("artifacts/integration/ (Phase 3)", "no input"),
    "rank_strain": ("artifacts/model/predictions.csv", "STRAIN_ and 4 digits; must exist"),
    "explain_strain": ("the ranking and artifacts/graph/\nexplanations.csv", "STRAIN_ and 4 digits; must exist"),
    "shortlist": ("artifacts/model/predictions.csv", "n: a whole number, 1 to 600"),
}


def draw_tools():
    fig, ax = canvas(11.5, 7.4, "Nine read-only tools, what each reads, and what it checks",
                     "Every tool is marked read-only for the app. A refused call comes back as one sentence "
                     "saying why.")
    heads = [("tool", 0.4), ("what it reads", 6.4), ("what it checks first", 14.2)]
    for text, x in heads:
        ax.text(x, 12.55, text, fontsize=9.2, fontweight="bold", color=INK)
    colours = {"ask_docs": BLUE, "ask_data": GOLD, "ask_graph": PURPLE, "describe_database": TEAL,
               "query_database": RED, "get_signature": DARK_GREEN, "rank_strain": DARK_GREEN,
               "explain_strain": DARK_GREEN, "shortlist": DARK_GREEN}
    for i, tool in enumerate(M.TOOLS):
        name = tool.__name__
        y = 11.35 - i * 1.22
        args, _ = M.describe(tool)
        box(ax, 0.4, y, 5.6, 1.0, colours[name], f"{name}({args.split(':')[0] if args else ''})", fs=8.3)
        reads, checks = READS[name]
        ax.text(6.4, y + 0.5, reads, fontsize=8.1, color=INK, va="center", linespacing=1.2)
        ax.text(14.2, y + 0.5, checks, fontsize=8.1, color=INK, va="center")
        ax.text(21.2, y + 0.5, "read-only", fontsize=7.6, color=DARK_GREEN, va="center", fontweight="bold")
    ax.text(0.4, 0.3, "Every call is logged (tool, arguments, outcome, time taken) in data/processed/mcp_calls.log; "
            "the results are not.", fontsize=8.3, color=SOFT)
    save(fig, "mcp_tools.png")


# =============================================================================
# 4. One question, two tool calls (computed)
# =============================================================================

def draw_conversation():
    rank = M.rank_strain("STRAIN_0485")
    why = M.explain_strain("STRAIN_0485")
    lines = [json.loads(line) for line in M.LOG_PATH.read_text(encoding="utf-8").splitlines()[-2:]]
    mech = [r for r in why["reasons"] if r["kind"] == "mechanism"]
    fig, ax = canvas(11.5, 7.0, "One question, two tool calls",
                     "What an assistant app does with \"Why does STRAIN_0485 rank first, and how sure is the "
                     "model?\" (results computed by calling the tools).")
    box(ax, 0.4, 10.3, 6.6, 2.0, BLUE, "you ask, in the app:\nWhy does STRAIN_0485 rank first,\nand how sure is "
        "the model?", fs=8.5)
    arrow(ax, 7.05, 11.3, 8.0, 11.3, colour=BLUE)
    box(ax, 8.05, 10.3, 6.2, 2.0, GOLD, "the app's model picks tools:\nrank_strain, then explain_strain",
        fs=8.5)
    arrow(ax, 11.15, 10.25, 6.5, 9.2, colour=GOLD)
    arrow(ax, 11.15, 10.25, 16.2, 9.2, colour=GOLD)
    box(ax, 0.4, 4.5, 11.4, 4.6, PURPLE, "", fill=tint(PURPLE, 0.9))
    ax.text(0.8, 8.5, 'rank_strain(strain_id="STRAIN_0485")', fontsize=8.6, fontweight="bold", color=INK,
            family="monospace")
    for k, line in enumerate([f"rank {rank['rank']} of {rank['of']}, {rank['kingdom']}",
                              f"probability {rank['probability']}  (band: {rank['band']})",
                              f"simulated trial: {rank['trial']['suppression_score']:.0f} % suppressed, "
                              f"effective: {'yes' if rank['trial']['is_effective'] else 'no'}",
                              f"data: {rank['data']}"]):
        ax.text(0.9, 7.6 - k * 0.72, line, fontsize=8.3, color=INK)
    box(ax, 12.2, 4.5, 10.4, 4.6, PURPLE, "", fill=tint(PURPLE, 0.9))
    ax.text(12.6, 8.5, 'explain_strain(strain_id="STRAIN_0485")', fontsize=8.6, fontweight="bold", color=INK,
            family="monospace")
    import textwrap
    shown = [f"{len(why['reasons'])} reasons shown, {len(mech)} of them mechanisms; the first:"]
    if mech:
        steps = mech[0]["route"].split(" > ")
        shown += ["  " + " > ".join(steps[:3]) + " >", "  " + " > ".join(steps[3:])]
    shown += [""] + textwrap.wrap("in plain words: \"" + why["in_plain_words"].split(". ")[0] + ".\"", 52)
    ax.text(12.7, 7.65, "\n".join(shown), fontsize=8.0, color=INK, va="top", linespacing=1.35)
    arrow(ax, 6.1, 4.45, 9.5, 3.55, colour=PURPLE)
    arrow(ax, 17.4, 4.45, 13.5, 3.55, colour=PURPLE)
    box(ax, 5.4, 2.0, 12.2, 1.5, DARK_GREEN, "the app writes the reply from these results:\nthe wording is the "
        "app's, the numbers and routes come from the tools", fs=8.4)
    log = "   ".join(f"{e['tool']}: {e['outcome']}" for e in lines)
    ax.text(0.4, 0.75, f"The call log kept two lines (tool, arguments, outcome, time; no results):   {log}",
            fontsize=8.0, color=SOFT)
    save(fig, "mcp_conversation.png")


# =============================================================================
# 5. The interactive tool explorer (computed)
# =============================================================================

EXAMPLES = [
    ("ask_docs", {"question": "How do I start the app?"}),
    ("ask_data", {"question": "How many strains are there in each kingdom?"}),
    ("ask_graph", {"question": "How does iturin suppress disease?"}),
    ("describe_database", {}),
    ("query_database", {"sql": "SELECT kingdom, COUNT(*) AS strains FROM phenotype GROUP BY kingdom "
                               "ORDER BY strains DESC"}),
    ("get_signature", {}),
    ("rank_strain", {"strain_id": "STRAIN_0485"}),
    ("explain_strain", {"strain_id": "STRAIN_0485"}),
    ("shortlist", {"n": 5}),
]
REFUSED = [("query_database", {"sql": "DELETE FROM phenotype"}), ("rank_strain", {"strain_id": "STRAIN_0601"})]


def shorten(value, rows: int = 6):
    """Long lists cut to their first few items, so the page stays readable."""
    if isinstance(value, dict):          # timings change on every run; show what they are instead
        return {k: ("(time taken)" if k == "seconds" else shorten(v, rows)) for k, v in value.items()}
    if isinstance(value, list) and len(value) > rows:
        return [shorten(v, rows) for v in value[:rows]] + [f"... and {len(value) - rows} more"]
    if isinstance(value, list):
        return [shorten(v, rows) for v in value]
    return value


def schemas() -> dict:
    """The input schema of every tool, as an app receives it from the server."""
    import anyio
    from mcp import Client

    async def run():
        async with Client(M.build_server()) as client:
            return {t.name: t.input_schema for t in (await client.list_tools()).tools}
    return anyio.run(run)


def write_explorer():
    import inspect
    schema = schemas()
    tools = {t.__name__: t for t in M.TOOLS}
    entries = []
    for name, args in EXAMPLES:
        result = tools[name](**args)
        entries.append({"name": name, "doc": " ".join(inspect.getdoc(tools[name]).split()),
                        "schema": schema[name], "args": args, "result": shorten(result)})
    refused = []
    for name, args in REFUSED:
        try:
            tools[name](**args)
        except M.Refused as why:
            refused.append({"name": name, "args": args, "why": str(why)})
    log = [dict(json.loads(line), time="(the time of the call, UTC)", seconds="(time taken)")
           for line in M.LOG_PATH.read_text(encoding="utf-8").splitlines()[-3:]]
    data = json.dumps({"tools": entries, "refused": refused, "log": log}, ensure_ascii=False)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>StrainScope: the MCP tools</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1F2933;background:#FFFFFF}}
h1{{font-size:22px}} h2{{font-size:16px;margin:18px 0 6px}} p{{color:#5f6b7a;line-height:1.5}}
.wrap{{display:flex;gap:18px;flex-wrap:wrap}} .list{{flex:0 0 220px}} .detail{{flex:1 1 560px;min-width:0}}
button{{display:block;width:100%;text-align:left;margin:0 0 6px;padding:8px 10px;border:1px solid #DCE6F5;border-radius:8px;
background:#F5F9FF;font:14px ui-monospace,SFMono-Regular,Menlo,monospace;cursor:pointer;color:#1F2933}}
button.on{{background:#E8DDF8;border-color:#9C6ADE}}
pre{{background:#F7F7F9;border:1px solid #E3E6EA;border-radius:8px;padding:10px;overflow:auto;font-size:12.5px;max-height:420px;white-space:pre-wrap;word-break:break-word}}
.tag{{display:inline-block;background:#E6F4EA;color:#2E7D5B;border-radius:6px;padding:2px 8px;font-size:12px;font-weight:600}}
.refused{{border-left:4px solid #D9634C;padding-left:10px;margin:8px 0}}
</style></head><body>
<h1>StrainScope: the MCP tools</h1>
<p>The nine tools of the MCP server (<code>src/strainscope/mcp_server.py</code>). Pick a tool to see what it does, the input
schema an assistant app receives, and a real example call with its result (long lists are cut to their first six items).
Every tool is read-only. The guide is <code>docs/08b-mcp-server.md</code>. The data is simulated.</p>
<div class="wrap"><div class="list" id="list"></div><div class="detail" id="detail"></div></div>
<h2>Two refused calls</h2><div id="refused"></div>
<h2>What the call log keeps</h2>
<p>One line per call in <code>data/processed/mcp_calls.log</code>: the tool, its arguments, the outcome and the time taken.
Never the results. The last three lines written while this page was made:</p><pre id="log"></pre>
<script>
const DATA = {data};
const esc = s => String(s).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}})[c]);
function show(i) {{
  const t = DATA.tools[i];
  document.querySelectorAll('#list button').forEach((b, k) => b.className = k === i ? 'on' : '');
  const call = t.name + '(' + Object.entries(t.args).map(([k, v]) => k + '=' + JSON.stringify(v)).join(', ') + ')';
  document.getElementById('detail').innerHTML =
    '<h2>' + esc(t.name) + ' <span class="tag">read-only</span></h2><p>' + esc(t.doc) + '</p>' +
    '<h2>The input schema an app receives</h2><pre>' + esc(JSON.stringify(t.schema, null, 2)) + '</pre>' +
    '<h2>Example call</h2><pre>' + esc(call) + '</pre>' +
    '<h2>Its result</h2><pre>' + esc(JSON.stringify(t.result, null, 2)) + '</pre>';
}}
DATA.tools.forEach((t, i) => {{
  const b = document.createElement('button'); b.textContent = t.name; b.onclick = () => show(i);
  document.getElementById('list').appendChild(b);
}});
document.getElementById('refused').innerHTML = DATA.refused.map(r =>
  '<div class="refused"><code>' + esc(r.name) + '(' + esc(JSON.stringify(r.args)) + ')</code><br>' + esc(r.why) + '</div>').join('');
document.getElementById('log').textContent = DATA.log.map(e => JSON.stringify(e)).join('\\n');
show(0);
</script></body></html>
"""
    (INT / "mcp_explorer.html").write_text(page, encoding="utf-8")
    print(f"  drew docs/interactive/mcp_explorer.html (interactive, {len(entries)} tools)")


if __name__ == "__main__":
    if not sv.DB_PATH.exists():
        sys.exit("Build the database first (python src/strainscope/harmonize.py and the three publish steps).")
    M.need_mcp()
    M.LOG_PATH.unlink(missing_ok=True)
    print("Phase 7b figures:")
    draw_socket()
    draw_three_doors()
    draw_tools()
    draw_conversation()
    write_explorer()
