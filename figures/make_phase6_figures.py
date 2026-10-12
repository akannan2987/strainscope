"""
figures/make_phase6_figures.py: the teaching figures for Phase 6 (the app).
==========================================================================
  CONCEPTS (drawn, no data needed):
    figures/app_rerun.png        how a Streamlit page runs: every click reruns the script, the cache
                                 keeps what's slow, session state keeps what's yours
    figures/app_map.png          the seven pages and the files each one reads
    figures/sql_guards.png       the four guards around the SQL console, and what each one stops
    figures/upload_journey.png   your CSV file, checked, scored, explained, handed back

  RESULTS (computed, never invented; needs the database for the example strains):
    figures/two_scores.png       the same twelve strains scored two ways: out-of-fold (the ranking)
                                 and by the final model (an upload)

Run (from the project root, venv active):
    python figures/make_phase6_figures.py

The screenshots of the running app (docs/img/app_*.png and docs/img/app_tour.gif)
come from a separate, optional script: figures/take_app_screenshots.py.
"""
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

BLUE, GREEN, GOLD, GREY, PURPLE, RED = ("#5B8DEF", "#4CAF7D", "#C9A227",
                                        "#8A94A6", "#9C6ADE", "#D9634C")
INK, SOFT, DARK_GREEN, TEAL = "#1F2933", "#5f6b7a", "#2E7D5B", "#2BA6A6"
plt.rcParams.update({"figure.dpi": 130, "font.size": 10, "axes.grid": False,
                     "axes.spines.top": False, "axes.spines.right": False})


def tint(hex_colour, amount=0.82):
    rgb = np.array([int(hex_colour[i:i + 2], 16) for i in (1, 3, 5)]) / 255
    return tuple(rgb + (1 - rgb) * amount)


def box(ax, x, y, w, h, colour, text="", fs=9.5, bold=False, dashed=False, fill=None, text_colour=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                facecolor=fill if fill is not None else tint(colour), edgecolor=colour, lw=1.6,
                                linestyle="--" if dashed else "-"))
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=text_colour,
                fontweight="bold" if bold else "normal", linespacing=1.35)


def arrow(ax, x1, y1, x2, y2, colour=SOFT, lw=1.6, ls="-", rad=0.0, text="", fs=8.5):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, color=colour,
                                 lw=lw, linestyle=ls, connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.18, text, ha="center", va="bottom", fontsize=fs,
                color=colour, style="italic")


def canvas(w, h, title, subtitle=""):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w * 2)
    ax.set_ylim(0, h * 2)
    ax.axis("off")
    ax.text(0.15, h * 2 - 0.25, title, fontsize=13, fontweight="bold", color=INK, va="top")
    if subtitle:
        ax.text(0.15, h * 2 - 0.78, subtitle, fontsize=9.5, color=SOFT, va="top")
    return fig, ax


def save(fig, name):
    fig.savefig(FIG / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  drew figures/{name}")


# =============================================================================
# 1. How a Streamlit page runs
# =============================================================================

def draw_rerun():
    fig, ax = canvas(11, 4.6, "How a Streamlit page runs",
                     "Every click runs the page's script again from the top. Two helpers keep that quick "
                     "and keep your choices.")
    steps = [("1", "You click", "move a slider,\npick a strain,\npress a button", BLUE),
             ("2", "The script reruns", "top to bottom,\nlike reading a recipe\nfrom the first line", PURPLE),
             ("3", "Slow parts come\nfrom the cache", "files and the graph\nwere read once and\nare kept in memory", GOLD),
             ("4", "The page is\nredrawn", "with the new\nnumbers, in well\nunder a second", GREEN)]
    for i, (num, head, body, colour) in enumerate(steps):
        x = 0.4 + i * 5.4
        box(ax, x, 3.4, 4.3, 3.6, colour)
        ax.add_patch(plt.Circle((x + 2.15, 7.0), 0.36, color=colour, zorder=3))   # the step number, on the top edge
        ax.text(x + 2.15, 7.0, num, ha="center", va="center", color="white", fontweight="bold", fontsize=11, zorder=4)
        ax.text(x + 2.15, 5.95, head, ha="center", va="center", fontsize=10.5, fontweight="bold", color=INK)
        ax.text(x + 2.15, 4.4, body, ha="center", va="center", fontsize=9.2, color=INK, linespacing=1.4)
        if i < 3:
            arrow(ax, x + 4.35, 5.2, x + 5.35, 5.2, colour=SOFT, lw=2)
    arrow(ax, 21.2, 3.35, 2.6, 3.35, colour=SOFT, ls="--", rad=-0.12)
    ax.text(11.9, 2.55, "the next click starts again at 1", ha="center", fontsize=9, color=SOFT, style="italic")
    # the two helpers
    box(ax, 0.4, 0.15, 10.2, 1.2, GOLD, "the cache (st.cache_data, st.cache_resource): a shelf of ready-made\n"
        "results, refreshed when the file behind them changes", fs=8.8)
    box(ax, 11.4, 0.15, 10.2, 1.2, TEAL, "session state (st.session_state): this browser tab's notebook,\n"
        "keeping your upload and the strain you picked between reruns", fs=8.8)
    save(fig, "app_rerun.png")


# =============================================================================
# 2. The seven pages and what each one reads
# =============================================================================

def draw_app_map():
    fig, ax = canvas(11, 6.2, "The app's seven pages, and what each one reads",
                     "Pages only read. The buttons that write (the database build, the real-data fetch) run "
                     "the same scripts you would run by hand.")
    pages = [("Home", "headline numbers,\nhealth check"), ("Ranking", "every strain, best first;\nthe top-N question"),
             ("Strain page", "one strain: score,\nreasons, its graph corner"), ("Knowledge graph", "network, paths,\nlook-up, communities"),
             ("Integration", "Phase 3: signature,\nscoreboard, agreement"), ("Data", "library, your upload,\nreal data"),
             ("SQL console", "read-only SQL,\ncookbook recipes")]
    sources = [("artifacts/model/", "ranking, scoreboard,\nmodel + model card", GOLD),
               ("artifacts/graph/", "nodes, edges, explanations,\nhubs, communities", PURPLE),
               ("artifacts/integration/", "signature, scoreboards,\nfeature list", BLUE),
               ("strainscope.duckdb", "the database\n(read-only)", "#C9A227"),
               ("docs/QUERY_COOKBOOK.md", "the recipes", GREY)]
    reads = {"Home": [0, 1, 3], "Ranking": [0, 1], "Strain page": [0, 1], "Knowledge graph": [1],
             "Integration": [2], "Data": [0, 1, 2, 3], "SQL console": [3, 4]}
    py = {}
    for i, (name, note) in enumerate(pages):
        y = 10.0 - i * 1.42
        box(ax, 0.4, y, 6.6, 1.1, GREEN, "", fill=tint(GREEN, 0.86))
        ax.text(0.75, y + 0.72, name, fontsize=10, fontweight="bold", color=INK, va="center")
        ax.text(0.75, y + 0.32, note.replace("\n", " "), fontsize=7.8, color=SOFT, va="center")
        py[name] = y + 0.55
    sy = []
    for j, (name, note, colour) in enumerate(sources):
        y = 9.6 - j * 1.95
        box(ax, 14.6, y, 7.3, 1.4, colour)
        ax.text(14.95, y + 0.95, name, fontsize=9.6, fontweight="bold", color=INK, va="center", family="monospace")
        ax.text(14.95, y + 0.42, note.replace("\n", " "), fontsize=8, color=SOFT, va="center")
        sy.append(y + 0.7)
    # every line passes through the service layer, drawn as a band behind them
    ax.add_patch(FancyBboxPatch((9.3, 0.6), 3.4, 10.25, boxstyle="round,pad=0.02,rounding_size=0.2",
                                facecolor=tint(DARK_GREEN, 0.9), edgecolor=DARK_GREEN, lw=1.4, zorder=0))
    ax.text(11.0, 1.15, "src/strainscope/\nservice.py", ha="center", va="center", fontsize=8.4,
            family="monospace", color=DARK_GREEN, fontweight="bold")
    ax.text(11.0, 10.45, "the service layer", ha="center", va="center", fontsize=8.6, color=DARK_GREEN,
            fontweight="bold")
    for page, idx in reads.items():
        for j in idx:
            ax.plot([7.05, 14.55], [py[page], sy[j]], color=sources[j][2], lw=1.1, alpha=0.75, zorder=1)
    save(fig, "app_map.png")


# =============================================================================
# 3. The four guards around the SQL console
# =============================================================================

def draw_sql_guards():
    fig, ax = canvas(11, 5.2, "Four guards around the SQL console",
                     "Each ring stops one kind of accident. A query has to pass all four to reach the data.")
    cx, cy = 6.2, 4.4
    rings = [(4.2, RED, "4  at most 10,000 rows come back"),
             (3.3, GOLD, "3  stopped after 10 seconds"),
             (2.4, PURPLE, "2  file access off (and locked)"),
             (1.5, BLUE, "1  read-only")]
    for r, colour, _ in rings:
        ax.add_patch(plt.Circle((cx, cy), r, facecolor=tint(colour, 0.88), edgecolor=colour, lw=2))
    # the database at the centre: a small cylinder
    ax.add_patch(Rectangle((cx - 0.55, cy - 0.5), 1.1, 0.9, facecolor="#FFF3CD", edgecolor=GOLD, lw=1.6))
    for yy in (cy + 0.4, cy - 0.5):
        ax.add_patch(matplotlib.patches.Ellipse((cx, yy), 1.1, 0.34, facecolor="#FFF3CD", edgecolor=GOLD, lw=1.6))
    ax.text(cx, cy - 1.0, "the data", ha="center", fontsize=8.5, color=INK)
    stops = [("1  read-only", "DELETE FROM phenotype;\nCREATE TABLE ...", "refused: the console can look, never change", BLUE),
             ("2  file access off (and locked)", "SELECT * FROM read_csv('C:/secret.csv');\nCOPY ... TO 'out.csv';",
              "refused: it only sees tables in the database", PURPLE),
             ("3  a 10-second timer", "a join without ON that would\nrun for hours", "stopped, with a hint to add WHERE or LIMIT", GOLD),
             ("4  a 10,000-row cap", "SELECT * FROM kg_edges;  (8,000+ rows)", "fine; a million rows would be cut, and you're told", RED)]
    for i, (name, example, outcome, colour) in enumerate(stops):
        y = 7.45 - i * 2.0
        box(ax, 11.4, y - 0.15, 10.2, 1.75, colour, "")
        ax.text(11.75, y + 1.22, name, fontsize=10, fontweight="bold", color=INK, va="center")
        ax.text(11.75, y + 0.62, example, fontsize=7.9, family="monospace", color=INK, va="center", linespacing=1.3)
        ax.text(11.75, y + 0.05, outcome, fontsize=8.3, color=SOFT, style="italic", va="center")
    for r, colour, label in rings:                  # a numbered badge in each ring, matching the boxes
        ax.add_patch(plt.Circle((cx, cy + r - 0.45), 0.3, color=colour, zorder=3))
        ax.text(cx, cy + r - 0.45, label.split()[0], ha="center", va="center", fontsize=9, color="white",
                fontweight="bold", zorder=4)
    save(fig, "sql_guards.png")


# =============================================================================
# 4. The upload journey
# =============================================================================

def draw_upload_journey():
    fig, ax = canvas(11, 4.8, "Your strains, from a CSV file to an explained ranking",
                     "Nothing is written to disk on the way: the file lives in your browser tab's memory.")
    stages = [("your CSV file", "one row per strain:\nstrain_id, kingdom,\n31 genes\n(0, 1 or blank),\n20 compounds\n(numbers)", BLUE),
              ("the checks", "", GOLD),
              ("the saved model\n(Phase 4)", "a chance of being\neffective for each\nstrain, and where\nit would sit among\nthe library's 600", PURPLE),
              ("knowledge graph\n(Phase 5)", "the reasons:\nweapons and how\nthey work, flags,\nmissing weapons,\neach with its source", DARK_GREEN),
              ("back to you", "Ranking and\nStrain pages,\nplus two downloads:\nscores and reasons", TEAL)]
    widths, gap, x = [3.5, 5.4, 3.6, 3.6, 3.5], 0.5, 0.3
    for i, ((head, body, colour), w) in enumerate(zip(stages, widths)):
        box(ax, x, 1.0, w, 6.2, colour)
        ax.text(x + w / 2, 6.45, head, ha="center", va="center", fontsize=9.8, fontweight="bold", color=INK)
        if body:
            ax.text(x + w / 2, 3.7, body, ha="center", va="center", fontsize=8.5, color=INK, linespacing=1.45)
        if i == 1:
            checks_x = x
        if i < len(stages) - 1:
            arrow(ax, x + w + 0.03, 4.1, x + w + gap - 0.03, 4.1, colour=SOFT, lw=2)
        x += w + gap
    checks = [("✓", "columns match the template", DARK_GREEN), ("✓", "each strain_id is unique", DARK_GREEN),
              ("✓", "genes are 0, 1 or blank", DARK_GREEN), ("✓", "levels are numbers, not below 0", DARK_GREEN),
              ("!", "unknown kingdom: scored\nagainst all strains", GOLD), ("·", "blank = not measured,\nnever zero", SOFT)]
    for j, (mark, text, colour) in enumerate(checks):
        y = 5.55 - j * 0.78
        ax.text(checks_x + 0.4, y, mark, fontsize=11, fontweight="bold", color=colour, va="center", ha="center")
        ax.text(checks_x + 0.75, y, text, fontsize=8, color=INK, va="center", linespacing=1.15)
    ax.text(0.3, 0.35, "An error (red) stops the scoring and says which rows to fix; a warning (gold) explains "
            "what was assumed; a note (grey) is for information.", fontsize=8.6, color=SOFT)
    save(fig, "upload_journey.png")


# =============================================================================
# 5. Two ways of scoring the same strains (a result)
# =============================================================================

def draw_two_scores():
    from strainscope import service as sv
    if not sv.DB_PATH.exists():
        print("  figures/two_scores.png needs the database (python src/strainscope/harmonize.py); skipped")
        return
    import warnings
    example = sv.example_upload()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        check = sv.validate_upload(example)
        scores, _ = sv.score_upload(check.table)
    lib = sv.read_artifact("model/predictions.csv").set_index("strain_id")["probability"]
    scores = scores.merge(example[["strain_id", "copied_from"]], on="strain_id")
    scores["oof"] = scores["copied_from"].map(lib)
    scores = scores.sort_values("oof")
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    y = np.arange(len(scores))
    for yi, a, b in zip(y, scores["oof"], scores["probability"]):
        ax.plot([a, b], [yi, yi], color="#C7CDD6", lw=3, zorder=1)
    ax.scatter(scores["oof"], y, s=70, color=GOLD, zorder=2, label="in the ranking (out-of-fold: a model that never saw it)")
    ax.scatter(scores["probability"], y, s=70, color=DARK_GREEN, marker="D", zorder=3,
               label="as an upload (the final model, which learned from all 600)")
    ax.set_yticks(y, [f"{c} ({k})" for c, k in zip(scores["copied_from"], scores["kingdom"])], fontsize=8.5)
    ax.set_xlabel("predicted chance of being effective")
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlim(-0.03, 1.05)
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    biggest = (scores["probability"] - scores["oof"]).abs().max()
    ax.set_title(f"The same twelve strains, scored two ways (largest difference: {biggest * 100:.0f} percentage points)",
                 fontsize=11, loc="left", color=INK)
    fig.text(0.99, -0.01, "StrainScope: SIMULATED data", ha="right", va="top", fontsize=7, color=GREY, style="italic")
    save(fig, "two_scores.png")


if __name__ == "__main__":
    draw_rerun()
    draw_app_map()
    draw_sql_guards()
    draw_upload_journey()
    draw_two_scores()
