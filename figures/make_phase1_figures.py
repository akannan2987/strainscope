"""
make_phase1_figures.py — build the teaching figures for Phase 1 (multi-kingdom).
================================================================================
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
KINGDOM_COLOURS = {"Bacteria": "#5B8DEF", "Fungi": "#4CAF7D",
                   "Yeast": "#C9A227", "Oomycete": "#9C6ADE"}
plt.rcParams.update({"figure.dpi": 130, "font.size": 10, "axes.grid": True,
                     "grid.alpha": 0.25})

SIGNAL_GENES = ["phlD","prnD","phzE","hcnA","srfAA","ituA","fenA","pvdA","chiA",
                "glcA","ech42","prb1","sixPP","dtxS","beaS","olpA","kilT","sidA"]
PGP_GENES = ["acdS","nifH","gcd","iaaM"]
HK_GENES = ["ssu_rRNA","ef1a","rpb1"]
NOISE_GENES = ["accA","accB","accC","accD","accE","accF"]
SIGNAL_METAB = ["DAPG","pyrrolnitrin","phenazine","HCN","surfactin","iturin",
                "fengycin","pyoverdine","six_PP","destruxin","beauvericin",
                "oligandrin","killer_toxin","yeast_siderophore"]
NOISE_METAB = [f"bg_metabolite_{i}" for i in range(1,7)]
KINGDOM_ORDER = ["Bacteria","Fungi","Yeast","Oomycete"]

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
# 2. KINGDOM MIX + effective rate per kingdom
# =============================================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11,4))
kc = phen["kingdom"].value_counts().reindex(KINGDOM_ORDER)
ax1.bar(kc.index, kc.values, color=[KINGDOM_COLOURS[k] for k in kc.index])
for i,v in enumerate(kc.values): ax1.text(i, v+3, str(v), ha="center", fontsize=9)
ax1.set_ylabel("number of strains"); ax1.set_title("How many strains of each kingdom")
eff = phen.groupby("kingdom")["is_effective"].mean().mul(100).reindex(KINGDOM_ORDER)
ax2.bar(eff.index, eff.values, color=[KINGDOM_COLOURS[k] for k in eff.index])
for i,v in enumerate(eff.values): ax2.text(i, v+0.6, f"{v:.1f}%", ha="center", fontsize=9)
ax2.set_ylabel("% effective"); ax2.set_title("Effective rate by kingdom (mild, realistic tilt)")
fig.suptitle("Four kingdoms of biocontrol microbes — each produces winners", fontsize=12)
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"kingdom_mix.png"); plt.close(fig)

# =============================================================================
# 3. DIFFERENT KINGDOMS, DIFFERENT WEAPONS (signal-gene prevalence per kingdom)
# =============================================================================
fig, ax = plt.subplots(figsize=(12,4.2))
prev = (geno.merge(phen[["strain_id","kingdom"]], on="strain_id")
        .groupby("kingdom")[SIGNAL_GENES].mean().reindex(KINGDOM_ORDER))
im = ax.imshow(prev.to_numpy(), aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
ax.set_yticks(range(len(KINGDOM_ORDER))); ax.set_yticklabels(KINGDOM_ORDER)
ax.set_xticks(range(len(SIGNAL_GENES))); ax.set_xticklabels(SIGNAL_GENES, rotation=90, fontsize=8)
ax.set_title("Different kingdoms carry different weapons (fraction of strains with each gene)")
fig.colorbar(im, ax=ax, shrink=0.7, label="prevalence")
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"weapons_by_kingdom.png"); plt.close(fig)

# =============================================================================
# 3b. NOT ALL GENES ARE INFORMATIVE (overall prevalence by gene type)
# =============================================================================
fig, ax = plt.subplots(figsize=(11,4))
order = SIGNAL_GENES+PGP_GENES+HK_GENES+NOISE_GENES
prevall = geno[order].mean().mul(100)
colours = ([GREEN]*len(SIGNAL_GENES) + [BLUE]*len(PGP_GENES)
           + [GREY]*len(HK_GENES) + [PURPLE]*len(NOISE_GENES))
ax.bar(range(len(order)), prevall.values, color=colours)
ax.set_ylabel("% of strains carrying the gene"); ax.set_ylim(0,105)
ax.set_xticks(range(len(order))); ax.set_xticklabels(order, rotation=90, fontsize=7)
handles = [plt.Rectangle((0,0),1,1,color=c) for c in [GREEN,BLUE,GREY,PURPLE]]
ax.legend(handles, ["suppression signal","growth signal","housekeeping (~all strains)","accessory noise"],
          fontsize=8, loc="upper right")
ax.set_title("Not all genes are informative: housekeeping genes are in ~every strain")
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"gene_prevalence.png"); plt.close(fig)

# =============================================================================
# 4. DATASET OVERVIEW — three layers, same strains, side by side (first 40)
# =============================================================================
n = 40
sub = df.head(n)
fig, axes = plt.subplots(1, 4, figsize=(13,5),
                         gridspec_kw={"width_ratios":[0.25,1.3,1.2,0.5]})
# kingdom strip
kmap = {k:i for i,k in enumerate(KINGDOM_ORDER)}
kcol = ListedColormap([KINGDOM_COLOURS[k] for k in KINGDOM_ORDER])
axes[0].imshow(sub["kingdom"].map(kmap).to_numpy().reshape(-1,1), aspect="auto", cmap=kcol)
axes[0].set_title("Kingdom"); axes[0].set_xticks([]); axes[0].set_ylabel(f"first {n} strains")
# genomics
g = sub[SIGNAL_GENES+PGP_GENES+HK_GENES+NOISE_GENES].to_numpy()
axes[1].imshow(g, aspect="auto", cmap=ListedColormap(["#EEF1F5", BLUE]))
axes[1].set_title("Genomics (gene present = blue)")
axes[1].set_xticks(range(g.shape[1]))
axes[1].set_xticklabels(SIGNAL_GENES+PGP_GENES+HK_GENES+NOISE_GENES, rotation=90, fontsize=5)
axes[1].set_yticks([])
# metabolomics
m = np.log1p(sub[SIGNAL_METAB+NOISE_METAB].to_numpy())
axes[2].imshow(m, aspect="auto", cmap="YlGnBu")
axes[2].set_title("Metabolomics (log abundance)")
axes[2].set_xticks(range(m.shape[1]))
axes[2].set_xticklabels(SIGNAL_METAB+NOISE_METAB, rotation=90, fontsize=5)
axes[2].set_yticks([])
# phenotype
axes[3].barh(range(n), sub["suppression_score"].to_numpy(),
             color=np.where(sub["is_effective"]==1, GREEN, GREY))
axes[3].axvline(65, color="red", lw=1, ls="--")
axes[3].set_title("Phenotype (suppression %)"); axes[3].set_yticks([]); axes[3].invert_yaxis()
axes[3].set_xlim(0,100)
fig.suptitle("One dataset, several views of the same multi-kingdom strains", fontsize=12)
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"dataset_overview.png"); plt.close(fig)

# =============================================================================
# 5. THE SIGNAL — a producing metabolite vs the outcome, coloured by kingdom
# =============================================================================
fig, ax = plt.subplots(figsize=(6.5,4.5))
for k in KINGDOM_ORDER:
    s = df[df["kingdom"]==k]
    ax.scatter(s["iturin"], s["suppression_score"], s=16, alpha=0.6,
               color=KINGDOM_COLOURS[k], label=k)
ax.axhline(65, color="red", ls="--", lw=1)
ax.set_xlabel("iturin abundance (a bacterial antifungal lipopeptide)")
ax.set_ylabel("disease suppression (%)")
ax.set_title("A weapon works within its kingdom: iturin (bacterial) vs suppression")
ax.legend(fontsize=8, title="kingdom")
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"signal_scatter.png"); plt.close(fig)

# =============================================================================
# 6. MISSINGNESS — where the metabolite readings dropped out
# =============================================================================
fig, ax = plt.subplots(figsize=(8,4.5))
miss = metab[SIGNAL_METAB+NOISE_METAB].head(80).isna().to_numpy()
ax.imshow(miss, aspect="auto", cmap=ListedColormap(["#EEF1F5", GOLD]))
ax.set_title(f"Missing metabolite readings (gold = missing) — {metab[SIGNAL_METAB+NOISE_METAB].isna().sum().sum()} cells total")
ax.set_xticks(range(len(SIGNAL_METAB+NOISE_METAB)))
ax.set_xticklabels(SIGNAL_METAB+NOISE_METAB, rotation=90, fontsize=6)
ax.set_ylabel("first 80 strains")
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"missingness.png"); plt.close(fig)

# =============================================================================
# 7. METABOLITE-OUTCOME CORRELATION — which metabolites carry signal?
# =============================================================================
fig, ax = plt.subplots(figsize=(9,4))
cors = {m: df[[m,"suppression_score"]].corr().iloc[0,1] for m in SIGNAL_METAB+NOISE_METAB}
cs = pd.Series(cors)
colours = [GREEN if m in SIGNAL_METAB else PURPLE for m in cs.index]
ax.bar(range(len(cs)), cs.values, color=colours)
ax.axhline(0, color="black", lw=0.8)
ax.set_ylabel("correlation with suppression %")
ax.set_xticks(range(len(cs))); ax.set_xticklabels(cs.index, rotation=90, fontsize=8)
handles = [plt.Rectangle((0,0),1,1,color=c) for c in [GREEN,PURPLE]]
ax.legend(handles, ["signal metabolite","background noise"], fontsize=8)
ax.set_title("The signal metabolites correlate with the outcome; the noise ones don't")
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"metabolite_correlation.png"); plt.close(fig)

# =============================================================================
# 8. BATCH EFFECT — systematic drift the cleaning phase must correct
# =============================================================================
fig, ax = plt.subplots(figsize=(7,4))
data = [df.loc[df["batch_id"]==b, "surfactin"].dropna().to_numpy() for b in range(1,7)]
bp = ax.boxplot(data, tick_labels=[f"batch {b}" for b in range(1,7)], patch_artist=True)
for patch in bp["boxes"]: patch.set_facecolor("#E8F0FE")
ax.set_ylabel("surfactin abundance"); ax.set_title("Batch effect: the same measurement drifts between lab batches")
footnote(fig); fig.tight_layout(); fig.savefig(FIG/"batch_effect.png"); plt.close(fig)

# =============================================================================
# 9. INTERACTIVE — hover any strain to see its details (Plotly -> HTML)
# =============================================================================
plot_df = df.copy()
plot_df["status"] = np.where(plot_df["is_effective"]==1, "Effective", "Not effective")
plot_df["signal_genes_present"] = geno.set_index("strain_id").loc[plot_df["strain_id"], SIGNAL_GENES].sum(axis=1).values
figi = px.scatter(
    plot_df, x="signal_genes_present", y="suppression_score", color="kingdom",
    color_discrete_map=KINGDOM_COLOURS,
    hover_data={"strain_id":True, "genus":True, "kingdom":True,
                "signal_genes_present":True, "suppression_score":":.1f"},
    labels={"signal_genes_present":"number of biocontrol 'weapon' genes carried",
            "suppression_score":"disease suppression (%)"},
    title="StrainScope (SIMULATED): more weapons → more suppression, across every kingdom")
figi.add_hline(y=65, line_dash="dash", line_color="red",
               annotation_text="effective threshold (65%)")
figi.update_layout(template="plotly_white", height=520)
figi.write_html(INT/"signal_scatter.html", include_plotlyjs=True, full_html=True)

print("Wrote figures to figures/*.png and docs/interactive/signal_scatter.html")
print("Correlation check (signal metabolites should be positive, noise ~0):")
print(cs.round(2).to_string())
