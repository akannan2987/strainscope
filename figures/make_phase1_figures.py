"""
make_phase1_figures.py — build the teaching figures for Phase 1.
================================================================
Reads the three raw CSVs from data/raw/ and writes:
  * static PNG figures            -> figures/*.png
  * one interactive Plotly chart  -> docs/interactive/signal_scatter.html

Run it (from the project root, venv active) AFTER generate_data.py:
    python figures/make_phase1_figures.py

Every figure carries a "SIMULATED DATA" note, because honesty about the data is
part of the project.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")                     # render to files, no screen needed
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import plotly.express as px

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FIG = ROOT / "figures"
INT = ROOT / "docs" / "interactive"
FIG.mkdir(exist_ok=True); INT.mkdir(parents=True, exist_ok=True)

# --- a soft, consistent palette (matches the project's diagrams) -------------
BLUE, GREEN, GOLD, GREY, PURPLE = "#5B8DEF", "#4CAF7D", "#C9A227", "#8A94A6", "#9C6ADE"
plt.rcParams.update({"figure.dpi": 130, "font.size": 10, "axes.grid": True,
                     "grid.alpha": 0.25})

SIGNAL_GENES = ["phlD","prnD","phzE","hcnA","srfAA","ituA","fenA","chiA","pvdA"]
PGP_GENES = ["acdS","nifH","gcd"]
HK_GENES = ["recA","gyrB","rpoB"]
NOISE_GENES = ["accA","accB","accC","accD","accE","accF"]
SIGNAL_METAB = ["DAPG","pyrrolnitrin","phenazine","HCN","surfactin","iturin","fengycin","pyoverdine"]
NOISE_METAB = [f"bg_metabolite_{i}" for i in range(1,7)]

geno = pd.read_csv(RAW/"genomics.csv").drop_duplicates("strain_id")
metab = pd.read_csv(RAW/"metabolomics.csv").drop_duplicates("strain_id")
phen = pd.read_csv(RAW/"phenotype.csv").drop_duplicates("strain_id")
df = phen.merge(geno, on="strain_id").merge(metab, on="strain_id")

def footnote(fig):
    fig.text(0.99, 0.01, "StrainScope — SIMULATED data", ha="right", va="bottom",
             fontsize=7, color=GREY, style="italic")

# =============================================================================
# 1. CLASS BALANCE — how rare are the effective strains?
# =============================================================================
fig, ax = plt.subplots(figsize=(6,4))
counts = phen["is_effective"].value_counts().sort_index()
bars = ax.bar(["Not effective\n(< 65% suppression)", "Effective\n(≥ 65% suppression)"],
              counts.values, color=[GREY, GREEN])
for b,v in zip(bars, counts.values):
    ax.text(b.get_x()+b.get_width()/2, v+4, f"{v}\n({v/counts.sum()*100:.1f}%)",
            ha="center", va="bottom", fontsize=9)
ax.set_ylabel("number of strains"); ax.set_ylim(0, counts.max()*1.18)
ax.set_title("Class balance: the effective strains are the rare minority")
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"class_balance.png"); plt.close(fig)

# =============================================================================
# 2. DATASET OVERVIEW — three layers, same strains, side by side (first 40)
# =============================================================================
n = 40
sub = df.head(n)
fig, axes = plt.subplots(1, 3, figsize=(12,5), gridspec_kw={"width_ratios":[1.1,1.3,0.5]})
# genomics: binary heatmap
g = sub[SIGNAL_GENES+PGP_GENES+HK_GENES+NOISE_GENES].to_numpy()
axes[0].imshow(g, aspect="auto", cmap=ListedColormap(["#EEF1F5", BLUE]))
axes[0].set_title("Genomics\n(gene present = blue)")
axes[0].set_xticks(range(g.shape[1]))
axes[0].set_xticklabels(SIGNAL_GENES+PGP_GENES+HK_GENES+NOISE_GENES, rotation=90, fontsize=6)
axes[0].set_ylabel(f"first {n} strains")
# metabolomics: continuous heatmap (log)
m = np.log1p(sub[SIGNAL_METAB+NOISE_METAB].to_numpy())
im = axes[1].imshow(m, aspect="auto", cmap="YlGnBu")
axes[1].set_title("Metabolomics\n(abundance, log scale)")
axes[1].set_xticks(range(m.shape[1]))
axes[1].set_xticklabels(SIGNAL_METAB+NOISE_METAB, rotation=90, fontsize=6)
axes[1].set_yticks([])
# phenotype: suppression score bar
axes[2].barh(range(n), sub["suppression_score"].to_numpy(),
             color=np.where(sub["is_effective"]==1, GREEN, GREY))
axes[2].axvline(65, color="red", lw=1, ls="--")
axes[2].set_title("Phenotype\n(suppression %)"); axes[2].set_yticks([]); axes[2].invert_yaxis()
axes[2].set_xlim(0,100)
fig.suptitle("One dataset, three views of the same strains", fontsize=12)
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"dataset_overview.png"); plt.close(fig)

# =============================================================================
# 3. THE SIGNAL — a producing metabolite vs the outcome
# =============================================================================
fig, ax = plt.subplots(figsize=(6.5,4.5))
for lab, colour, mask in [("Not effective", GREY, df["is_effective"]==0),
                          ("Effective", GREEN, df["is_effective"]==1)]:
    ax.scatter(df.loc[mask,"iturin"], df.loc[mask,"suppression_score"],
               s=16, alpha=0.6, color=colour, label=lab)
ax.axhline(65, color="red", ls="--", lw=1, label="effective threshold (65%)")
ax.set_xlabel("iturin abundance (an antifungal lipopeptide)")
ax.set_ylabel("disease suppression (%)")
ax.set_title("Hidden signal: strains making more iturin tend to suppress more")
ax.legend(fontsize=8)
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"signal_scatter.png"); plt.close(fig)

# =============================================================================
# 4. MISSINGNESS — where the metabolite readings dropped out
# =============================================================================
fig, ax = plt.subplots(figsize=(7,4.5))
miss = metab[SIGNAL_METAB+NOISE_METAB].head(80).isna().to_numpy()
ax.imshow(miss, aspect="auto", cmap=ListedColormap(["#EEF1F5", GOLD]))
ax.set_title(f"Missing metabolite readings (gold = missing) — {metab[SIGNAL_METAB+NOISE_METAB].isna().sum().sum()} cells total")
ax.set_xticks(range(len(SIGNAL_METAB+NOISE_METAB)))
ax.set_xticklabels(SIGNAL_METAB+NOISE_METAB, rotation=90, fontsize=7)
ax.set_ylabel("first 80 strains")
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"missingness.png"); plt.close(fig)

# =============================================================================
# 5. GENE PREVALENCE — signal vs housekeeping vs noise (variance matters)
# =============================================================================
fig, ax = plt.subplots(figsize=(9,4))
order = SIGNAL_GENES+PGP_GENES+HK_GENES+NOISE_GENES
prev = geno[order].mean().mul(100)
colours = ([GREEN]*len(SIGNAL_GENES) + [BLUE]*len(PGP_GENES)
           + [GREY]*len(HK_GENES) + [PURPLE]*len(NOISE_GENES))
ax.bar(order, prev.values, color=colours)
ax.set_ylabel("% of strains carrying the gene"); ax.set_ylim(0,105)
ax.set_xticks(range(len(order))); ax.set_xticklabels(order, rotation=90, fontsize=8)
handles = [plt.Rectangle((0,0),1,1,color=c) for c in [GREEN,BLUE,GREY,PURPLE]]
ax.legend(handles, ["suppression signal","growth signal","housekeeping (~all strains)","accessory noise"],
          fontsize=8, loc="upper right")
ax.set_title("Not all genes are informative: housekeeping genes are in ~every strain")
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"gene_prevalence.png"); plt.close(fig)

# =============================================================================
# 6. METABOLITE-OUTCOME CORRELATION — which metabolites carry the signal?
# =============================================================================
fig, ax = plt.subplots(figsize=(8,4))
cors = {m: df[[m,"suppression_score"]].corr().iloc[0,1] for m in SIGNAL_METAB+NOISE_METAB}
cs = pd.Series(cors)
colours = [GREEN if m in SIGNAL_METAB else PURPLE for m in cs.index]
ax.bar(cs.index, cs.values, color=colours)
ax.axhline(0, color="black", lw=0.8)
ax.set_ylabel("correlation with suppression %")
ax.set_xticks(range(len(cs))); ax.set_xticklabels(cs.index, rotation=90, fontsize=8)
handles = [plt.Rectangle((0,0),1,1,color=c) for c in [GREEN,PURPLE]]
ax.legend(handles, ["signal metabolite","background noise"], fontsize=8)
ax.set_title("The signal metabolites correlate with the outcome; the noise ones don't")
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"metabolite_correlation.png"); plt.close(fig)

# =============================================================================
# 7. BATCH EFFECT — systematic drift the cleaning phase must correct
# =============================================================================
fig, ax = plt.subplots(figsize=(7,4))
data = [df.loc[df["batch_id"]==b, "surfactin"].dropna().to_numpy() for b in range(1,7)]
bp = ax.boxplot(data, tick_labels=[f"batch {b}" for b in range(1,7)], patch_artist=True)
for patch in bp["boxes"]: patch.set_facecolor("#E8F0FE")
ax.set_ylabel("surfactin abundance"); ax.set_title("Batch effect: the same measurement drifts between lab batches")
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"batch_effect.png"); plt.close(fig)

# =============================================================================
# 8. INTERACTIVE — hover any strain to see its details (Plotly -> HTML)
# =============================================================================
plot_df = df.copy()
plot_df["status"] = np.where(plot_df["is_effective"]==1, "Effective", "Not effective")
plot_df["signal_genes_present"] = geno.set_index("strain_id").loc[plot_df["strain_id"], SIGNAL_GENES].sum(axis=1).values
figi = px.scatter(
    plot_df, x="iturin", y="suppression_score", color="status",
    color_discrete_map={"Effective": GREEN, "Not effective": GREY},
    hover_data={"strain_id":True, "genus":True, "signal_genes_present":True,
                "surfactin":":.1f", "DAPG":":.1f", "iturin":":.1f"},
    labels={"iturin":"iturin abundance", "suppression_score":"disease suppression (%)"},
    title="StrainScope (SIMULATED): hover any strain to see its molecular profile")
figi.add_hline(y=65, line_dash="dash", line_color="red",
               annotation_text="effective threshold (65%)")
figi.update_layout(template="plotly_white", height=520)
figi.write_html(INT/"signal_scatter.html", include_plotlyjs=True, full_html=True)

print("Wrote figures to figures/*.png and docs/interactive/signal_scatter.html")
print("Correlation check (should be positive for signal metabolites):")
print(cs.round(2).to_string())
