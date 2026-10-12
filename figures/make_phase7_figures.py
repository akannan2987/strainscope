"""
figures/make_phase7_figures.py: the teaching figures for Phase 7 (deployment and the AI layer).
==============================================================================================
  CONCEPTS (drawn; names and numbers in them are read from the code and the results):
    figures/deployment_map.png       from your laptop to a link anyone can open: GitHub, Streamlit
                                     Community Cloud, the secrets box, the first start
    figures/three_assistants.png     one shape, three assistants: what each finds, what the gate
                                     refuses, what a model may add, and what a model sees
    figures/five_guards.png          Ask the data: a tested recipe first; a model's query only behind
                                     five guards; the model never sees a row
    figures/graphrag_walk.png        one question answered by walking the graph: the route and the
                                     numbered facts with their sources (computed)
    figures/plain_words.png          how a strain's rank becomes a paragraph: results in, rules,
                                     sentences out, every number traceable (computed)

  RESULTS (computed from the golden questions, never invented):
    figures/assistant_golden_scores.png
                                     every golden question of Ask the data and Ask the graph, where
                                     it scored, and what the assistant did
    docs/interactive/assistants_explorer.html
                                     the same, interactive, plus the recipe scores for any question

Run (from the project root, venv active, database built):
    python figures/make_phase7_figures.py

The drawing helpers are shared with figures/make_phase6_figures.py.
"""
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "figures"))

from make_phase6_figures import (BLUE, DARK_GREEN, GOLD, GREY, INK, PURPLE, RED, SOFT, TEAL,  # noqa: E402
                                 arrow, box, canvas, plt, save, tint)
from strainscope import ask_data as D  # noqa: E402
from strainscope import ask_graph as Q  # noqa: E402
from strainscope import narrate  # noqa: E402
from strainscope import service as sv  # noqa: E402

INT = ROOT / "docs" / "interactive"
DATA_COLOUR = {D.RECIPE: DARK_GREEN, D.WRITTEN: TEAL, D.CLOSEST: GOLD, D.REFUSED: RED, D.VAGUE: GREY}
GRAPH_COLOUR = {Q.ANSWERED: DARK_GREEN, Q.CLOSEST: GOLD, Q.REFUSED: RED, Q.VAGUE: GREY}


# =============================================================================
# 1. From your laptop to a link
# =============================================================================

def draw_deployment_map():
    fig, ax = canvas(11.5, 6.4, "From your laptop to a link anyone can open",
                     "The online copy is built from what you push. Nothing secret and no data travels "
                     "through GitHub.")
    # your computer
    box(ax, 0.3, 2.4, 5.6, 7.6, BLUE, "", fill=tint(BLUE, 0.92))
    ax.text(0.65, 9.45, "your computer", fontsize=10.5, fontweight="bold", color=BLUE)
    for i, (head, body) in enumerate([("develop branch", "code, docs, results"),
                                      ("pytest -q", "every test passes"),
                                      ("./check-public-safe.sh", "SAFE TO PUSH"),
                                      ("git push", "develop, beta and master")]):
        y = 7.6 - i * 1.55
        box(ax, 0.65, y, 4.9, 1.25, BLUE, "")
        ax.text(0.95, y + 0.85, head, fontsize=8.8, fontweight="bold", color=INK, family="monospace", va="center")
        ax.text(0.95, y + 0.38, body.replace("\n", " "), fontsize=7.8, color=SOFT, va="center")
    ax.text(0.65, 1.75, "stays here: data/, .env, .venv/", fontsize=8, color=RED, fontweight="bold")
    ax.text(0.65, 1.2, "(Git ignores them; the gate checks)", fontsize=7.6, color=SOFT)
    arrow(ax, 5.95, 6.2, 7.25, 6.2, colour=SOFT, lw=2, text="push")
    # GitHub
    box(ax, 7.3, 2.4, 4.8, 7.6, GREY, "", fill=tint(GREY, 0.9))
    ax.text(7.6, 9.45, "GitHub", fontsize=10.5, fontweight="bold", color=INK)
    ax.text(7.6, 8.85, "master branch", fontsize=8.5, color=SOFT, family="monospace")
    for i, line in enumerate(["app/  src/  docs/", "artifacts/ (results)", "app/requirements.txt",
                              "  exact versions for", "  the online copy", ".streamlit/config.toml"]):
        ax.text(7.6, 8.0 - i * 0.62, line, fontsize=8.2, color=INK, family="monospace")
    ax.text(7.6, 3.6, "optional: docs/ as a\nGitHub Pages site\n(the interactive figures)", fontsize=7.8,
            color=SOFT, linespacing=1.35)
    arrow(ax, 12.15, 6.2, 13.45, 6.2, colour=SOFT, lw=2, text="watches")
    # Community Cloud
    box(ax, 13.5, 1.0, 5.9, 9.0, DARK_GREEN, "", fill=tint(DARK_GREEN, 0.9))
    ax.text(13.8, 9.45, "Streamlit Community Cloud", fontsize=10.5, fontweight="bold", color=DARK_GREEN)
    steps = [("1", "installs app/requirements.txt"), ("2", "reads the Secrets box:\nSTRAINSCOPE_MODE = \"public\"\n"
             "(+ an optional model key)"), ("3", "runs app/streamlit_app.py"), ("4", "first start: builds the\n"
             "database (about 15 s)"), ("5", "redeploys on every push;\nsleeps after 12 h alone")]
    for (num, text), y in zip(steps, (8.75, 7.95, 6.25, 5.5, 4.15)):
        ax.add_patch(plt.Circle((14.1, y - 0.15), 0.27, color=DARK_GREEN, zorder=3))
        ax.text(14.1, y - 0.15, num, ha="center", va="center", color="white", fontsize=8.5, fontweight="bold", zorder=4)
        ax.text(14.55, y, text, fontsize=8.2, color=INK, va="top", linespacing=1.3)
    box(ax, 13.8, 1.3, 5.3, 1.5, GOLD, "secrets live here, never\nin Git: Settings > Secrets", fs=8.2)
    arrow(ax, 19.45, 6.2, 20.6, 6.2, colour=SOFT, lw=2)
    # visitor
    ax.add_patch(plt.Circle((21.8, 6.2), 1.05, facecolor=tint(TEAL, 0.8), edgecolor=TEAL, lw=1.8))
    ax.text(21.8, 6.2, "a visitor's\nbrowser", ha="center", va="center", fontsize=8.6, color=INK)
    ax.text(21.8, 4.65, "a link,\nnothing installed", ha="center", va="center", fontsize=8, color=SOFT)
    ax.text(0.3, 0.25, "Shared mode on the online copy: real-data buttons hidden, no rebuild once the database "
            "exists, uploads kept in the visitor's tab only, a daily cap on model requests.", fontsize=8.4,
            color=SOFT)
    save(fig, "deployment_map.png")


# =============================================================================
# 2. One shape, three assistants
# =============================================================================

def draw_three_assistants():
    fig, ax = canvas(11.5, 6.6, "One shape, three assistants",
                     "Each one finds material first and decides before showing anything. A language model is "
                     "optional, and it only rewrites what was found.")
    heads = ["", "finds (always; nothing\nleaves the computer)", "refuses before\nanything is shown",
             "a model, if switched on,\nmay add", "the model sees"]
    xs = [0.3, 4.3, 9.1, 13.9, 18.7]
    widths = [3.8, 4.6, 4.6, 4.6, 4.3]
    for x, w, h in zip(xs, widths, heads):
        ax.text(x + w / 2, 10.55, h, ha="center", va="center", fontsize=8.8, fontweight="bold", color=INK,
                linespacing=1.3)
    rows = [("Ask StrainScope", "about the project\n(Phase 6b)", BLUE,
             "the passages that answer,\nword for word, with links", "instructions;\nwords no document uses;\na weak match",
             "a short answer that\ncites the passages", "the question and\nup to 3 passages"),
            ("Ask the data", "about the data\n(Phase 7)", GOLD,
             "a tested recipe from the\nQuery Cookbook, run\nthrough four guards", "instructions;\nchanges to the database;\nunknown words",
             "a new query when no\nrecipe fits, behind\na fifth guard", "the question, table\nand column names,\n3 recipes: never a row"),
            ("Ask the graph", "how things connect\n(Phase 7, GraphRAG)", PURPLE,
             "walks through the graph:\nnumbered facts with\nsources, the route", "instructions;\nnothing from the\ngraph named",
             "a short answer that\ncites the facts and\nadds no numbers", "the question and the\nfacts (domain model,\npublic references):\nnever a strain")]
    for r, (name, sub, colour, finds, refuses, adds, sees) in enumerate(rows):
        y = 7.35 - r * 3.05
        box(ax, xs[0], y, widths[0], 2.55, colour, "", fill=tint(colour, 0.78))
        ax.text(xs[0] + widths[0] / 2, y + 1.65, name, ha="center", va="center", fontsize=10.2, fontweight="bold",
                color=INK)
        ax.text(xs[0] + widths[0] / 2, y + 0.8, sub, ha="center", va="center", fontsize=8, color=SOFT, linespacing=1.3)
        for x, w, text, c in zip(xs[1:], widths[1:], (finds, refuses, adds, sees),
                                 (DARK_GREEN, RED, TEAL, GREY)):
            box(ax, x, y, w, 2.55, c, text, fs=8.1, fill=tint(c, 0.92))
    ax.text(0.3, 0.3, "Plain-language explanations (Strain and Ranking pages) are written by rules from the results: "
            "no model, so nothing to invent and nothing sent.", fontsize=8.4, color=SOFT)
    save(fig, "three_assistants.png")


# =============================================================================
# 3. Ask the data: five guards
# =============================================================================

def draw_five_guards():
    fig, ax = canvas(11.5, 6.6, "Ask the data: a tested recipe first, then five guards",
                     "A model only ever writes the question in SQL. The guards check what it wrote, and it never "
                     "sees the answer.")
    box(ax, 0.3, 10.0, 4.2, 1.2, TEAL, "your question", fs=9.5, bold=True)
    arrow(ax, 2.4, 9.95, 2.4, 9.15, colour=SOFT)
    box(ax, 0.3, 7.5, 4.2, 1.6, RED, "the gate: instructions,\nchanges, unknown words\nare refused", fs=8.3)
    arrow(ax, 2.4, 7.45, 2.4, 6.65, colour=SOFT)
    box(ax, 0.3, 4.7, 4.2, 1.9, GOLD, f"does a Query Cookbook\nrecipe fit? (match >= {D.RECIPE_NEEDED},\n"
        f"{D.COVERAGE_NEEDED:.0%} of the words, every\ncolumn the question names)", fs=7.9)
    # yes: the recipe
    arrow(ax, 4.55, 5.65, 6.4, 5.65, colour=DARK_GREEN, text="yes")
    box(ax, 6.45, 4.7, 4.3, 1.9, DARK_GREEN, f"run the tested recipe\n({len(D.recipe_index().recipes)} in the "
        "cookbook)", fs=8.5)
    # no: a model?
    arrow(ax, 2.4, 4.65, 2.4, 4.05, colour=GOLD)
    ax.text(2.6, 4.25, "no", fontsize=8.5, color=GOLD, style="italic")
    box(ax, 0.3, 3.0, 4.2, 1.0, GREY, "is a language model on?", fs=8.4)
    arrow(ax, 2.4, 2.95, 2.4, 2.4, colour=GREY)
    ax.text(2.6, 2.55, "no", fontsize=8.5, color=GREY, style="italic")
    box(ax, 0.3, 1.0, 4.2, 1.35, GREY, "the closest recipes are\noffered; none is run", fs=8.2)
    arrow(ax, 4.55, 3.5, 6.4, 3.0, colour=PURPLE, text="yes")
    box(ax, 6.45, 1.5, 4.3, 2.5, PURPLE, "the model writes one\nquery from the table\nand column names and\n"
        "3 recipes; never a row", fs=8.2)
    arrow(ax, 10.8, 2.75, 12.0, 2.75, colour=PURPLE)
    box(ax, 12.05, 1.5, 3.7, 2.5, RED, "", fill=tint(RED, 0.88))
    ax.text(13.9, 3.55, "5  one read-only\n    statement", ha="center", va="center", fontsize=8.6, fontweight="bold",
            color=INK, linespacing=1.25)
    ax.text(13.9, 2.25, "SELECT or WITH only;\nno DROP, COPY, ATTACH,\nno read_csv()", ha="center", va="center",
            fontsize=7.6, color=SOFT, linespacing=1.3)
    # guards 1 to 4
    rings = [("1  read-only", BLUE), ("2  no file access", PURPLE), (f"3  {sv.SQL_TIMEOUT_S}-second limit", GOLD),
             (f"4  {sv.SQL_MAX_ROWS:,}-row cap", RED)]
    box(ax, 16.4, 1.5, 3.4, 9.7, BLUE, "", fill=tint(BLUE, 0.94))
    ax.text(18.1, 10.65, "the SQL console's\nfour guards", ha="center", va="center", fontsize=8.6,
            fontweight="bold", color=INK, linespacing=1.25)
    for i, (label, colour) in enumerate(rings):
        box(ax, 16.65, 8.2 - i * 1.65, 2.9, 1.25, colour, label, fs=8.1)
    arrow(ax, 10.8, 5.65, 16.35, 5.65, colour=DARK_GREEN)
    arrow(ax, 15.8, 2.75, 16.35, 2.75, colour=SOFT)
    arrow(ax, 19.85, 5.65, 20.45, 5.65, colour=SOFT, lw=2)
    box(ax, 20.5, 3.4, 2.3, 4.6, TEAL, "the query,\nshown,\nand its\ntable", fs=8.5)
    ax.text(0.3, 0.45, "A refused or stopped query is never run. Every query, recipe or not, can be opened in the "
            "SQL console and changed.", fontsize=8.4, color=SOFT)
    save(fig, "five_guards.png")


# =============================================================================
# 4. A GraphRAG answer, computed
# =============================================================================

def draw_graphrag_walk(G):
    question = "How does iturin suppress disease?"
    a = Q.ask(question, G, write=False)
    if a.verdict != Q.ANSWERED:
        print(f"  note: '{question}' is now {a.verdict}; update graphrag_walk.png")
    fig, ax = canvas(11.5, 6.2, "Ask the graph: an answer you can follow, step by step",
                     f"Computed by src/strainscope/ask_graph.py for \"{question}\"")
    walk = [a.hops[0]["step_from"]] + [h["step_to"] for h in a.hops]
    colours = [GOLD, PURPLE, DARK_GREEN, BLUE]
    xs = np.linspace(3.2, 19.8, len(walk))
    for i, (x, name) in enumerate(zip(xs, walk)):
        box(ax, x - 2.9, 8.0, 5.8, 1.5, colours[i % len(colours)], name, fs=9, bold=True)
        if i < len(walk) - 1:
            arrow(ax, x + 2.95, 8.75, xs[i + 1] - 2.95, 8.75, colour=SOFT, lw=2, text=a.hops[i]["relation"])
    ax.text(0.3, 10.35, "1  find what the question names: iturin (a compound)", fontsize=8.8, color=INK)
    ax.text(0.3, 7.25, "2  walk: the route to disease suppression, then everything iturin connects to; each step "
            "is a numbered fact", fontsize=8.8, color=INK)
    y = 6.7
    for n, f in enumerate(a.facts, start=1):
        source = f.source if len(f.source) < 110 else f.source[:107] + "..."
        ax.text(0.6, y, f"[{n}]", fontsize=8.2, color=SOFT, family="monospace", va="top")
        ax.text(1.5, y, f.text if len(f.text) < 95 else f.text[:92] + "...", fontsize=8.4, color=INK, va="top")
        ax.text(1.5, y - 0.42, f"source: {source}", fontsize=7.2, color=SOFT, va="top", style="italic")
        y -= 0.84
    ax.text(0.3, 0.05, "3  optional: a model writes 2 or 3 sentences that must cite these numbers and may not add "
            "a number of its own.", fontsize=8.8, color=INK)
    save(fig, "graphrag_walk.png")


# =============================================================================
# 5. Plain words, computed
# =============================================================================

def draw_plain_words():
    pred = sv.read_artifact("model/predictions.csv")
    reasons = sv.read_artifact("graph/explanations.csv")
    card = sv.model_card()
    sid = "STRAIN_0485"
    row = pred[pred["strain_id"] == sid].iloc[0].to_dict()
    nodes = sv.read_artifact("graph/nodes.csv")
    row["genus"] = nodes.loc[nodes["label"] == sid, "genus"].iloc[0]
    mine = reasons[reasons["strain_id"] == sid]
    short = [re.sub(r" the usual level\)", ")", t.split(":")[0]).replace(" and produces ", " + ")
             for t in mine["text"]]
    story = narrate.strain(row, mine, len(pred), card)
    fig, ax = canvas(11.5, 6.0, "In plain words: how a strain's rank becomes a paragraph",
                     "Rules fill in sentences with numbers that are already in the results. No model, so every "
                     "number can be traced.")
    facts = [("artifacts/model/predictions.csv", f"rank {int(row['rank'])} of {len(pred)}\nchance {row['probability']:.4f}\n"
              f"effective in the trial: {int(row['is_effective'])}", GOLD),
             ("artifacts/model/model_card.json", f"top {card['top_n_check']['n']}: "
              f"{card['top_n_check']['truly_effective']} effective", GOLD),
             ("artifacts/graph/explanations.csv", "\n".join(short) +
              f"\n{int(mine['mechanism_paths'].iloc[0])} mechanism paths", PURPLE)]
    y = 9.3
    for name, text, colour in facts:
        h = 0.75 + 0.42 * (text.count("\n") + 1)
        box(ax, 0.3, y - h, 7.2, h, colour, "", fill=tint(colour, 0.88))
        ax.text(0.55, y - 0.35, name, fontsize=7.8, family="monospace", color=INK, fontweight="bold", va="center")
        ax.text(0.55, y - 0.65, text, fontsize=7.7, color=INK, va="top", linespacing=1.35)
        y -= h + 0.35
    box(ax, 8.4, 3.2, 3.4, 5.6, BLUE, "the rules\nsrc/strainscope/\nnarrate.py\n\nchance -> words\n(over 99 %)\n"
        "band -> meaning\n(likely: above 70 %)\nreasons -> sentences", fs=7.9)
    arrow(ax, 7.55, 6.0, 8.35, 6.0, colour=SOFT, lw=2)
    arrow(ax, 11.85, 6.0, 12.65, 6.0, colour=SOFT, lw=2)
    import textwrap
    para = "\n\n".join("\n".join(textwrap.wrap(p, 62)) for p in story.paragraphs)
    box(ax, 12.7, 0.9, 10.0, 9.1, DARK_GREEN, "", fill=tint(DARK_GREEN, 0.93))
    ax.text(12.95, 9.6, "In plain words (the Strain page)", fontsize=8.8, fontweight="bold", color=DARK_GREEN)
    ax.text(12.95, 9.15, para, fontsize=6.9, color=INK, va="top", linespacing=1.32)
    extra = narrate.numbers_of(story.text) - story.numbers
    ax.text(0.3, 0.35, f"Checked for all {len(pred)} strains by tests/test_narrate.py: every number in the text is in "
            f"the results ({'none' if not extra else len(extra)} outside them here).", fontsize=8.2, color=SOFT)
    save(fig, "plain_words.png")


# =============================================================================
# 6. The golden questions of both assistants (computed) and the explorer
# =============================================================================

DATA_GROUPS = [("recipe", "a recipe answers it"), ("closest", "no recipe fits"), ("refuse", "off-topic, orders, changes")]
GRAPH_GROUPS = [("answer", "the graph answers it"), ("closest", "not covered"), ("refuse", "nothing from the graph")]


def data_results():
    rows = []
    for row in D.read_golden():
        a = D.ask(row["question"], write=False, run=False)
        hits = D.find_recipes(row["question"], D.recipe_index()) if a.verdict not in (D.REFUSED, D.VAGUE) else []
        rows.append({"question": row["question"], "expect": row["expect"], "verdict": a.verdict,
                     "score": min(hits[0].score, 1.0) if hits else 0.0,
                     "top": hits[0].recipe.question if hits else "refused before any search"})
    return rows


def graph_results(G):
    rows = []
    for row in Q.read_golden():
        a = Q.ask(row["question"], G, write=False)
        rows.append({"question": row["question"], "expect": row["expect"], "verdict": a.verdict,
                     "coverage": a.coverage if a.coverage is not None else (1.0 if a.strain else 0.0),
                     "facts": len(a.facts), "named": ", ".join(Q.label(G, n) for n in a.named) or "nothing"})
    return rows


def draw_golden(data_rows, graph_rows):
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.3), sharey=False)
    rng = np.random.default_rng(7)
    panels = [(axes[0], data_rows, DATA_GROUPS, "score", DATA_COLOUR, D.RECIPE_NEEDED,
               "best recipe's match (capped at 1: a recipe typed word for word)", "Ask the data"),
              (axes[1], graph_rows, GRAPH_GROUPS, "coverage", GRAPH_COLOUR, Q.COVERAGE_NEEDED,
               "share of the question's other words the facts use", "Ask the graph")]
    for ax, rows, groups, key, colours, line, xlabel, title in panels:
        for gi, (kind, _) in enumerate(groups):
            group = [r for r in rows if r["expect"] == kind]
            jitter = rng.uniform(-0.17, 0.17, len(group))
            for r, j in zip(group, jitter):
                ax.scatter(r[key], gi + j, s=44, color=colours[r["verdict"]], alpha=0.88, edgecolor="white",
                           lw=0.6, zorder=3)
        ax.axvline(line, color=DARK_GREEN, ls="--", lw=1.2)
        ax.set_yticks(range(len(groups)), [f"{label} ({sum(r['expect'] == k for r in rows)})" for k, label in groups],
                      fontsize=8.5)
        ax.set_ylim(len(groups) - 0.45, -0.55)
        ax.set_xlim(-0.04, 1.06)
        ax.set_xlabel(xlabel, fontsize=8.5)
        passed = sum((r["expect"] == "refuse" and r["verdict"] in ("refused", "vague"))
                     or (r["expect"] == "closest" and r["verdict"] not in ("recipe", "answered", "written"))
                     or (r["expect"] in ("recipe", "answer") and r["verdict"] in ("recipe", "answered"))
                     for r in rows)
        ax.set_title(f"{title}: {passed} of {len(rows)} golden questions as expected", fontsize=10, loc="left",
                     color=INK)
        seen = {r["verdict"] for r in rows}
        for verdict, colour in colours.items():
            if verdict in seen:
                ax.scatter([], [], color=colour, s=40, label=verdict)
        ax.legend(loc="lower right", fontsize=7.5, frameon=False)
    fig.text(0.01, -0.03, "Colour = what the assistant did. Dashed line: below it a recipe doesn't run (left) or the "
             "facts count as not covering the question (right). Refused questions sit at 0: they're never searched.",
             fontsize=7.5, color=GREY, style="italic")
    fig.tight_layout()
    save(fig, "assistant_golden_scores.png")


def write_explorer(data_rows, graph_rows):
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("  plotly missing, interactive explorer skipped")
        return
    sections = []
    for rows, groups, key, colours, line, title, hover, caption in (
            (data_rows, DATA_GROUPS, "score", DATA_COLOUR, D.RECIPE_NEEDED, "Ask the data: the golden questions",
             "top", "Each dot is one question from tests/golden_data_questions.csv, placed at the match of the "
             f"best Query Cookbook recipe; its colour is what Ask the data did. Below the dashed line ({D.RECIPE_NEEDED}) "
             "no recipe runs; above it, the recipe also has to use most of the question's words and every column it names."),
            (graph_rows, GRAPH_GROUPS, "coverage", GRAPH_COLOUR, Q.COVERAGE_NEEDED, "Ask the graph: the golden questions",
             "named", "Each dot is one question from tests/golden_graph_questions.csv, placed at the share of its "
             "words (apart from the names it found) that the facts use. Below the dashed line "
             f"({Q.COVERAGE_NEEDED:.0%}) the facts are shown as closest, not as an answer.")):
        fig = go.Figure()
        for verdict, colour in colours.items():
            pts = [r for r in rows if r["verdict"] == verdict]
            if not pts:
                continue
            ys = [next(label for k, label in groups if k == r["expect"]) for r in pts]
            fig.add_trace(go.Scatter(x=[r[key] for r in pts], y=ys, mode="markers", name=verdict,
                                     marker=dict(color=colour, size=11, line=dict(color="white", width=1)),
                                     customdata=[[r["question"], r[hover]] for r in pts],
                                     hovertemplate="<b>%{customdata[0]}</b><br>%{x:.2f}<br>%{customdata[1]}"
                                                   "<extra>" + verdict + "</extra>"))
        fig.add_vline(x=line, line_dash="dash", line_color=DARK_GREEN)
        fig.update_layout(template="plotly_white", height=380, title=title, xaxis=dict(range=[-0.05, 1.08]),
                          yaxis=dict(categoryorder="array", categoryarray=[label for _, label in groups][::-1]))
        sections.append((title, caption, fig))
    # one question at a time: every recipe's match
    index = D.recipe_index()
    questions = [r["question"] for r in data_rows if r["expect"] != "refuse"]
    fig = go.Figure()
    buttons = []
    for qi, q in enumerate(questions):
        hits = D.find_recipes(q, index, top=8)
        fig.add_trace(go.Bar(x=[min(h.score, 1.0) for h in hits], y=[h.recipe.question[:70] for h in hits],
                             orientation="h", marker_color=[DARK_GREEN if i == 0 else BLUE for i in range(len(hits))],
                             visible=qi == 0, showlegend=False,
                             hovertemplate="%{y}<br>match %{x:.3f}<extra></extra>"))
        buttons.append(dict(label=q[:60], method="update",
                            args=[{"visible": [i == qi for i in range(len(questions))]}, {"title": q}]))
    fig.add_vline(x=D.RECIPE_NEEDED, line_dash="dash", line_color=DARK_GREEN)
    fig.update_layout(template="plotly_white", height=460, title=questions[0], xaxis_title="match",
                      yaxis=dict(autorange="reversed"), margin=dict(l=420),
                      updatemenus=[dict(buttons=buttons, direction="down", x=1.0, xanchor="right", y=1.2, yanchor="top")])
    sections.append(("One question, every recipe", "Pick a question to see the eight recipes that match it best. "
                     "Green is the best; it runs only if it passes the dashed line and the word checks.", fig))
    rules = ("<table><tr><th>Assistant</th><th>Without a model</th><th>A model, if switched on, sees</th></tr>"
             "<tr><td>Ask StrainScope</td><td>passages, word for word</td><td>the question and up to 3 passages</td></tr>"
             "<tr><td>Ask the data</td><td>a tested recipe, run through four guards</td><td>the question, table and "
             "column names, 3 recipes; never a row</td></tr><tr><td>Ask the graph</td><td>numbered facts with "
             "sources</td><td>the question and the facts; never a strain</td></tr></table>")
    parts = ["<!doctype html><html><head><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width, initial-scale=1'>",
             "<title>StrainScope: Ask the data and Ask the graph</title>",
             "<style>body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1100px;"
             "margin:24px auto;padding:0 16px;color:#1F2933}h1{font-size:22px}h2{font-size:17px;"
             "margin-top:36px}p{color:#5f6b7a;line-height:1.5}table{border-collapse:collapse;margin:12px 0}"
             "td,th{border:1px solid #DCE6F5;padding:6px 10px;text-align:left;font-size:14px}</style></head><body>",
             "<h1>StrainScope · Phase 7: Ask the data and Ask the graph</h1>",
             "<p>How the two Phase 7 assistants handle their golden questions, and what each would send to a "
             "language model. The guide is <code>docs/08-deployment-ai.md</code>.</p>", rules]
    if not (INT / "plotly.min.js").exists():
        from plotly.offline import get_plotlyjs
        (INT / "plotly.min.js").write_text(get_plotlyjs(), encoding="utf-8")
    parts.append("<script src='plotly.min.js'></script>")
    for title, caption, fig in sections:
        parts.append(f"<h2>{title}</h2><p>{caption}</p>")
        parts.append(fig.to_html(full_html=False, include_plotlyjs=False))
    parts.append("</body></html>")
    (INT / "assistants_explorer.html").write_text("\n".join(parts), encoding="utf-8")
    print(f"  drew docs/interactive/assistants_explorer.html (interactive, {len(sections)} charts)")


if __name__ == "__main__":
    if not sv.DB_PATH.exists():
        sys.exit("Build the database first (python src/strainscope/harmonize.py and the three publish steps).")
    print("Phase 7 figures:")
    graph = sv.load_full_graph()
    draw_deployment_map()
    draw_three_assistants()
    draw_five_guards()
    draw_graphrag_walk(graph)
    draw_plain_words()
    d_rows, g_rows = data_results(), graph_results(graph)
    draw_golden(d_rows, g_rows)
    write_explorer(d_rows, g_rows)
