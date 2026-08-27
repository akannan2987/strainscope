"""
make_phase2b_figures.py — figures for the real-data ingestion phase.
====================================================================
Two kinds of figure, honestly separated:

1. A CONCEPT ILLUSTRATION (always drawn, needs no data): the ingestion
   framework — one "socket", many source "plugs", the evidence locker, the
   provenance log, the tidy tables.

2. DATA FIGURES (drawn only AFTER you run fetch_real.py, from the tables it
   produced): real compound weights, pathway counts, real strains per genus,
   plus an interactive chart. If you haven't fetched yet, the script tells you
   and skips them — it never invents data.

Run (from the project root, venv active):
    python figures/make_phase2b_figures.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data" / "processed" / "real"
FIG = ROOT / "figures"
INT = ROOT / "docs" / "interactive"
FIG.mkdir(exist_ok=True); INT.mkdir(parents=True, exist_ok=True)

BLUE, GREEN, GOLD, GREY, PURPLE = "#5B8DEF", "#4CAF7D", "#C9A227", "#8A94A6", "#9C6ADE"
plt.rcParams.update({"figure.dpi": 130, "font.size": 10})


def footnote(fig, text="StrainScope"):
    fig.text(0.99, 0.01, text, ha="right", va="bottom",
             fontsize=7, color=GREY, style="italic")


# =============================================================================
# 1. CONCEPT ILLUSTRATION — the ingestion framework (always drawn)
# =============================================================================
def draw_framework():
    fig, ax = plt.subplots(figsize=(11, 5.2))
    ax.set_xlim(0, 11); ax.set_ylim(0, 5.2); ax.axis("off")

    def box(x, y, w, h, colour, title, sub="", fs=9):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                                    facecolor=colour, edgecolor="#5f6b7a", lw=1.2))
        ax.text(x + w/2, y + h - 0.32, title, ha="center", va="center",
                fontsize=fs, fontweight="bold")
        if sub:
            ax.text(x + w/2, y + h/2 - 0.22, sub, ha="center", va="center",
                    fontsize=fs - 1.5)

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=14, color="#5f6b7a", lw=1.4))

    # The plugs (sources)
    box(0.3, 3.9, 2.4, 1.0, "#E8F0FE", "BacDive", "real strains (DSMZ)")
    box(0.3, 2.5, 2.4, 1.0, "#E8F0FE", "PubChem", "real chemistry (NIH)")
    box(0.3, 1.1, 2.4, 1.0, "#E8F0FE", "KEGG", "real pathways (academic)")
    ax.text(1.5, 0.55, "…more plugs later:\nNCBI · Metabolomics WB · MGnify · ENA",
            ha="center", fontsize=7.5, color="#5f6b7a")

    # The socket (contract)
    box(3.6, 2.1, 2.5, 1.9, "#F3E8FD", "The socket",
        "one contract:\nprobe → fetch → tidy", fs=10)
    for y in (4.4, 3.0, 1.6):
        arrow(2.75, y, 3.6, 3.05)

    # Evidence locker + provenance log
    box(6.9, 3.2, 3.6, 1.3, "#FFF3CD", "Evidence locker",
        "data/raw/real/<source>/\nraw responses, untouched")
    box(6.9, 1.7, 3.6, 1.1, "#FFF3CD", "Provenance log",
        "fetch_log.csv — who asked what,\nwhen, and how much came back")
    arrow(6.15, 3.3, 6.9, 3.8)
    arrow(6.15, 2.8, 6.9, 2.25)

    # Tidy tables
    box(6.9, 0.2, 3.6, 1.1, "#EAECEF", "Tidy tables",
        "data/processed/real/*.csv\n→ join the database next phase")
    # tidy() reads the EVIDENCE LOCKER (not the log) — arc the arrow around.
    ax.add_patch(FancyArrowPatch((6.85, 3.5), (6.85, 0.9),
                                 connectionstyle="arc3,rad=0.35",
                                 arrowstyle="-|>", mutation_scale=14,
                                 color="#5f6b7a", lw=1.4))
    ax.text(5.9, 2.1, "tidy() reads\nthe raw files", ha="center", fontsize=7.5,
            color="#5f6b7a", style="italic")

    ax.set_title("Real-data ingestion: many sources, one socket, a full paper trail",
                 fontsize=12)
    footnote(fig, "StrainScope — concept illustration")
    fig.tight_layout(); fig.savefig(FIG / "ingestion_framework.png"); plt.close(fig)
    print("  drew figures/ingestion_framework.png (concept illustration)")


# =============================================================================
# 2. DATA FIGURES — only from tables YOUR fetch produced (never invented)
# =============================================================================
def draw_data_figures():
    try:
        import pandas as pd
    except ImportError:
        print("  pandas missing — install requirements first"); return

    compounds_p = REAL / "real_compounds.csv"
    edges_p = REAL / "real_compound_pathways.csv"
    strains_p = REAL / "real_strains.csv"

    if not compounds_p.exists() and not strains_p.exists():
        print("  (no real tables yet — run `python src/strainscope/fetch_real.py`"
              " first; data figures will then appear here)")
        return

    if compounds_p.exists():
        comp = pd.read_csv(compounds_p)
        found = comp[comp["status"] == "found"].copy()
        if len(found):
            found["molecular_weight"] = pd.to_numeric(found["molecular_weight"],
                                                      errors="coerce")
            found = found.dropna(subset=["molecular_weight"]).sort_values("molecular_weight")
            fig, ax = plt.subplots(figsize=(8, 4.5))
            ax.barh(found["metabolite"], found["molecular_weight"], color=GREEN)
            ax.set_xlabel("molecular weight (g/mol) — real values from PubChem")
            ax.set_title("Our metabolites are real molecules: verified weights from PubChem")
            footnote(fig, "data: PubChem (NIH)")
            fig.tight_layout(); fig.savefig(FIG / "real_compound_weights.png"); plt.close(fig)
            print(f"  drew figures/real_compound_weights.png ({len(found)} compounds)")

    if edges_p.exists():
        edges = pd.read_csv(edges_p)
        if len(edges):
            per = edges.groupby("metabolite").size().sort_values()
            fig, ax = plt.subplots(figsize=(8, 4.2))
            ax.barh(per.index, per.values, color=PURPLE)
            ax.set_xlabel("number of KEGG pathways the compound appears in")
            ax.set_title("Real pathway context: where our compounds sit in biology")
            footnote(fig, "data: KEGG (academic use)")
            fig.tight_layout(); fig.savefig(FIG / "real_pathways_per_compound.png"); plt.close(fig)
            print(f"  drew figures/real_pathways_per_compound.png ({len(per)} compounds)")

    if strains_p.exists():
        strains = pd.read_csv(strains_p)
        if len(strains):
            per = strains["genus"].value_counts()
            fig, ax = plt.subplots(figsize=(7, 4))
            ax.bar(per.index, per.values, color=BLUE)
            for i, v in enumerate(per.values):
                ax.text(i, v + 0.3, str(v), ha="center", fontsize=9)
            ax.set_ylabel("real strains fetched")
            ax.set_title("Real strains from BacDive, by genus (your fetch)")
            footnote(fig, "data: BacDive (DSMZ)")
            fig.tight_layout(); fig.savefig(FIG / "real_strains_per_genus.png"); plt.close(fig)
            print(f"  drew figures/real_strains_per_genus.png ({len(strains)} strains)")

    # Interactive: weight vs pathway-count, hover for details.
    if compounds_p.exists() and edges_p.exists():
        try:
            import plotly.express as px
            comp = pd.read_csv(compounds_p)
            edges = pd.read_csv(edges_p)
            found = comp[comp["status"] == "found"].copy()
            found["molecular_weight"] = pd.to_numeric(found["molecular_weight"],
                                                      errors="coerce")
            counts = edges.groupby("metabolite").size().rename("n_pathways")
            merged = found.merge(counts, on="metabolite", how="left").fillna({"n_pathways": 0})
            if len(merged):
                figi = px.scatter(
                    merged, x="molecular_weight", y="n_pathways", text="metabolite",
                    hover_data={"molecular_formula": True, "cid": True,
                                "iupac_name": True},
                    labels={"molecular_weight": "molecular weight (g/mol, PubChem)",
                            "n_pathways": "KEGG pathways"},
                    title="Real chemistry meets real pathways — hover any compound")
                figi.update_traces(textposition="top center",
                                   marker=dict(size=12, color=GREEN))
                figi.update_layout(template="plotly_white", height=520)
                figi.write_html(INT / "real_compounds.html",
                                include_plotlyjs=True, full_html=True)
                print("  drew docs/interactive/real_compounds.html (interactive)")
        except ImportError:
            print("  plotly missing — interactive skipped")


if __name__ == "__main__":
    print("Phase 2b figures:")
    draw_framework()
    draw_data_figures()
