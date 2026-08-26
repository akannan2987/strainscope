"""
generate_data.py — StrainScope Phase 1: the synthetic multi-omics data generator.
================================================================================

WHAT THIS SCRIPT DOES (in one sentence)
---------------------------------------
It invents a realistic-but-fake library of beneficial microbial strains spanning
several kingdoms (bacteria, fungi, yeasts, oomycetes) and writes three data
tables about them to `data/raw/`: a genomics table, a metabolomics table, and a
phenotype table.

WHY IT EXISTS
-------------
Clean, matched multi-omics data on the SAME strains (genes AND chemicals AND a
measured outcome, all lined up) is not something you can simply download in one
tidy package. So instead of pretending, we BUILD the data ourselves, in code,
transparently. Everyone who runs this script gets the exact same data, because
we fix the "random seed" (see below). The data is grounded in real biology, but
it is SIMULATED — a model trained on it proves the workflow is correct, not that
the numbers would hold on real-world microbes. We say so plainly everywhere.

WHY "MULTI-KINGDOM"?
-------------------
Biological crop-protection agents ("biologicals") are not just bacteria. The real
landscape includes bacteria (Bacillus, Pseudomonas), fungi (Trichoderma,
Beauveria), yeasts, and oomycetes (Pythium) — and each group fights plant pests
with DIFFERENT weapons: bacteria lean on antibiotics and lipopeptides; fungi on
mycoparasitism (attacking other fungi) and toxins; yeasts on competition; and so
on. We model those four cellular groups because they share a molecular-fingerprint
basis (they all have genes AND produce measurable chemicals). Viruses and protozoa
are also part of the biocontrol landscape, but they do NOT share that basis (a
virus has no metabolome), so we deliberately leave them out of the molecular
matrix and mention them as context in the docs. That honest scoping is itself part
of doing this properly.

WHAT IS A "RANDOM SEED"?
------------------------
Computers make "random" numbers using a formula that starts from a chosen number
called the seed. Give the formula the same seed and it produces the exact same
sequence of "random" numbers every time. Everyday analogy: shuffling a deck of
cards the exact same way every time so everyone ends up with the identical
shuffle. Fixing the seed is what makes this dataset reproducible.

HOW TO RUN IT
-------------
From the project root, with your virtual environment active:

    python src/strainscope/generate_data.py

It writes three CSV files into data/raw/ and prints a summary "ledger".
"""

from __future__ import annotations

# --- Standard-library imports (these ship with Python) -----------------------
from pathlib import Path          # builds file paths that work on every OS.

# --- Third-party imports (installed via requirements.txt) --------------------
import numpy as np                # fast number crunching + the seeded RNG.
import pandas as pd               # tables ("programmable spreadsheets").
from faker import Faker           # realistic fake metadata (dates, etc.).


# =============================================================================
# 1. SETTINGS — every knob that controls the dataset, in one place.
# =============================================================================

SEED = 42                 # The one number that makes everything reproducible.
N_STRAINS = 600           # How many microbial strains (samples) to invent.
N_BATCHES = 6             # Lab "batches" — groups processed together (drift source).
EFFECTIVE_THRESHOLD = 65  # A strain is "effective" if it suppresses disease >= 65%.
N_DUPLICATE_STRAINS = 8   # How many strains to accidentally record twice.
METAB_MISSING_RATE = 0.06 # ~6% of metabolite readings go missing.
GENE_MISSING_RATE = 0.02  # ~2% of gene calls go missing.
OUTLIER_RATE = 0.01       # ~1% of metabolite readings become wild spikes.

ROOT = Path(__file__).resolve().parents[2]   # .../strainscope  (repo root)
RAW = ROOT / "data" / "raw"                  # .../strainscope/data/raw


# =============================================================================
# 2. THE BIOLOGY WE ARE MODELLING (grounded in real biocontrol science)
#    ------------------------------------------------------------------
#    KINGDOMS: the four cellular groups we model, each with typical genera.
#    Proportions reflect that bacteria are the most-studied biocontrol agents,
#    then fungi, then yeasts, then oomycetes.
# =============================================================================

KINGDOM_GENERA = {
    "Bacteria": ["Bacillus", "Pseudomonas", "Streptomyces", "Paenibacillus"],
    "Fungi":    ["Trichoderma", "Beauveria", "Metarhizium", "Clonostachys"],
    "Yeast":    ["Metschnikowia", "Aureobasidium", "Saccharomyces", "Candida"],
    "Oomycete": ["Pythium"],
}
KINGDOM_PROPORTIONS = {"Bacteria": 0.45, "Fungi": 0.30, "Yeast": 0.15, "Oomycete": 0.10}

# Prevalence tuples below are ordered (Bacteria, Fungi, Yeast, Oomycete).
KINGDOM_ORDER = ("Bacteria", "Fungi", "Yeast", "Oomycete")
KINGDOM_INDEX = {k: i for i, k in enumerate(KINGDOM_ORDER)}

# --- SIGNAL genes -------------------------------------------------------------
# Each signal gene GENUINELY contributes to disease suppression. Crucially, each
# has a per-kingdom PREVALENCE: a bacterial weapon (e.g. surfactin synthetase) is
# common in bacteria and essentially absent in fungi, and vice-versa. This is
# what makes "kingdom" a real driver of a strain's molecular profile — different
# microbes carry different weapons. Some genes PRODUCE a measurable metabolite
# ("metabolite": name); others are enzymes with no secreted small molecule
# ("metabolite": None) and so contribute through the genomics layer only.
SIGNAL_GENES = {
    # ---- Bacterial antibiotics, lipopeptides, siderophore ----
    "phlD":  {"desc": "DAPG antifungal antibiotic biosynthesis",        "metabolite": "DAPG",         "prev": (0.45, 0.02, 0.01, 0.02)},
    "prnD":  {"desc": "pyrrolnitrin antifungal antibiotic biosynthesis", "metabolite": "pyrrolnitrin", "prev": (0.40, 0.02, 0.01, 0.02)},
    "phzE":  {"desc": "phenazine antibiotic biosynthesis",              "metabolite": "phenazine",    "prev": (0.42, 0.02, 0.01, 0.02)},
    "hcnA":  {"desc": "hydrogen cyanide (HCN) production",              "metabolite": "HCN",          "prev": (0.38, 0.03, 0.01, 0.03)},
    "srfAA": {"desc": "surfactin lipopeptide synthetase",              "metabolite": "surfactin",    "prev": (0.45, 0.02, 0.02, 0.01)},
    "ituA":  {"desc": "iturin antifungal lipopeptide synthetase",      "metabolite": "iturin",       "prev": (0.42, 0.02, 0.01, 0.01)},
    "fenA":  {"desc": "fengycin antifungal lipopeptide synthetase",    "metabolite": "fengycin",     "prev": (0.40, 0.02, 0.01, 0.01)},
    "pvdA":  {"desc": "pyoverdine siderophore (iron competition)",     "metabolite": "pyoverdine",   "prev": (0.40, 0.05, 0.05, 0.03)},
    # ---- Cross-kingdom cell-wall-degrading enzymes ----
    "chiA":  {"desc": "chitinase — digests fungal cell walls",         "metabolite": None,           "prev": (0.30, 0.50, 0.10, 0.40)},
    "glcA":  {"desc": "beta-1,3-glucanase — degrades fungal walls",    "metabolite": None,           "prev": (0.20, 0.55, 0.15, 0.45)},
    # ---- Fungal mycoparasitism & antifungal metabolites ----
    "ech42": {"desc": "endochitinase (Trichoderma mycoparasitism)",    "metabolite": None,           "prev": (0.03, 0.55, 0.05, 0.10)},
    "prb1":  {"desc": "mycoparasitic protease",                        "metabolite": None,           "prev": (0.03, 0.50, 0.05, 0.30)},
    "sixPP": {"desc": "6-pentyl-alpha-pyrone antifungal volatile",     "metabolite": "six_PP",       "prev": (0.02, 0.45, 0.03, 0.03)},
    # ---- Entomopathogenic fungal (insect-killing) toxins ----
    "dtxS":  {"desc": "destruxin insecticidal toxin synthetase",       "metabolite": "destruxin",    "prev": (0.01, 0.35, 0.02, 0.01)},
    "beaS":  {"desc": "beauvericin insecticidal toxin synthetase",     "metabolite": "beauvericin",  "prev": (0.01, 0.30, 0.02, 0.01)},
    # ---- Oomycete mycoparasitism / elicitor ----
    "olpA":  {"desc": "oligandrin elicitor (Pythium oligandrum)",      "metabolite": "oligandrin",   "prev": (0.01, 0.05, 0.02, 0.70)},
    # ---- Yeast competition / killer toxin ----
    "kilT":  {"desc": "killer toxin (yeast antagonism)",               "metabolite": "killer_toxin", "prev": (0.02, 0.03, 0.50, 0.02)},
    "sidA":  {"desc": "yeast siderophore (iron competition)",          "metabolite": "yeast_siderophore", "prev": (0.03, 0.10, 0.45, 0.05)},
}

# --- Plant-growth-promotion (PGP) genes: a SECONDARY outcome ------------------
PGP_GENES = {
    "acdS": {"desc": "ACC deaminase — relieves plant stress", "prev": (0.40, 0.20, 0.10, 0.10)},
    "nifH": {"desc": "nitrogen fixation",                     "prev": (0.35, 0.03, 0.02, 0.02)},
    "gcd":  {"desc": "phosphate solubilisation",             "prev": (0.40, 0.15, 0.10, 0.10)},
    "iaaM": {"desc": "auxin (IAA) production — boosts growth","prev": (0.30, 0.35, 0.20, 0.10)},
}

# --- Housekeeping genes: conserved, present in ~all microbes of EVERY kingdom -
HOUSEKEEPING_GENES = {
    "ssu_rRNA": "small-subunit ribosomal RNA gene — a universal marker",
    "ef1a":     "translation elongation factor — broadly conserved",
    "rpb1":     "largest RNA-polymerase subunit — broadly conserved",
}

# --- Accessory "noise" genes: vary from strain to strain, NO link to outcome --
NOISE_GENES = {f"acc{c}": "accessory gene with no link to performance" for c in "ABCDEF"}

# --- Metabolites: derived from SIGNAL_GENES that have a producer metabolite ----
SIGNAL_METABOLITES = {info["metabolite"]: gene
                      for gene, info in SIGNAL_GENES.items()
                      if info["metabolite"] is not None}
NOISE_METABOLITES = [f"bg_metabolite_{i}" for i in range(1, 7)]

# Messy categorical values to give the cleaning phase real harmonisation work.
MESSY_SITES = ["rhizosphere", "Rhizosphere", "RHIZOSPHERE ", " rhizosphere",
               "soil", "Soil", "soil ", "endosphere", "Endosphere",
               "phyllosphere", "Phyllosphere", "compost", "Compost"]
GENUS_TYPOS = {"Pseudomonas": "Psuedomonas", "Trichoderma": "trichoderma"}


# =============================================================================
# 3. THE GENERATOR
# =============================================================================

def generate() -> dict[str, pd.DataFrame]:
    """Build and return the three tables as pandas DataFrames."""
    rng = np.random.default_rng(SEED)      # one seeded RNG => reproducible data.
    faker = Faker(); Faker.seed(SEED)

    strain_ids = [f"STRAIN_{i:04d}" for i in range(1, N_STRAINS + 1)]

    # -- 3a. Assign each strain a KINGDOM, then a genus from that kingdom -------
    kingdoms = rng.choice(list(KINGDOM_PROPORTIONS),
                          size=N_STRAINS, p=list(KINGDOM_PROPORTIONS.values()))
    k_idx = np.array([KINGDOM_INDEX[k] for k in kingdoms])   # 0..3 per strain

    def messy_genus(kingdom: str) -> str:
        g = rng.choice(KINGDOM_GENERA[kingdom])
        r = rng.random()
        if g in GENUS_TYPOS and r < 0.15:   return GENUS_TYPOS[g]   # a real typo
        if r < 0.30:                         return g + " "          # trailing space
        if r < 0.45:                         return g.lower()        # wrong case
        return g
    genera = [messy_genus(k) for k in kingdoms]

    # -- 3b. GENOMICS: presence(1)/absence(0), KINGDOM-specific prevalence ------
    all_genes = (list(SIGNAL_GENES) + list(PGP_GENES)
                 + list(HOUSEKEEPING_GENES) + list(NOISE_GENES))
    genomics = pd.DataFrame({"strain_id": strain_ids})

    def draw_by_kingdom(prev_tuple) -> np.ndarray:
        p = np.array(prev_tuple)[k_idx]              # each strain's prevalence
        return (rng.random(N_STRAINS) < p).astype(int)

    for gene, info in SIGNAL_GENES.items():
        genomics[gene] = draw_by_kingdom(info["prev"])
    for gene, info in PGP_GENES.items():
        genomics[gene] = draw_by_kingdom(info["prev"])
    for gene in HOUSEKEEPING_GENES:                  # ~universal across kingdoms
        genomics[gene] = (rng.random(N_STRAINS) < rng.uniform(0.95, 0.99)).astype(int)
    for gene in NOISE_GENES:                         # kingdom-independent noise
        genomics[gene] = (rng.random(N_STRAINS) < rng.uniform(0.30, 0.70)).astype(int)

    # -- 3c. METABOLOMICS: high abundance when the producing gene is present ----
    metabolomics = pd.DataFrame({"strain_id": strain_ids})

    def lognormal(mean_log, sigma_log, n):
        return rng.lognormal(mean=mean_log, sigma=sigma_log, size=n)

    for metab, producer_gene in SIGNAL_METABOLITES.items():
        has_gene = genomics[producer_gene].to_numpy()
        high = lognormal(3.0, 0.5, N_STRAINS)        # ~e^3 ≈ 20 when gene present
        low = lognormal(0.5, 0.6, N_STRAINS)         # trace amounts when absent
        metabolomics[metab] = np.where(has_gene == 1, high, low)
    for metab in NOISE_METABOLITES:
        metabolomics[metab] = lognormal(2.0, 0.7, N_STRAINS)

    # -- 3d. BATCH EFFECT (systematic lab drift on metabolite readings) --------
    batch_id = rng.integers(1, N_BATCHES + 1, size=N_STRAINS)
    batch_factor = {b: rng.uniform(0.80, 1.25) for b in range(1, N_BATCHES + 1)}
    factors = np.array([batch_factor[b] for b in batch_id])
    metab_cols = list(SIGNAL_METABOLITES) + NOISE_METABOLITES
    metabolomics[metab_cols] = metabolomics[metab_cols].to_numpy() * factors[:, None]

    # -- 3e. THE HIDDEN "TRUTH": disease-suppression, from SIGNAL features only -
    # Each kingdom reaches efficacy via its OWN weapons. Because a strain only
    # carries its kingdom's genes, the sums below are automatically kingdom-
    # appropriate — the model must learn several "recipes", not one.
    gene_signal = genomics[list(SIGNAL_GENES)].to_numpy().sum(axis=1)
    metab_signal = np.log1p(metabolomics[list(SIGNAL_METABOLITES)].to_numpy()).sum(axis=1)
    synergy = 0.15 * gene_signal * (metab_signal / metab_signal.mean())
    noise = rng.normal(0, 1.2, size=N_STRAINS)

    latent = (1.4 * gene_signal) + (1.1 * metab_signal) + synergy + noise
    # Judge each strain RELATIVE TO ITS OWN KINGDOM. A yeast and a bacterium fight
    # with different arsenals, so scoring them on one absolute scale would be
    # unfair (and would let a model cheat by reading the kingdom label). We z-score
    # the latent value within each kingdom, then add a small, realistic tilt
    # (bacteria are, on average, somewhat stronger direct antagonists). This keeps
    # every kingdom producing some winners, so the model must learn the mechanisms.
    latent_z = np.zeros(N_STRAINS, dtype=float)
    for k in KINGDOM_ORDER:
        m = (kingdoms == k)
        if m.sum() > 1:
            latent_z[m] = (latent[m] - latent[m].mean()) / latent[m].std()
    kingdom_tilt = {"Bacteria": 0.30, "Fungi": 0.10, "Oomycete": 0.00, "Yeast": -0.10}
    tilt = np.array([kingdom_tilt[k] for k in kingdoms])
    suppression = 52 + 16 * (latent_z + tilt) + rng.normal(0, 2.5, size=N_STRAINS)

    pgp_gene_signal = genomics[list(PGP_GENES)].to_numpy().sum(axis=1)
    pgp_latent = (1.6 * pgp_gene_signal) + rng.normal(0, 1.0, N_STRAINS)
    pgp_z = (pgp_latent - pgp_latent.mean()) / pgp_latent.std()
    growth_promotion = 50 + 18 * pgp_z + rng.normal(0, 3.0, N_STRAINS)

    is_effective = (suppression >= EFFECTIVE_THRESHOLD).astype(int)

    phenotype = pd.DataFrame({
        "strain_id": strain_ids,
        "kingdom": kingdoms,
        "genus": genera,                                  # messy on purpose
        "collection_site": rng.choice(MESSY_SITES, size=N_STRAINS),
        "isolation_date": [faker.date_between("-8y", "today").isoformat()
                           for _ in range(N_STRAINS)],
        "batch_id": batch_id,
        "suppression_score": np.round(suppression, 2),
        "growth_promotion": np.round(growth_promotion, 2),
        "is_effective": is_effective,
    })

    # -- 3f. INJECT REALISTIC MESS (documented, on purpose) --------------------
    def punch_holes(df, rate, columns):
        arr = df[columns].to_numpy(dtype=float)
        mask = rng.random(arr.shape) < rate
        arr[mask] = np.nan
        df[columns] = arr
        return int(mask.sum())

    n_missing_metab = punch_holes(metabolomics, METAB_MISSING_RATE, metab_cols)
    n_missing_gene = punch_holes(genomics, GENE_MISSING_RATE, all_genes)

    metab_arr = metabolomics[metab_cols].to_numpy()
    out_mask = (rng.random(metab_arr.shape) < OUTLIER_RATE) & ~np.isnan(metab_arr)
    metab_arr[out_mask] = metab_arr[out_mask] * 10
    metabolomics[metab_cols] = metab_arr
    n_outliers = int(out_mask.sum())

    dup_ids = rng.choice(strain_ids, size=N_DUPLICATE_STRAINS, replace=False)
    for name in ("genomics", "metabolomics", "phenotype"):
        df = {"genomics": genomics, "metabolomics": metabolomics, "phenotype": phenotype}[name]
        dup_rows = df[df["strain_id"].isin(dup_ids)].copy()
        if name == "genomics":       genomics = pd.concat([genomics, dup_rows], ignore_index=True)
        elif name == "metabolomics": metabolomics = pd.concat([metabolomics, dup_rows], ignore_index=True)
        else:                        phenotype = pd.concat([phenotype, dup_rows], ignore_index=True)

    metabolomics[metab_cols] = metabolomics[metab_cols].round(3)

    eff_by_kingdom = (phenotype.drop_duplicates("strain_id")
                      .groupby("kingdom")["is_effective"].mean().mul(100).round(1).to_dict())

    generate.ledger = {                       # type: ignore[attr-defined]
        "n_strains": N_STRAINS,
        "n_effective": int(is_effective.sum()),
        "pct_effective": round(100 * is_effective.mean(), 1),
        "n_missing_metabolite_cells": n_missing_metab,
        "n_missing_gene_cells": n_missing_gene,
        "n_outlier_cells": n_outliers,
        "n_duplicate_strains": N_DUPLICATE_STRAINS,
        "n_impossible_scores": int(((suppression < 0) | (suppression > 100)).sum()),
        "n_genes": len(all_genes),
        "n_metabolites": len(metab_cols),
        "kingdom_counts": {k: int((kingdoms == k).sum()) for k in KINGDOM_ORDER},
        "eff_by_kingdom": eff_by_kingdom,
    }
    return {"genomics": genomics, "metabolomics": metabolomics, "phenotype": phenotype}


def main() -> None:
    """Generate the tables, write them to data/raw/, and print a summary."""
    RAW.mkdir(parents=True, exist_ok=True)
    tables = generate()
    for name, df in tables.items():
        out = RAW / f"{name}.csv"
        df.to_csv(out, index=False)
        print(f"  wrote {out.relative_to(ROOT)}  ({len(df):,} rows, {df.shape[1]} columns)")

    L = generate.ledger                        # type: ignore[attr-defined]
    print("\n  ── StrainScope synthetic dataset — ledger ──────────────────────")
    print(f"  strains (samples ....... {L['n_strains']:,}")
    print(f"  effective strains ...... {L['n_effective']:,}  ({L['pct_effective']}%)  <- the rare winners")
    kc = "  ".join(f"{k}:{n}" for k, n in L['kingdom_counts'].items())
    print(f"  kingdoms ............... {kc}")
    eb = "  ".join(f"{k}:{v}%" for k, v in L['eff_by_kingdom'].items())
    print(f"  effective by kingdom ... {eb}")
    print(f"  genes (genomics cols) .. {L['n_genes']}")
    print(f"  metabolites (metab cols) {L['n_metabolites']}")
    print(f"  missing metabolite cells {L['n_missing_metabolite_cells']:,}  (instrument dropouts)")
    print(f"  missing gene cells ..... {L['n_missing_gene_cells']:,}  (assembly gaps)")
    print(f"  outlier metabolite cells {L['n_outlier_cells']:,}  (measurement spikes)")
    print(f"  duplicated strains ..... {L['n_duplicate_strains']}  (recorded twice)")
    print(f"  impossible scores ...... {L['n_impossible_scores']}  (<0 or >100 %; QC will clip)")
    print("  ────────────────────────────────────────────────────────────────")
    print("  Reminder: this data is SIMULATED. It proves the workflow, not real-world accuracy.")


if __name__ == "__main__":
    main()
