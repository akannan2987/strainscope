"""
make_phase2c_figures.py — figures for Tier 2 real sources (+ the secrets lesson).
=================================================================================
1. A CONCEPT ILLUSTRATION (always drawn): the two homes of a secret — how an
   API key travels from shell/.env into a request header without ever touching
   Git.
2. DATA FIGURES (only after `fetch_real.py --source ncbi_datasets` /
   `--source metabolomics_wb`, from YOUR fetched tables — never invented):
   real genome sizes by kingdom, GC-vs-size interactive, RefMet classes,
   studies per keyword.

Run:  python figures/make_phase2c_figures.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data" / "processed" / "real"
FIG = ROOT / "figures"
INT = ROOT / "docs" / "interactive"
FIG.mkdir(exist_ok=True); INT.mkdir(parents=True, exist_ok=True)

BLUE, GREEN, GOLD, GREY, PURPLE, RED = ("#5B8DEF", "#4CAF7D", "#C9A227",
                                        "#8A94A6", "#9C6ADE", "#D9634C")
KINGDOM_COLOURS = {"Bacteria": BLUE, "Fungi": GREEN, "Yeast": GOLD, "Oomycete": PURPLE}
plt.rcParams.update({"figure.dpi": 130, "font.size": 10, "axes.grid": True,
                     "grid.alpha": 0.25})


def footnote(fig, text):
    fig.text(0.99, 0.01, text, ha="right", va="bottom",
             fontsize=7, color=GREY, style="italic")


# =============================================================================
# 1. THE TWO HOMES OF A SECRET (always drawn)
# =============================================================================
def draw_secret_homes():
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.set_xlim(0, 11); ax.set_ylim(0, 5); ax.axis("off")

    def box(x, y, w, h, colour, title, sub="", fs=9, dashed=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                                    facecolor=colour, edgecolor="#5f6b7a",
                                    lw=1.2, linestyle="--" if dashed else "-"))
        ax.text(x + w/2, y + h - 0.32, title, ha="center", fontsize=fs,
                fontweight="bold")
        if sub:
            ax.text(x + w/2, y + h/2 - 0.22, sub, ha="center", fontsize=fs - 1.5)

    def arrow(x1, y1, x2, y2, label=""):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=14, color="#5f6b7a", lw=1.4))
        if label:
            ax.text((x1 + x2)/2, (y1 + y2)/2 + 0.16, label, ha="center",
                    fontsize=7.5, color="#5f6b7a", style="italic")

    box(0.3, 3.4, 3.0, 1.2, "#E8F0FE", "Home 1 — the shell",
        "export NCBI_API_KEY=…\n(this session only)")
    box(0.3, 1.6, 3.0, 1.2, "#FFF3CD", "Home 2 — the .env file",
        "NCBI_API_KEY=…  (one line;\ngit-ignored + gate-guarded)")
    box(4.2, 2.4, 2.7, 1.4, "#F3E8FD", "The environment",
        "load_env() fills gaps;\nthe shell always wins", fs=9.5)
    box(7.8, 2.4, 2.9, 1.4, "#E6F4EA", "The request header",
        'api-key: ****\nsent only to NCBI, per call')
    box(4.2, 0.3, 2.7, 1.1, "#F5F5F5", "The repository",
        "the key NEVER appears here", dashed=True)

    arrow(3.3, 4.0, 4.25, 3.35, "already set → wins")
    arrow(3.3, 2.2, 4.25, 2.75, "read at startup")
    arrow(6.9, 3.1, 7.8, 3.1, "adapter attaches it")
    ax.add_patch(FancyArrowPatch((5.55, 2.4), (5.55, 1.4), arrowstyle="-|>",
                                 mutation_scale=14, color=RED, lw=1.6))
    ax.text(5.9, 1.85, "✗ blocked:\n.gitignore + safety gate", ha="left",
            fontsize=7.5, color=RED)

    ax.set_title("One key, two safe homes — and one place it must never appear",
                 fontsize=12)
    footnote(fig, "StrainScope — concept illustration")
    fig.tight_layout(); fig.savefig(FIG / "secret_homes.png"); plt.close(fig)
    print("  drew figures/secret_homes.png (concept illustration)")


# =============================================================================
# 2. DATA FIGURES — only from YOUR fetched tables
# =============================================================================
def draw_data_figures():
    import pandas as pd
    genomes_p = REAL / "real_genomes.csv"
    refmet_p = REAL / "real_refmet.csv"
    studies_p = REAL / "real_mw_studies.csv"
    if not genomes_p.exists() and not refmet_p.exists():
        print("  (no Tier-2 tables yet — run `python src/strainscope/fetch_real.py"
              " --source ncbi_datasets` and `--source metabolomics_wb` first)")
        return

    if genomes_p.exists():
        g = pd.read_csv(genomes_p)
        g["genome_length_bp"] = pd.to_numeric(g["genome_length_bp"], errors="coerce")
        g = g.dropna(subset=["genome_length_bp"])
        if len(g):
            fig, ax = plt.subplots(figsize=(8.5, 4.4))
            for i, k in enumerate([k for k in KINGDOM_COLOURS if k in set(g["kingdom"])]):
                vals = g.loc[g["kingdom"] == k, "genome_length_bp"] / 1e6
                x = np.random.default_rng(1).normal(i, 0.06, len(vals))
                ax.scatter(x, vals, s=22, alpha=0.7, color=KINGDOM_COLOURS[k], label=k)
            ax.set_yscale("log")
            ax.set_xticks(range(len([k for k in KINGDOM_COLOURS if k in set(g['kingdom'])])))
            ax.set_xticklabels([k for k in KINGDOM_COLOURS if k in set(g["kingdom"])])
            ax.set_ylabel("genome length (million letters, log scale)")
            ax.set_title("Real genomes, real biology: fungal genomes dwarf bacterial ones")
            footnote(fig, "data: NCBI Datasets")
            fig.tight_layout(); fig.savefig(FIG / "real_genome_sizes.png"); plt.close(fig)
            print(f"  drew figures/real_genome_sizes.png ({len(g)} genomes)")

            try:
                import plotly.express as px
                figi = px.scatter(
                    g.assign(Mb=g["genome_length_bp"] / 1e6),
                    x="Mb", y="gc_percent", color="kingdom",
                    color_discrete_map=KINGDOM_COLOURS, log_x=True,
                    hover_data={"organism": True, "accession": True,
                                "assembly_level": True},
                    labels={"Mb": "genome length (Mb, log)",
                            "gc_percent": "GC content (%)"},
                    title="Real genomes — hover any point (NCBI Datasets)")
                figi.update_layout(template="plotly_white", height=520)
                figi.write_html(INT / "real_genomes.html",
                                include_plotlyjs=True, full_html=True)
                print("  drew docs/interactive/real_genomes.html (interactive)")
            except ImportError:
                pass

    if refmet_p.exists():
        r = pd.read_csv(refmet_p)
        found = r[r["status"] == "found"]
        if len(found):
            per = found["main_class"].fillna("—").value_counts()
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.barh(per.index[::-1], per.values[::-1], color=GREEN)
            ax.set_xlabel("of our metabolites in this RefMet class")
            ax.set_title("Where our compounds sit on chemistry's shelves (RefMet)")
            footnote(fig, "data: Metabolomics Workbench RefMet")
            fig.tight_layout(); fig.savefig(FIG / "real_refmet_classes.png"); plt.close(fig)
            print(f"  drew figures/real_refmet_classes.png ({len(found)} classified)")

    if studies_p.exists():
        s = pd.read_csv(studies_p)
        if len(s):
            per = s["keyword"].value_counts()
            fig, ax = plt.subplots(figsize=(7, 3.8))
            ax.bar(per.index, per.values, color=GOLD)
            for i, v in enumerate(per.values):
                ax.text(i, v + 0.3, str(v), ha="center", fontsize=9)
            ax.set_ylabel("real studies fetched")
            ax.set_title("Real labs measure this chemistry: studies by search word")
            footnote(fig, "data: Metabolomics Workbench")
            fig.tight_layout(); fig.savefig(FIG / "real_mw_studies.png"); plt.close(fig)
            print(f"  drew figures/real_mw_studies.png ({len(s)} studies)")


if __name__ == "__main__":
    print("Phase 2c figures:")
    draw_secret_homes()
    draw_data_figures()
