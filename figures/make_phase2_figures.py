"""
make_phase2_figures.py — the teaching figures for Phase 2 (cleaning & QC).
==========================================================================
Reads BOTH the raw and the cleaned tables, so every figure is honest
before-vs-after evidence of what cleaning did. Also draws a small schematic of
the database. Writes:
  * static PNGs                  -> figures/*.png
  * one interactive comparison   -> docs/interactive/batch_before_after.html

Run (from the project root, venv active) AFTER harmonize.py:
    python figures/make_phase2_figures.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
FIG = ROOT / "figures"
INT = ROOT / "docs" / "interactive"
FIG.mkdir(exist_ok=True); INT.mkdir(parents=True, exist_ok=True)

BLUE, GREEN, GOLD, GREY, PURPLE, RED = ("#5B8DEF", "#4CAF7D", "#C9A227",
                                        "#8A94A6", "#9C6ADE", "#D9634C")
plt.rcParams.update({"figure.dpi": 130, "font.size": 10, "axes.grid": True,
                     "grid.alpha": 0.25})

raw_m = pd.read_csv(RAW / "metabolomics.csv").drop_duplicates("strain_id")
raw_p = pd.read_csv(RAW / "phenotype.csv").drop_duplicates("strain_id")
clean_m = pd.read_csv(PROCESSED / "metabolomics_clean.csv")
clean_p = pd.read_csv(PROCESSED / "phenotype_clean.csv")


def footnote(fig, text="StrainScope — SIMULATED data"):
    fig.text(0.99, 0.01, text, ha="right", va="bottom",
             fontsize=7, color=GREY, style="italic")


# =============================================================================
# 1. THE CLEANING LEDGER, AS A PICTURE — what changed, at a glance
# =============================================================================
steps = [("duplicates removed", "24 rows (8 × 3 tables)", 24, RED),
         ("text cells harmonised", "657 cells", 657, BLUE),
         ("impossible scores clipped", "3 cells", 3, RED),
         ("outlier cells capped", "41 cells", 41, GOLD),
         ("missing cells kept as NULL", "1,052 cells (documented)", 1052, GREY)]
fig, ax = plt.subplots(figsize=(9, 4.2))
labels = [s[0] for s in steps]; vals = [s[2] for s in steps]
bars = ax.barh(labels, vals, color=[s[3] for s in steps])
for bar, s in zip(bars, steps):
    ax.text(bar.get_width() * 1.02 + 5, bar.get_y() + bar.get_height() / 2,
            s[1], va="center", fontsize=9)
ax.set_xscale("log"); ax.set_xlabel("rows / cells affected (log scale)")
ax.invert_yaxis()
ax.set_title("The cleaning ledger, drawn: every change counted, nothing silent")
footnote(fig); fig.tight_layout(); fig.savefig(FIG / "cleaning_ledger.png"); plt.close(fig)

# =============================================================================
# 2. BATCH EFFECT: BEFORE vs AFTER — the drift, removed
# =============================================================================
batch_map = raw_p.set_index("strain_id")["batch_id"]
fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for ax, df, title in ((axes[0], raw_m, "BEFORE: batches drift"),
                      (axes[1], clean_m, "AFTER: batches agree")):
    b = df["strain_id"].map(batch_map)
    data = [df.loc[b == i, "surfactin"].dropna() for i in range(1, 7)]
    bp = ax.boxplot(data, tick_labels=[f"b{i}" for i in range(1, 7)],
                    patch_artist=True, showfliers=False)
    for patch in bp["boxes"]:
        patch.set_facecolor("#E8F0FE")
    meds = [d.median() for d in data]
    ax.plot(range(1, 7), meds, color=RED, marker="o", lw=1.2, label="batch median")
    ax.set_title(title); ax.legend(fontsize=8)
axes[0].set_ylabel("surfactin abundance")
fig.suptitle("Median-scaling removes the lab drift and keeps the biology", fontsize=12)
footnote(fig); fig.tight_layout(); fig.savefig(FIG / "batch_before_after.png"); plt.close(fig)

# =============================================================================
# 3. OUTLIERS: what was capped — and what honestly can't be caught
# =============================================================================
fig, ax = plt.subplots(figsize=(8, 4.4))
v_raw = raw_m["HCN"].dropna()
ceiling = 3 * v_raw.quantile(0.95)
bins = np.logspace(np.log10(max(v_raw.min(), 0.05)), np.log10(v_raw.max() * 1.1), 50)
ax.hist(v_raw[v_raw <= ceiling], bins=bins, color=BLUE, alpha=0.75,
        label="kept (trace hump + producer hump)")
ax.hist(v_raw[v_raw > ceiling], bins=bins, color=RED, alpha=0.9,
        label=f"capped (> 3×p95 = {ceiling:.0f})")
ax.axvline(ceiling, color=RED, ls="--", lw=1.2)
ax.set_xscale("log")
ax.set_xlabel("HCN abundance (log scale)"); ax.set_ylabel("strains")
ax.set_title("Two humps are biology; the far tail is measurement error")
ax.legend(fontsize=8)
footnote(fig); fig.tight_layout(); fig.savefig(FIG / "outliers_capped.png"); plt.close(fig)

# =============================================================================
# 4. TEXT HARMONISATION — many spellings in, one voice out
# =============================================================================
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
before = raw_p["genus"].value_counts()
after = clean_p["genus"].value_counts()
axes[0].barh(before.index[::-1], before.values[::-1], color=GREY)
axes[0].set_title(f"BEFORE: {len(before)} distinct spellings")
axes[0].tick_params(axis="y", labelsize=7)
axes[1].barh(after.index[::-1], after.values[::-1], color=GREEN)
axes[1].set_title(f"AFTER: {len(after)} clean genera")
axes[1].tick_params(axis="y", labelsize=8)
for ax in axes:
    ax.set_xlabel("strains")
fig.suptitle("One agreed spelling per real-world thing", fontsize=12)
footnote(fig); fig.tight_layout(); fig.savefig(FIG / "text_harmonization.png"); plt.close(fig)

# =============================================================================
# 5. THE DATABASE, AS A PICTURE — what now lives in strainscope.duckdb
# =============================================================================
fig, ax = plt.subplots(figsize=(10, 4.6))
ax.set_xlim(0, 10); ax.set_ylim(0, 4.6); ax.axis("off")

def box(x, y, w, h, colour, title, sub):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.07",
                                facecolor=colour, edgecolor="#5f6b7a", lw=1.1))
    ax.text(x + w / 2, y + h - 0.3, title, ha="center", fontsize=9.5,
            fontweight="bold")
    ax.text(x + w / 2, y + h / 2 - 0.22, sub, ha="center", fontsize=8)

ax.text(5, 4.3, "strainscope.duckdb — one file, every table, queryable with SQL",
        ha="center", fontsize=12, fontweight="bold")
box(0.4, 2.4, 2.9, 1.3, "#E8F0FE", "genomics",
    "600 strains × 31 genes\n(clean, NULLs kept)")
box(3.6, 2.4, 2.9, 1.3, "#E8F0FE", "metabolomics",
    "600 strains × 20 compounds\n(capped, batch-corrected)")
box(6.8, 2.4, 2.9, 1.3, "#E8F0FE", "phenotype",
    "600 strains: kingdom, genus,\nscores (clipped), metadata")
box(0.4, 0.5, 2.9, 1.3, "#E6F4EA", "real_strains",
    "100 real BacDive strains")
box(3.6, 0.5, 2.9, 1.3, "#E6F4EA", "real_compounds (+kegg)",
    "verified chemistry (PubChem)\n+ KEGG compound IDs")
box(6.8, 0.5, 2.9, 1.3, "#E6F4EA", "real_compound_pathways",
    "curated compound→pathway\nedges (KEGG, attributed)")
ax.text(5, 2.12, "synthetic (cleaned this phase)", ha="center", fontsize=8,
        color="#5f6b7a", style="italic")
ax.text(5, 0.22, "real (auto-loaded from data/processed/real/ — future sources join automatically)",
        ha="center", fontsize=8, color="#5f6b7a", style="italic")
footnote(fig, "StrainScope — schematic")
fig.tight_layout(); fig.savefig(FIG / "database_schema.png"); plt.close(fig)

# =============================================================================
# 6. INTERACTIVE — drag between before and after batch views
# =============================================================================
try:
    import plotly.graph_objects as go
    b_raw = raw_m["strain_id"].map(batch_map)
    b_clean = clean_m["strain_id"].map(batch_map)
    figi = go.Figure()
    for i in range(1, 7):
        figi.add_trace(go.Box(y=raw_m.loc[b_raw == i, "surfactin"],
                              name=f"batch {i}", marker_color="#8A94A6",
                              visible=True, boxpoints=False))
    for i in range(1, 7):
        figi.add_trace(go.Box(y=clean_m.loc[b_clean == i, "surfactin"],
                              name=f"batch {i}", marker_color="#4CAF7D",
                              visible=False, boxpoints=False))
    figi.update_layout(
        template="plotly_white", height=520, showlegend=False,
        title="Batch effect, before vs after — use the buttons",
        yaxis_title="surfactin abundance",
        updatemenus=[dict(type="buttons", x=0.5, y=1.15, xanchor="center",
                          buttons=[
                              dict(label="BEFORE (raw)", method="update",
                                   args=[{"visible": [True] * 6 + [False] * 6}]),
                              dict(label="AFTER (clean)", method="update",
                                   args=[{"visible": [False] * 6 + [True] * 6}]),
                          ])])
    figi.write_html(INT / "batch_before_after.html",
                    include_plotlyjs=True, full_html=True)
    print("  drew docs/interactive/batch_before_after.html (interactive)")
except ImportError:
    print("  plotly missing — interactive skipped")

print("Wrote Phase 2 figures to figures/*.png")
