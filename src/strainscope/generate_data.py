"""
generate_data.py — StrainScope Phase 1: the synthetic multi-omics data generator.
================================================================================

WHAT THIS SCRIPT DOES (in one sentence)
---------------------------------------
It invents a realistic-but-fake library of microbial strains and writes three
data tables about them to `data/raw/`: a genomics table, a metabolomics table,
and a phenotype table.

WHY IT EXISTS
-------------
Clean, matched multi-omics data on the SAME strains (genes AND chemicals AND a
measured outcome, all lined up) is not something you can simply download in one
tidy package. So instead of pretending, we BUILD the data ourselves, in code,
transparently. Everyone who runs this script gets the exact same data, because
we fix the "random seed" (see below). The data is grounded in real biology, but
it is SIMULATED — a model trained on it proves the workflow is correct, not that
the numbers would hold on real-world microbes. We say so plainly everywhere.

WHAT IS A "RANDOM SEED"?
------------------------
Computers make "random" numbers using a formula that starts from a chosen number
called the seed. Give the formula the same seed and it produces the exact same
sequence of "random" numbers every time. Everyday analogy: shuffling a deck of
cards the exact same way every time so everyone ends up with the identical
shuffle. Fixing the seed is what makes this dataset reproducible — the whole
point of a project others can rebuild.

HOW TO RUN IT
-------------
From the project root, with your virtual environment active:

    python src/strainscope/generate_data.py

or, as a module:

    python -m strainscope.generate_data      # (needs src on the import path)

It writes three CSV files into data/raw/ and prints a summary "ledger" so you
can see exactly what it produced.
"""

from __future__ import annotations

# --- Standard-library imports (these ship with Python) -----------------------
from pathlib import Path          # pathlib builds file paths that work on
                                  # Windows, macOS AND Linux without changes.

# --- Third-party imports (installed via requirements.txt) --------------------
import numpy as np                # numpy: fast number crunching + the random-
                                  # number generator we seed for reproducibility.
import pandas as pd               # pandas: tables ("programmable spreadsheets").
from faker import Faker           # Faker: makes realistic fake metadata
                                  # (dates, etc.) so the data feels lifelike.


# =============================================================================
# 1. SETTINGS — every knob that controls the dataset lives here, at the top,
#    so a reader can see and change the design in one place.
# =============================================================================

SEED = 42                 # The one number that makes everything reproducible.
N_STRAINS = 600           # How many microbial strains (samples) to invent.
N_BATCHES = 6             # Lab "batches" — groups processed together. Real labs
                          # process samples in batches, and each batch drifts a
                          # little (the "batch effect") — we simulate that so the
                          # cleaning phase has something real to correct.
EFFECTIVE_THRESHOLD = 65  # A strain counts as "effective" if it suppresses the
                          # disease by >= 65%. Winners are deliberately rare.
N_DUPLICATE_STRAINS = 8   # How many strains to accidentally record twice
                          # (real datasets have duplicate rows; QC must catch them).
METAB_MISSING_RATE = 0.06 # ~6% of metabolite readings go missing (instrument
                          # dropouts happen in real labs).
GENE_MISSING_RATE = 0.02  # ~2% of gene calls go missing (assembly gaps).
OUTLIER_RATE = 0.01       # ~1% of metabolite readings become wild spikes
                          # (measurement errors); QC will flag these.

# --- Where to write the output. Computed relative to THIS file, so it works
#     no matter which folder you run the script from (cross-platform safe). ----
ROOT = Path(__file__).resolve().parents[2]   # .../strainscope  (repo root)
RAW = ROOT / "data" / "raw"                  # .../strainscope/data/raw


# =============================================================================
# 2. THE BIOLOGY WE ARE MODELLING (grounded in real biocontrol science)
#    ------------------------------------------------------------------
#    Each name below is a REAL gene family or compound class known to matter
#    for microbes that protect plants. We split features into three honest
#    groups, because real data is a mix of signal and noise:
#
#      * SIGNAL genes/metabolites  -> genuinely linked to the outcome.
#      * HOUSEKEEPING genes        -> present in almost every strain (low
#                                     variance); carry no useful signal.
#      * NOISE genes/metabolites   -> present/vary at random; carry no signal.
#
#    Planting noise on purpose is important: it forces the later machine-
#    learning step to actually FIND the signal among distractors, which is
#    exactly the real challenge. A dataset where every column matters is a toy.
# =============================================================================

# Genes that truly contribute to DISEASE SUPPRESSION (antifungal / antibiotic /
# lipopeptide / cell-wall-degrading / iron-competition machinery):
SIGNAL_GENES = {
    "phlD":  "2,4-diacetylphloroglucinol (DAPG) biosynthesis — a broad antifungal antibiotic",
    "prnD":  "pyrrolnitrin biosynthesis — an antifungal antibiotic",
    "phzE":  "phenazine biosynthesis — an antibiotic active against many pathogens",
    "hcnA":  "hydrogen cyanide (HCN) production — suppresses fungi and some pests",
    "srfAA": "surfactin synthetase — a lipopeptide that disrupts microbial membranes",
    "ituA":  "iturin synthetase — a strongly antifungal lipopeptide",
    "fenA":  "fengycin synthetase — an antifungal lipopeptide",
    "chiA":  "chitinase — an enzyme that digests fungal cell walls",
    "pvdA":  "pyoverdine siderophore — starves pathogens of iron by out-competing them",
}

# Genes that contribute to PLANT-GROWTH PROMOTION (a secondary outcome):
PGP_GENES = {
    "acdS": "ACC deaminase — relieves plant stress, boosting growth",
    "nifH": "nitrogen fixation — supplies plants with usable nitrogen",
    "gcd":  "glucose dehydrogenase — helps solubilise phosphate for the plant",
}

# Housekeeping genes: essential, so present in ~almost every strain. Low
# variance => the model should learn to ignore them. (Real, well-known markers.)
HOUSEKEEPING_GENES = {
    "recA": "DNA repair — a near-universal housekeeping gene",
    "gyrB": "DNA gyrase — a near-universal housekeeping gene",
    "rpoB": "RNA polymerase subunit — a near-universal housekeeping gene",
}

# Accessory "noise" genes: vary from strain to strain but have NO link to the
# outcome. Named generically because they stand in for the many accessory genes
# a real genome carries that aren't relevant to biocontrol.
NOISE_GENES = {f"acc{c}": "accessory gene with no link to performance"
               for c in "ABCDEF"}

# Metabolites (secreted small molecules). Each SIGNAL metabolite is PRODUCED BY a
# specific gene (its "producer"), so genomics and metabolomics are correlated —
# that cross-layer link is what makes multi-omics integration worthwhile. The
# link is imperfect on purpose (having a gene doesn't guarantee high production —
# regulation, environment, etc.).
SIGNAL_METABOLITES = {
    # metabolite name : producing gene
    "DAPG":         "phlD",
    "pyrrolnitrin": "prnD",
    "phenazine":    "phzE",
    "HCN":          "hcnA",
    "surfactin":    "srfAA",
    "iturin":       "ituA",
    "fengycin":     "fenA",
    "pyoverdine":   "pvdA",
}
# Background "noise" metabolites: measured, but unrelated to the outcome.
NOISE_METABOLITES = [f"bg_metabolite_{i}" for i in range(1, 7)]

# Messy categorical values (inconsistent case / spelling / whitespace) to give
# the cleaning phase real text-harmonisation work — exactly like real datasets.
MESSY_SITES = ["rhizosphere", "Rhizosphere", "RHIZOSPHERE ", " rhizosphere",
               "soil", "Soil", "soil ", "endosphere", "Endosphere",
               "phyllosphere", "Phyllosphere"]
MESSY_GENERA = ["Bacillus", "bacillus", "Bacillus ", "Pseudomonas",
                "Pseudomonas ", "Psuedomonas",   # deliberate typo
                "Streptomyces", "Trichoderma", "trichoderma"]


# =============================================================================
# 3. THE GENERATOR
# =============================================================================

def generate() -> dict[str, pd.DataFrame]:
    """Build and return the three tables as pandas DataFrames.

    Returns a dict: {"genomics": df, "metabolomics": df, "phenotype": df}.
    """
    # One random-number generator, seeded once. EVERY random draw below comes
    # from `rng`, so the whole dataset is determined by SEED alone.
    rng = np.random.default_rng(SEED)
    faker = Faker()
    Faker.seed(SEED)   # seed Faker too, so the fake dates are reproducible.

    # Clean strain identifiers: STRAIN_0001 ... STRAIN_0600.
    strain_ids = [f"STRAIN_{i:04d}" for i in range(1, N_STRAINS + 1)]

    # -- 3a. GENOMICS: presence(1)/absence(0) of each gene ---------------------
    # Each gene family has a "prevalence" — how common it is across strains.
    # Signal genes: moderately common. Housekeeping: almost always present.
    # Noise genes: random-ish. We draw each strain's gene as a coin flip
    # weighted by that prevalence.
    all_genes = (list(SIGNAL_GENES) + list(PGP_GENES)
                 + list(HOUSEKEEPING_GENES) + list(NOISE_GENES))

    prevalence = {}
    for g in SIGNAL_GENES:      prevalence[g] = rng.uniform(0.25, 0.55)  # moderate
    for g in PGP_GENES:         prevalence[g] = rng.uniform(0.30, 0.60)
    for g in HOUSEKEEPING_GENES: prevalence[g] = rng.uniform(0.95, 0.99) # ~all strains
    for g in NOISE_GENES:       prevalence[g] = rng.uniform(0.30, 0.70)

    genomics = pd.DataFrame({"strain_id": strain_ids})
    for g in all_genes:
        # rng.random(N) gives N numbers in [0,1); "< prevalence" turns them into
        # 0/1 with the right proportion of 1s.
        genomics[g] = (rng.random(N_STRAINS) < prevalence[g]).astype(int)

    # -- 3b. METABOLOMICS: continuous abundances -------------------------------
    # For a SIGNAL metabolite: if the producing gene is present, abundance tends
    # to be HIGH; if absent, LOW (but not exactly zero — trace amounts leak
    # through). We draw from a log-normal distribution, which is the classic
    # shape of chemical-abundance data (many small values, a few large ones).
    metabolomics = pd.DataFrame({"strain_id": strain_ids})

    def lognormal(mean_log, sigma_log, n):
        """Positive, right-skewed values — realistic for chemical abundances."""
        return rng.lognormal(mean=mean_log, sigma=sigma_log, size=n)

    for metab, producer_gene in SIGNAL_METABOLITES.items():
        has_gene = genomics[producer_gene].to_numpy()
        # High baseline when the gene is present, low when absent.
        high = lognormal(mean_log=3.0, sigma_log=0.5, n=N_STRAINS)   # ~e^3 ≈ 20
        low = lognormal(mean_log=0.5, sigma_log=0.6, n=N_STRAINS)    # ~e^0.5 ≈ 1.6
        metabolomics[metab] = np.where(has_gene == 1, high, low)

    for metab in NOISE_METABOLITES:
        # Background compounds: same distribution for everyone, no link to genes.
        metabolomics[metab] = lognormal(mean_log=2.0, sigma_log=0.7, n=N_STRAINS)

    # -- 3c. BATCH EFFECT (systematic lab drift) -------------------------------
    # Assign each strain to a processing batch, then multiply that batch's
    # metabolite readings by a batch-specific factor. This mimics the real
    # phenomenon where instruments/reagents drift between runs. The cleaning
    # phase will need to correct for it. We DON'T touch genomics (0/1 calls are
    # far less sensitive to this kind of drift).
    batch_id = rng.integers(1, N_BATCHES + 1, size=N_STRAINS)
    batch_factor = {b: rng.uniform(0.80, 1.25) for b in range(1, N_BATCHES + 1)}
    factors = np.array([batch_factor[b] for b in batch_id])
    metab_cols = list(SIGNAL_METABOLITES) + NOISE_METABOLITES
    metabolomics[metab_cols] = metabolomics[metab_cols].to_numpy() * factors[:, None]

    # -- 3d. THE HIDDEN "TRUTH": how effective is each strain, really? ---------
    # We compute a latent (hidden) efficacy from the SIGNAL features only, then
    # turn it into a 0–100 suppression score. This is the pattern the machine-
    # learning phase will later try to recover from the data.
    #
    # Contribution 1: signal genes present (each adds a fixed amount).
    gene_signal = genomics[list(SIGNAL_GENES)].to_numpy().sum(axis=1)
    # Contribution 2: signal metabolites (log-scaled so huge values don't
    # dominate), summed.
    metab_signal = np.log1p(metabolomics[list(SIGNAL_METABOLITES)].to_numpy()).sum(axis=1)
    # Contribution 3: synergy — having BOTH a strong gene set AND strong
    # chemistry is better than either alone (a small interaction term).
    synergy = 0.15 * gene_signal * (metab_signal / metab_signal.mean())
    # Random biological noise — nothing is perfectly predictable.
    noise = rng.normal(0, 1.2, size=N_STRAINS)

    latent = (1.4 * gene_signal) + (1.1 * metab_signal) + synergy + noise
    # Rescale the latent value to a 0–100 "% suppression" range. We map it with
    # min/max scaling and a stretch factor, then add a little noise so a FEW
    # values land slightly outside 0–100 — an "impossible" reading the cleaning
    # phase will have to clip. (Real data contains impossible values too.)
    z = (latent - latent.mean()) / latent.std()
    suppression = 50 + 20 * z + rng.normal(0, 2.5, size=N_STRAINS)
    # (No clipping here on purpose — QC clips later.)

    # Secondary outcome: plant-growth promotion, driven by the PGP genes plus
    # pyoverdine, on its own 0–100 scale.
    pgp_gene_signal = genomics[list(PGP_GENES)].to_numpy().sum(axis=1)
    pgp_metab = np.log1p(metabolomics["pyoverdine"].to_numpy())
    pgp_latent = (1.6 * pgp_gene_signal) + (0.8 * pgp_metab) + rng.normal(0, 1.0, N_STRAINS)
    pgp_z = (pgp_latent - pgp_latent.mean()) / pgp_latent.std()
    growth_promotion = 50 + 18 * pgp_z + rng.normal(0, 3.0, N_STRAINS)

    is_effective = (suppression >= EFFECTIVE_THRESHOLD).astype(int)

    phenotype = pd.DataFrame({
        "strain_id": strain_ids,
        "genus": rng.choice(MESSY_GENERA, size=N_STRAINS),         # messy on purpose
        "collection_site": rng.choice(MESSY_SITES, size=N_STRAINS),# messy on purpose
        "isolation_date": [faker.date_between("-8y", "today").isoformat()
                           for _ in range(N_STRAINS)],
        "batch_id": batch_id,
        "suppression_score": np.round(suppression, 2),
        "growth_promotion": np.round(growth_promotion, 2),
        "is_effective": is_effective,
    })

    # -- 3e. INJECT REALISTIC MESS (documented, on purpose) --------------------
    # (i) Missing values: scatter NaNs through metabolomics and genomics.
    def punch_holes(df, rate, columns):
        arr = df[columns].to_numpy(dtype=float)
        mask = rng.random(arr.shape) < rate      # True where we blank a value
        arr[mask] = np.nan
        df[columns] = arr
        return int(mask.sum())

    n_missing_metab = punch_holes(metabolomics, METAB_MISSING_RATE, metab_cols)
    n_missing_gene = punch_holes(genomics, GENE_MISSING_RATE, all_genes)

    # (ii) Outliers: a few metabolite readings spike to 10x (measurement errors).
    metab_arr = metabolomics[metab_cols].to_numpy()
    out_mask = (rng.random(metab_arr.shape) < OUTLIER_RATE) & ~np.isnan(metab_arr)
    metab_arr[out_mask] = metab_arr[out_mask] * 10
    metabolomics[metab_cols] = metab_arr
    n_outliers = int(out_mask.sum())

    # (iii) Duplicate rows: pick a few strains and record them TWICE in every
    # table (same strain_id appears on two rows) — a classic data-entry error.
    dup_ids = rng.choice(strain_ids, size=N_DUPLICATE_STRAINS, replace=False)
    for name, df in [("genomics", genomics), ("metabolomics", metabolomics),
                     ("phenotype", phenotype)]:
        dup_rows = df[df["strain_id"].isin(dup_ids)].copy()
        if name == "genomics":
            genomics = pd.concat([genomics, dup_rows], ignore_index=True)
        elif name == "metabolomics":
            metabolomics = pd.concat([metabolomics, dup_rows], ignore_index=True)
        else:
            phenotype = pd.concat([phenotype, dup_rows], ignore_index=True)

    # Round metabolite values for tidy CSVs (after all maths is done).
    metabolomics[metab_cols] = metabolomics[metab_cols].round(3)

    # Stash the counts so the caller can print an honest "ledger".
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
    }
    return {"genomics": genomics, "metabolomics": metabolomics, "phenotype": phenotype}


def main() -> None:
    """Generate the tables, write them to data/raw/, and print a summary."""
    RAW.mkdir(parents=True, exist_ok=True)     # make data/raw/ if missing
    tables = generate()

    for name, df in tables.items():
        out = RAW / f"{name}.csv"
        df.to_csv(out, index=False)
        print(f"  wrote {out.relative_to(ROOT)}  ({len(df):,} rows, {df.shape[1]} columns)")

    # The "data ledger" — an honest, at-a-glance summary of what we produced.
    L = generate.ledger                        # type: ignore[attr-defined]
    print("\n  ── StrainScope synthetic dataset — ledger ──────────────────────")
    print(f"  strains (samples ....... {L['n_strains']:,}")
    print(f"  effective strains ...... {L['n_effective']:,}  ({L['pct_effective']}%)  <- the rare winners")
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
