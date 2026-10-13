"""
figures/make_phase9_figures.py: the teaching figures for Phase 9 (the whole workflow, on your own data).
=======================================================================================================
  Drawn from the project's own code, so they stay true when it changes:
    docs/img/workflow_steps.png     the workflow in pictures: three tables in, every page of the app out
                                    (also shown at the top of the app's Workflow page)
    figures/three_tables.png        the three tables a dataset of your own is made of, with real rows
                                    from the example (src/strainscope/datasets.py, example())
    figures/dataset_folders.png     where the library's files live, and where a dataset's go
                                    (src/strainscope/paths.py)
    figures/check_levels.png        errors, warnings and notes: real messages from the checks
                                    (datasets.check_tables on the example with mistakes put in)
    figures/library_vs_yours.png    what changes when there's no answer key
    figures/your_data_where.png     where your data goes, on your own computer and on the shared copy
    docs/interactive/workflow_explorer.html
                                    the steps, what each one reads and writes, measured run times,
                                    the checks and the limits, to click through

Run (from the project root, venv active):
    python figures/make_phase9_figures.py

The drawing helpers are shared with figures/make_phase6_figures.py.
"""
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "figures"))

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402
from make_phase6_figures import (BLUE, DARK_GREEN, GOLD, GREY, INK, PURPLE, RED, SOFT, TEAL,  # noqa: E402
                                 arrow, box, canvas, save, tint)
from strainscope import datasets as ds  # noqa: E402
from strainscope import service as sv  # noqa: E402

IMG = ROOT / "docs" / "img"
INT = ROOT / "docs" / "interactive"

# Run times measured with `python src/strainscope/pipeline.py --dataset NAME` on 2026-10-13, on a
# Linux computer without R (so no DIABLO). Seconds per step, as each dataset's dataset.json recorded them.
TIMINGS = [
    {"name": "example120", "what": "the example, 120 strains, quick settings",
     "steps": {"harmonize.py": 0.8, "integrate.py": 2.0, "model.py": 36.5, "graph.py": 2.2}},
    {"name": "seed7_300", "what": "simulated, 300 strains, quick settings",
     "steps": {"generate_data.py": 0.6, "harmonize.py": 0.6, "integrate.py": 2.1, "model.py": 38.7, "graph.py": 2.4}},
    {"name": "seed42_600_quick", "what": "simulated, 600 strains, quick settings",
     "steps": {"generate_data.py": 0.6, "harmonize.py": 0.7, "integrate.py": 2.1, "model.py": 65.1, "graph.py": 3.4}},
    {"name": "seed42_600", "what": "simulated, 600 strains, full settings (the library's)",
     "steps": {"generate_data.py": 0.6, "harmonize.py": 0.7, "integrate.py": 3.6, "model.py": 170.2, "graph.py": 3.3}},
    {"name": "seed11_1000", "what": "simulated, 1,000 strains, quick settings",
     "steps": {"generate_data.py": 0.6, "harmonize.py": 0.7, "integrate.py": 2.1, "model.py": 66.6, "graph.py": 4.1}},
]


def save_img(fig, name):
    fig.savefig(IMG / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  drew docs/img/{name}")


# =============================================================================
# Small pictographs
# =============================================================================

def table_icon(ax, x, y, colour, w=1.5, h=1.1):
    ax.add_patch(Rectangle((x, y), w, h, facecolor="white", edgecolor=colour, lw=1.4))
    ax.add_patch(Rectangle((x, y + h * 0.72), w, h * 0.28, facecolor=tint(colour, 0.5), edgecolor=colour, lw=1.4))
    for k in (1, 2):
        ax.plot([x, x + w], [y + h * 0.72 * k / 3, y + h * 0.72 * k / 3], color=colour, lw=0.8)
    ax.plot([x + w * 0.35, x + w * 0.35], [y, y + h], color=colour, lw=0.8)


def icon(ax, kind, cx, cy, colour):
    """A small picture for each step, drawn around (cx, cy)."""
    if kind == "tables":
        for k in range(3):
            table_icon(ax, cx - 1.4 + k * 0.55, cy - 0.85 + k * 0.32, colour, 1.3, 0.95)
    elif kind == "clean":
        ax.add_patch(Rectangle((cx - 0.8, cy - 0.9), 1.6, 1.8, facecolor="white", edgecolor=colour, lw=1.4))
        for k in range(4):
            yy = cy + 0.55 - k * 0.42
            ax.plot([cx - 0.55, cx + 0.25], [yy, yy], color=colour, lw=1.1)
            ax.text(cx + 0.48, yy, "✓", ha="center", va="center", fontsize=8, color=DARK_GREEN)
    elif kind == "together":
        ax.add_patch(Circle((cx - 0.4, cy), 0.75, facecolor=tint(BLUE, 0.6), edgecolor=BLUE, lw=1.4, alpha=0.9))
        ax.add_patch(Circle((cx + 0.4, cy), 0.75, facecolor=tint(GOLD, 0.6), edgecolor=GOLD, lw=1.4, alpha=0.75))
    elif kind == "predict":
        for k, hgt in enumerate((0.5, 0.9, 1.4, 1.75)):
            ax.add_patch(Rectangle((cx - 0.9 + k * 0.48, cy - 0.9), 0.36, hgt, facecolor=tint(colour, 0.35),
                                   edgecolor=colour, lw=1.0))
        ax.plot([cx - 1.0, cx + 1.0], [cy - 0.9, cy - 0.9], color=INK, lw=1.0)
    elif kind == "graph":
        pts = [(cx - 0.9, cy + 0.5), (cx, cy + 0.85), (cx + 0.85, cy + 0.2), (cx - 0.3, cy - 0.15),
               (cx + 0.3, cy - 0.8), (cx - 0.95, cy - 0.65)]
        for a, b in ((0, 1), (1, 2), (0, 3), (3, 2), (3, 4), (5, 3), (5, 4)):
            ax.plot([pts[a][0], pts[b][0]], [pts[a][1], pts[b][1]], color=colour, lw=1.0)
        for p in pts:
            ax.add_patch(Circle(p, 0.17, facecolor=tint(colour, 0.3), edgecolor=colour, lw=1.0))
    elif kind == "app":
        ax.add_patch(Rectangle((cx - 1.1, cy - 0.85), 2.2, 1.7, facecolor="white", edgecolor=colour, lw=1.4))
        ax.add_patch(Rectangle((cx - 1.1, cy + 0.55), 2.2, 0.3, facecolor=tint(colour, 0.5), edgecolor=colour, lw=1.4))
        ax.add_patch(Rectangle((cx - 1.0, cy - 0.75), 0.5, 1.2, facecolor=tint(colour, 0.75), edgecolor="none"))
        for k in range(3):
            ax.plot([cx - 0.35, cx + 0.9], [cy + 0.25 - k * 0.35, cy + 0.25 - k * 0.35], color=GREY, lw=1.0)


# =============================================================================
# 1. The workflow in pictures (also on the app's Workflow page)
# =============================================================================

def draw_workflow_steps():
    fig, ax = canvas(12, 3.9, "From three tables to every page of the app",
                     "The Workflow page runs these steps in the dataset's own folder (the library is never "
                     "changed). A simulated dataset starts with the generator.")
    steps = [("tables", "Your data", "three tables,\nchecked cell by cell", GREY),
             ("clean", "1. Clean", "duplicates, typos, drift:\nevery change counted", BLUE),
             ("together", "2. Read together", "genes and chemistry:\none shared story", GOLD),
             ("predict", "3. Predict", "models tested on\nstrains they never saw", DARK_GREEN),
             ("graph", "4. Knowledge graph", "a source on\nevery connection", PURPLE),
             ("app", "Every page", "Ranking, Strain page,\nGraph, SQL, Ask", TEAL)]
    for i, (kind, title, note, colour) in enumerate(steps):
        x = 0.3 + i * 3.95
        box(ax, x, 0.35, 3.45, 6.0, colour, "", fill=tint(colour, 0.9))
        icon(ax, kind, x + 1.72, 4.25, colour)
        ax.text(x + 1.72, 2.55, title, ha="center", fontsize=9.6, fontweight="bold", color=INK)
        ax.text(x + 1.72, 2.05, note, ha="center", va="top", fontsize=7.8, color=SOFT, linespacing=1.3)
        if i < len(steps) - 1:
            arrow(ax, x + 3.5, 3.4, x + 3.9, 3.4, colour=INK)
    save_img(fig, "workflow_steps.png")


# =============================================================================
# 2. The three tables, with real rows from the example
# =============================================================================

def draw_three_tables():
    t = ds.example(120, 7)
    fig, ax = canvas(12, 6.8, "A dataset of your own: three tables, one row per strain",
                     "The same layout as the library's raw files. These rows come from the example "
                     "(python src/strainscope/datasets.py example), which is simulated.")
    shown = {"genomics": ["strain_id", "ituA", "srfAA", "chiA", "accA"],
             "metabolomics": ["strain_id", "iturin", "surfactin", "DAPG"],
             "phenotype": ["strain_id", "kingdom", "suppression_score", "genus"]}
    rules = {"genomics": "1 = carries the gene, 0 = doesn't,\nempty = not known (yes/no also work)",
             "metabolomics": "the level the lab measured (0 or more),\nempty = not measured",
             "phenotype": "kingdom: Bacteria, Fungi, Yeast or Oomycete\nsuppression_score: % of disease suppressed"}
    colours = {"genomics": BLUE, "metabolomics": GOLD, "phenotype": DARK_GREEN}
    required = {"strain_id", "kingdom", "suppression_score"}
    for i, name in enumerate(ds.TABLES):
        x0, colour = 0.3 + i * 8.0, colours[name]
        ax.text(x0, 11.5, f"{name}.csv", fontsize=10.4, fontweight="bold", color=INK, family="monospace")
        ax.text(x0, 11.05, ds.WHAT[name], fontsize=8.4, color=SOFT)
        cols = shown[name]
        rows = t[name].head(5)
        longest = [max([len(c)] + [len(f"{v:g}" if isinstance(v, float) and v == v else str(v))
                                   for v in rows[c]]) for c in cols]
        widths = [max(n, 5) for n in longest]
        scale = 7.4 / sum(widths)
        widths = [w * scale for w in widths]
        for r in range(len(rows) + 2):
            y = 9.9 - r * 0.95
            xx = x0
            for c, w in zip(cols, widths):
                header = r == 0
                if r == len(rows) + 1:
                    text = "..."
                elif header:
                    text = c
                else:
                    v = rows.iloc[r - 1][c]
                    text = "" if v != v else (f"{v:g}" if isinstance(v, float) else str(v))
                ax.add_patch(Rectangle((xx, y), w, 0.9, facecolor=tint(colour, 0.55) if header else "white",
                                       edgecolor=tint(colour, 0.2), lw=0.8))
                weight = "bold" if header and (c in required) else "normal"
                style = "italic" if header and c not in required and name == "phenotype" else "normal"
                ax.text(xx + w / 2, y + 0.45, text, ha="center", va="center", fontsize=6.6, color=INK,
                        fontweight=weight, style=style, family="monospace")
                xx += w
        ax.text(x0, 3.1, rules[name], fontsize=8.0, color=INK, va="top", linespacing=1.4)
    ax.text(0.3, 1.2, "Needed: strain_id in every table; kingdom and suppression_score (bold). If you have them: "
            "is_effective, genus, batch_id, collection_site, isolation_date (italic).\nAny gene and compound names "
            f"(a letter first, then letters, digits and _). At least {ds.MIN_STRAINS} strains in all three tables, "
            f"{ds.MIN_PER_CLASS} effective and {ds.MIN_PER_CLASS} not.", fontsize=8.1, color=SOFT, va="top",
            linespacing=1.5)
    save(fig, "three_tables.png")


# =============================================================================
# 3. Where the files live
# =============================================================================

def tree(ax, x, y, lines, colour, step=0.62):
    for k, (depth, text, note) in enumerate(lines):
        yy = y - k * step
        ax.text(x + depth * 0.55, yy, text, fontsize=8.3, color=INK, family="monospace", va="center")
        if note:
            ax.text(x + 6.7, yy, note, fontsize=7.6, color=SOFT, va="center")


def draw_dataset_folders():
    fig, ax = canvas(12, 6.6, "One set of scripts, two kinds of place",
                     "The built-in library keeps the folders of Phases 1 to 8. A dataset gets the same layout in a "
                     "folder of its own (src/strainscope/paths.py).")
    box(ax, 0.3, 0.4, 11.4, 11.0, BLUE, "", fill=tint(BLUE, 0.9))
    ax.text(6.0, 10.85, "the built-in library", ha="center", fontsize=10.2, fontweight="bold", color=INK)
    tree(ax, 0.7, 9.9, [(0, "data/raw/", "the three raw tables"),
                        (0, "data/processed/", ""),
                        (1, "genomics_clean.csv ...", "the clean tables"),
                        (1, "strainscope.duckdb", "the database"),
                        (0, "artifacts/", "committed to Git"),
                        (1, "integration/", "Phase 3"),
                        (1, "model/", "Phase 4"),
                        (1, "graph/", "Phase 5"),
                        (0, "figures/diablo_*.png", "DIABLO's pictures")], BLUE)
    ax.text(0.7, 3.4, "STRAINSCOPE_DATASET unset or empty", fontsize=8.2, color=SOFT, family="monospace")
    ax.text(0.7, 2.75, "the app's sidebar: Simulated library (built in)", fontsize=8.2, color=SOFT)
    box(ax, 12.3, 0.4, 11.4, 11.0, DARK_GREEN, "", fill=tint(DARK_GREEN, 0.9))
    ax.text(18.0, 10.85, "a dataset, for example trial", ha="center", fontsize=10.2, fontweight="bold", color=INK)
    tree(ax, 12.7, 9.9, [(0, "data/processed/datasets/trial/", ""),
                         (1, "dataset.json", "what it is, how far it got"),
                         (1, "raw/", "your three tables"),
                         (1, "processed/", "clean tables, database"),
                         (1, "artifacts/", "never committed"),
                         (2, "integration/ model/ graph/", ""),
                         (1, "figures/", "DIABLO's, with R")], DARK_GREEN)
    ax.text(12.7, 3.4, "STRAINSCOPE_DATASET=trial", fontsize=8.2, color=SOFT, family="monospace")
    ax.text(12.7, 2.75, "the app's sidebar: trial (your data, ... strains)", fontsize=8.2, color=SOFT)
    ax.text(12.7, 1.5, "Everything under data/ stays on your computer:\nGit and the container build both leave it out.",
            fontsize=8.0, color=INK, va="top", linespacing=1.4)
    save(fig, "dataset_folders.png")


# =============================================================================
# 4. Errors, warnings and notes: real messages
# =============================================================================

def example_messages() -> dict[str, list[str]]:
    """Real messages: the example's tables with a few mistakes put in, checked."""
    text = {n: ds.read_table(df.to_csv(index=False).encode())[0] for n, df in ds.example(120, 7).items()}
    text["genomics"].loc[4, "ituA"] = "maybe"
    text["metabolomics"].loc[2, "iturin"] = "2,5"
    bad = ds.check_tables(text["genomics"], text["metabolomics"], text["phenotype"])
    text = {n: ds.read_table(df.to_csv(index=False).encode())[0] for n, df in ds.example(120, 7).items()}
    text["metabolomics"] = text["metabolomics"].iloc[2:]
    text["phenotype"] = text["phenotype"].drop(columns=["batch_id", "is_effective"])
    good = ds.check_tables(text["genomics"], text["metabolomics"], text["phenotype"])
    out = {"error": bad.errors}
    for level in ("warning", "note"):
        out[level] = [m for lv, m in good.problems if lv == level]
    return out


def draw_check_levels():
    found = example_messages()
    fig, ax = canvas(12, 4.9, "Before anything is saved: errors, warnings and notes",
                     "Real messages from datasets.py check, on the example with a few mistakes put in. "
                     "Row numbers count the header as row 1.")
    columns = [("error", "Errors", "stop: nothing is saved\nuntil each one is fixed", RED),
               ("warning", "Warnings", "saved, but something was\nleft out or rests on little", GOLD),
               ("note", "Notes", "saved; it says what\nwas assumed", BLUE)]
    for i, (level, title, meaning, colour) in enumerate(columns):
        x = 0.3 + i * 8.0
        box(ax, x, 0.3, 7.4, 8.0, colour, "", fill=tint(colour, 0.9))
        ax.text(x + 3.7, 7.75, title, ha="center", fontsize=10.6, fontweight="bold", color=INK)
        ax.text(x + 3.7, 7.25, meaning, ha="center", va="top", fontsize=8.2, color=SOFT, linespacing=1.3)
        y = 5.9
        for message in found[level][:2]:
            short = message if len(message) < 210 else message[:205].rsplit(" ", 1)[0] + " ..."
            lines = textwrap.fill(short.replace("`", ""), 46, break_long_words=False)
            n = lines.count("\n") + 1
            h = 0.36 * n + 0.35
            box(ax, x + 0.3, y - h, 6.8, h, colour, "", fill="white")
            ax.text(x + 0.5, y - 0.2, lines, fontsize=6.9, color=INK, va="top", linespacing=1.3)
            y -= h + 0.3
    save(fig, "check_levels.png")


# =============================================================================
# 5. The library and your data
# =============================================================================

def draw_library_vs_yours():
    rows = [("an answer key (which features really drive the outcome)", "✓ the simulation planted it", "✗ none"),
            ("report cards and communities graded against it", "✓ graded", "✗ shown as found"),
            ("mechanisms in the knowledge graph", "✓ for every weapon", "✓ for every name it knows"),
            ("the source on a strain's edges", "synthetic library", "your data"),
            ("the model card's \"not for\" line", "the data is simulated", "check the ranking in the lab"),
            ("Ask the data writes SQL with a model (when one is on)", "✓ when no recipe fits", "✗ recipes only"),
            ("Ask the graph writes an answer with a model", "✓ from the facts", "✗ facts and route only"),
            ("DIABLO (R)", "✓ committed results", "✓ where R is installed")]
    fig, ax = canvas(12, 6.0, "The library and your own data: what changes",
                     "Same scripts, same steps. Without an answer key nothing is graded, and nothing about your "
                     "data reaches a language model.")
    ax.text(14.2, 9.95, "library and simulated datasets", fontsize=9.2, fontweight="bold", color=INK, ha="center")
    ax.text(20.6, 9.95, "your own data", fontsize=9.2, fontweight="bold", color=INK, ha="center")
    for k, (what, lib, yours) in enumerate(rows):
        y = 9.0 - k * 1.05
        box(ax, 0.3, y - 0.42, 23.4, 0.86, GREY, "", fill=tint(GREY, 0.92 if k % 2 else 0.97))
        ax.text(0.6, y, what, fontsize=8.1, color=INK, va="center")
        ax.text(14.2, y, lib, fontsize=7.9, color=DARK_GREEN if lib.startswith("✓") else INK, va="center",
                ha="center")
        ax.text(20.6, y, yours, fontsize=7.9, color=RED if yours.startswith("✗") else
                (DARK_GREEN if yours.startswith("✓") else INK), va="center", ha="center")
    save(fig, "library_vs_yours.png")


# =============================================================================
# 6. Where your data goes
# =============================================================================

def draw_your_data_where():
    local, shared = ds.LIMITS["local"], ds.LIMITS["shared"]
    fig, ax = canvas(12, 6.0, "Where your data goes",
                     "A dataset is written to a folder because every phase reads and writes files. "
                     "It's never committed, and never sent to a language model.")
    panels = [("on your own computer", BLUE,
               ["data/processed/datasets/<name>/", "stays until you delete it", "Git never sees it",
                f"up to {local['strains']:,} strains, {local['genes']} genes, {local['compounds']} compounds",
                "full or quick settings, your choice", "DIABLO too, when R is installed"]),
              ("on the shared online copy", PURPLE,
               ["a folder on the host, named visit_...", "only your browser tab lists it",
                f"deleted {ds.SHARED_MAX_AGE_HOURS} hour after you last use it",
                f"up to {shared['strains']:,} strains, {shared['genes']} genes, {shared['compounds']} compounds",
                f"quick settings ({ds.QUICK_REPEATS} repeats), one run at a time", "no R there, so no DIABLO"])]
    for i, (title, colour, items) in enumerate(panels):
        x = 0.3 + i * 12.0
        box(ax, x, 2.2, 11.4, 7.9, colour, "", fill=tint(colour, 0.88))
        ax.text(x + 5.7, 9.5, title, ha="center", fontsize=10.4, fontweight="bold", color=INK)
        for k, item in enumerate(items):
            box(ax, x + 0.4, 7.95 - k * 1.0, 10.6, 0.8, colour, item, fs=8.4, fill="white")
    box(ax, 0.3, 0.3, 23.4, 1.5, RED, "Never: a row, a column name or a result of your own data sent to a language "
        "model (Ask the data uses recipes only, Ask the graph facts only)", fs=8.6, fill=tint(RED, 0.9))
    save(fig, "your_data_where.png")


# =============================================================================
# 7. The interactive page
# =============================================================================

def write_explorer():
    reads = {"generate_data.py": "the dataset's seed and size (dataset.json)", "harmonize.py": "raw/ (the three tables)",
             "integrate.py": "the clean tables in the database", "model.py": "the clean tables in the database",
             "graph.py": "the clean tables, the domain model, Phases 3 and 4"}
    steps = []
    for script, (where, name) in ds.RECEIPTS.items():
        steps.append({"script": script, "name": sv.STEP_NAMES[script], "reads": reads[script],
                      "receipt": f"{where}/{name}".replace("integration/", "artifacts/integration/")
                      .replace("model/", "artifacts/model/").replace("graph/", "artifacts/graph/")})
    plans = {k: {"title": sv.PIPELINES[k]["title"], "takes": sv.PIPELINES[k]["takes"],
                 "steps": [sv.step_label(s) for s in sv.PIPELINES[k]["steps"]]} for k in ("simulate", "workflow")}
    data = json.dumps({"steps": steps, "plans": plans, "timings": TIMINGS, "checks": example_messages(),
                       "limits": ds.LIMITS, "quick": ds.QUICK_REPEATS, "min": [ds.MIN_STRAINS, ds.MIN_PER_CLASS],
                       "names": sv.STEP_NAMES}, ensure_ascii=False)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>StrainScope: the whole workflow</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1F2933;background:#FFFFFF}}
h1{{font-size:22px}} h2{{font-size:16px;margin:18px 0 6px}} p{{color:#4B5563;line-height:1.5}}
.tabs button{{margin:0 6px 8px 0;padding:8px 12px;border:1px solid #DCE6F5;border-radius:8px;background:#F5F9FF;font-size:14px;cursor:pointer;color:#1F2933}}
.tabs button[aria-selected="true"]{{background:#E6F4EA;border-color:#2E7D5B;font-weight:600}}
button:focus-visible{{outline:3px solid #1A5FA6;outline-offset:2px}}
table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid #E3E6EA;padding:6px 8px;text-align:left;vertical-align:top;font-size:14px}}
code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}}
.bar{{display:flex;height:22px;border-radius:4px;overflow:hidden;min-width:2px}} .bar span{{display:block;height:100%}}
.legend span{{display:inline-block;margin-right:14px;font-size:13px}} .legend i{{display:inline-block;width:12px;height:12px;margin-right:5px;vertical-align:-1px;border-radius:2px}}
.error{{border-left:4px solid #D9634C}} .warning{{border-left:4px solid #C9A227}} .note{{border-left:4px solid #5B8DEF}}
.msg{{padding:6px 10px;margin:6px 0;background:#FAFBFC;font-size:14px;line-height:1.45}}
</style></head><body>
<h1>StrainScope: the whole workflow, on your own data</h1>
<p>Phase 9 in four views, built from the project's own code: the steps and what each one reads and writes
(<code>src/strainscope/datasets.py</code>, <code>src/strainscope/service.py</code>), how long a run took,
the checks a dataset passes before it's saved, and the limits. The guide is
<code>docs/10-workflow-and-your-data.md</code>.</p>
<div class="tabs" role="tablist">
<button role="tab" id="t-steps" aria-selected="true" onclick="tab('steps')">The steps</button>
<button role="tab" id="t-time" aria-selected="false" onclick="tab('time')">How long</button>
<button role="tab" id="t-checks" aria-selected="false" onclick="tab('checks')">The checks</button>
<button role="tab" id="t-limits" aria-selected="false" onclick="tab('limits')">Limits</button>
</div>
<div id="view"></div>
<script>
const D = {data};
const esc = s => String(s).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}})[c]);
const COLOURS = {{"generate_data.py":"#8A94A6","harmonize.py":"#5B8DEF","integrate.py":"#C9A227","model.py":"#2E7D5B","graph.py":"#9C6ADE"}};
function tab(name) {{
  ['steps','time','checks','limits'].forEach(t => document.getElementById('t-'+t).setAttribute('aria-selected', t === name));
  const v = document.getElementById('view');
  if (name === 'steps') {{
    v.innerHTML = '<p>A dataset of your own runs the <b>workflow</b> plan; a simulated one runs <b>simulate</b>, which '
      + 'starts with the generator. Each step runs in the dataset\\'s folder. A step counts as done when its last file '
      + '(the receipt) exists and is newer than the step before it.</p><table><tr><th>Step</th><th>Reads</th>'
      + '<th>Its last file (in the dataset folder)</th></tr>' + D.steps.map(s => '<tr><td><b>' + esc(s.name)
      + '</b><br><code>python src/strainscope/' + esc(s.script) + '</code></td><td>' + esc(s.reads) + '</td><td><code>'
      + esc(s.receipt) + '</code></td></tr>').join('') + '</table>' + Object.entries(D.plans).map(([k, p]) =>
      '<h2>' + esc(k) + ': ' + esc(p.title) + '</h2><p>' + esc(p.takes) + '.</p><ol>' + p.steps.map(s => '<li><code>'
      + esc(s) + '</code></li>').join('') + '</ol>').join('');
  }}
  if (name === 'time') {{
    const most = Math.max(...D.timings.map(t => Object.values(t.steps).reduce((a, b) => a + b, 0)));
    v.innerHTML = '<p>Measured on 2026-10-13 on a Linux computer without R (so without DIABLO), with '
      + '<code>python src/strainscope/pipeline.py --dataset NAME</code>. Quick settings use ' + D.quick
      + ' cross-validation repeats instead of 10. Learning to predict takes most of the time.</p><div class="legend">'
      + Object.entries(COLOURS).map(([k, c]) => '<span><i style="background:' + c + '"></i>' + esc(D.names[k]) + '</span>').join('')
      + '</div><table><tr><th>Dataset</th><th style="width:55%">Seconds per step</th><th>In all</th></tr>'
      + D.timings.map(t => {{ const total = Object.values(t.steps).reduce((a, b) => a + b, 0);
        return '<tr><td><code>' + esc(t.name) + '</code><br>' + esc(t.what) + '</td><td><div class="bar" style="width:'
        + (100 * total / most).toFixed(1) + '%">' + Object.entries(t.steps).map(([k, s]) => '<span title="'
        + esc(D.names[k]) + ': ' + s + ' s" style="width:' + (100 * s / total).toFixed(2) + '%;background:' + COLOURS[k]
        + '"></span>').join('') + '</div><div style="font-size:12px;color:#5f6b7a">' + Object.entries(t.steps).map(([k, s]) =>
        esc(D.names[k]) + ' ' + s + ' s').join(' · ') + '</div></td><td>' + Math.round(total) + ' s</td></tr>'; }}).join('')
      + '</table>';
  }}
  if (name === 'checks') {{
    v.innerHTML = '<p>Real messages from the checks, on the example with a few mistakes put in. Errors stop the save; '
      + 'warnings say what was left out or rests on very little; notes say what was assumed.</p>' + ['error','warning','note'].map(l =>
      '<h2>' + {{error:'Errors',warning:'Warnings',note:'Notes'}}[l] + '</h2>' + D.checks[l].map(m =>
      '<div class="msg ' + l + '">' + esc(m) + '</div>').join('')).join('');
  }}
  if (name === 'limits') {{
    const L = D.limits;
    v.innerHTML = '<table><tr><th></th><th>On your own computer</th><th>On a shared copy</th></tr>'
      + [['strains', 'strains'], ['genes', 'genes'], ['compounds', 'compounds'], ['megabytes', 'size of one file (MB)']]
        .map(([k, w]) => '<tr><td>' + w + '</td><td>' + L.local[k].toLocaleString('en') + '</td><td>'
        + L.shared[k].toLocaleString('en') + '</td></tr>').join('')
      + '<tr><td>settings</td><td>full (10 repeats) or quick (' + D.quick + ')</td><td>quick (' + D.quick + ')</td></tr>'
      + '<tr><td>kept</td><td>until you delete it</td><td>an hour after its last use; only the browser tab that made it '
      + 'lists it</td></tr></table><p>At least ' + D.min[0] + ' strains in all three tables, with at least ' + D.min[1]
      + ' effective and ' + D.min[1] + ' not, so a model has both sides to learn from.</p>';
  }}
}}
tab('steps');
</script></body></html>
"""
    (INT / "workflow_explorer.html").write_text(page, encoding="utf-8")
    print(f"  drew docs/interactive/workflow_explorer.html (interactive, {len(steps)} steps, {len(TIMINGS)} timed runs)")


if __name__ == "__main__":
    print("Phase 9 figures:")
    draw_workflow_steps()
    draw_three_tables()
    draw_dataset_folders()
    draw_check_levels()
    draw_library_vs_yours()
    draw_your_data_where()
    write_explorer()
