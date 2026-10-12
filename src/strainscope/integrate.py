"""
src/strainscope/integrate.py (StrainScope Phase 3): multi-omics integration, the Python side.
=============================================================================================

WHAT THIS MODULE DOES (in one sentence)
---------------------------------------
It turns the clean genomics and metabolomics tables into two aligned "blocks"
ready for integration, runs a plain-Python counterpart to DIABLO with leak-free
cross-validation, checks how well each approach recovers the signal we know
is there, and publishes every result into the project database.

THE FOUR VERBS (run them from the project root, venv active)
------------------------------------------------------------
    python src/strainscope/integrate.py prepare   # clean tables -> integration-ready blocks
    Rscript R/diablo_integration.R                # DIABLO in R (reads the same blocks)
    python src/strainscope/integrate.py twin      # the Python counterpart + controls
    python src/strainscope/integrate.py publish   # results -> DuckDB tables (int_*)

or all four in order, with one command:

    python src/strainscope/integrate.py all       # skips the R step politely if R is absent

WHERE THINGS GO
---------------
  data/processed/integration/   the prepared blocks (regenerable, NOT in Git)
  artifacts/integration/        small result tables (committed, since the app reads them)
  data/processed/strainscope.duckdb   gains int_* tables after `publish`

THE DECISIONS, WRITTEN DOWN (each is explained in docs/04-integration.md)
------------------------------------------------------------------------
1. ALIGN on strain_id and refuse to continue if any strain is missing from a
   block: integration needs the SAME strains in every block, in the same order.
2. FILL gaps (imputation) using each strain's OWN kingdom: a missing gene call
   gets the most common value among strains of that kingdom; a missing
   metabolite gets that kingdom's median. Labels (effective or not) are never
   used to fill anything.
3. DROP near-constant features: a feature whose single most common value covers
   95 % or more of strains cannot tell strains apart (the housekeeping genes).
4. TRANSFORM metabolites with log(1 + x): abundances span orders of magnitude;
   the log puts "10 vs 20" and "100 vs 200" on the same footing.
5. COMPARE LIKE WITH LIKE: the efficacy score was defined relative to each
   kingdom (Phase 1), so a second version of every block is centred within
   kingdom. Both versions are kept; DIABLO tests both and the better is used.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Make `strainscope` importable no matter where the script is run from
# (the same pattern as fetch_real.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strainscope.generate_data import (  # noqa: E402  (after the path fix)
    HOUSEKEEPING_GENES, KINGDOM_ORDER, NOISE_GENES, NOISE_METABOLITES,
    PGP_GENES, SIGNAL_GENES, SIGNAL_METABOLITES)

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "processed" / "strainscope.duckdb"
BLOCKS = ROOT / "data" / "processed" / "integration"
ARTIFACTS = ROOT / "artifacts" / "integration"
R_SCRIPT = ROOT / "R" / "diablo_integration.R"

SEED = 42                    # same seed as the generator: reproducible folds
NEAR_CONSTANT_SHARE = 0.95   # rule 3 above
CV_FOLDS, CV_REPEATS = 5, 10 # 5-fold cross-validation, repeated 10 times


# =============================================================================
# FEATURE ANNOTATION: what we KNOW about every column (synthetic superpower)
# =============================================================================

def _arsenal(prev: tuple[float, ...]) -> str:
    """Which kingdom's weapon is this? Two or more kingdoms carrying it at
    >= 30 % makes it 'Cross-kingdom'; otherwise the most common carrier."""
    strong = [k for k, p in zip(KINGDOM_ORDER, prev) if p >= 0.30]
    if len(strong) >= 2:
        return "Cross-kingdom"
    return KINGDOM_ORDER[int(np.argmax(prev))]


def feature_annotations() -> pd.DataFrame:
    """One row per feature: its block, its role in the simulation, and which
    kingdom's arsenal it belongs to.

    Because the data is synthetic, we know the ground truth: which features
    were written into the efficacy formula ('signal') and which were not
    ('decoy'). Real projects never get this answer key. We use it to GRADE the
    signatures the methods find, which is the point of building on known data."""
    rows = []
    for gene, info in SIGNAL_GENES.items():
        rows.append({"feature": gene, "block": "genomics", "role": "signal",
                     "arsenal": _arsenal(info["prev"]), "description": info["desc"]})
    for gene, info in PGP_GENES.items():
        rows.append({"feature": gene, "block": "genomics", "role": "decoy",
                     "arsenal": "Plant-growth (other trait)", "description": info["desc"]})
    for gene, desc in HOUSEKEEPING_GENES.items():
        rows.append({"feature": gene, "block": "genomics", "role": "housekeeping",
                     "arsenal": "Housekeeping", "description": desc})
    for gene, desc in NOISE_GENES.items():
        rows.append({"feature": gene, "block": "genomics", "role": "decoy",
                     "arsenal": "Accessory noise", "description": desc})
    for metab, gene in SIGNAL_METABOLITES.items():
        rows.append({"feature": metab, "block": "metabolomics", "role": "signal",
                     "arsenal": _arsenal(SIGNAL_GENES[gene]["prev"]),
                     "description": f"product of {gene} ({SIGNAL_GENES[gene]['desc']})",
                     "producer_gene": gene})
    for metab in NOISE_METABOLITES:
        rows.append({"feature": metab, "block": "metabolomics", "role": "decoy",
                     "arsenal": "Background chemistry", "description":
                     "background compound with no link to performance"})
    return pd.DataFrame(rows)


# =============================================================================
# PREPARE: clean tables -> aligned, imputed, filtered, transformed blocks
# =============================================================================

def load_clean_tables(db_path: Path = DB_PATH) -> dict[str, pd.DataFrame]:
    """Read the three clean tables from the database (read-only), indexed by
    strain_id and sorted, so every block lists strains in the same order."""
    import duckdb
    if not db_path.exists():
        sys.exit(f"No database at {db_path}.\n"
                 "Build it first:  python src/strainscope/harmonize.py")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        out = {name: con.execute(f"SELECT * FROM {name} ORDER BY strain_id").fetchdf()
                     .set_index("strain_id")
               for name in ("genomics", "metabolomics", "phenotype")}
    finally:
        con.close()
    return out


def align_blocks(genomics: pd.DataFrame, metabolomics: pd.DataFrame,
                 phenotype: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Rule 1: the same strains, in the same order, in every block.

    Integration methods match rows by POSITION, not by name: row 17 of the
    genes block must be the same strain as row 17 of the chemistry block. So we
    check the strain sets are identical and stop loudly if they are not."""
    sets = [set(genomics.index), set(metabolomics.index), set(phenotype.index)]
    if not (sets[0] == sets[1] == sets[2]):
        missing = (sets[0] | sets[1] | sets[2]) - (sets[0] & sets[1] & sets[2])
        raise ValueError(f"{len(missing)} strain(s) are not present in every table, "
                         f"e.g. {sorted(missing)[:5]}. Re-run python src/strainscope/harmonize.py")
    order = sorted(sets[0])
    return genomics.loc[order], metabolomics.loc[order], phenotype.loc[order]


def impute_within_kingdom(block: pd.DataFrame, kingdom: pd.Series,
                          binary: bool) -> tuple[pd.DataFrame, int]:
    """Rule 2: fill each gap from the strain's own kingdom.

    Genes (binary): the most common value among that kingdom's strains, so a
    missing call for a yeast is filled with what yeasts usually carry.
    Metabolites: that kingdom's median. Returns the filled block and how many
    cells were filled (for the ledger)."""
    filled = block.copy().astype(float)
    n_missing = int(filled.isna().sum().sum())
    for k in kingdom.unique():
        rows = (kingdom == k).to_numpy()
        sub = filled.loc[rows]
        if binary:
            # mode = the most common value; ties go to 0 ("not detected"),
            # the conservative choice for a presence/absence call
            fill = (sub.mean() > 0.5).astype(float)
        else:
            fill = sub.median()
        filled.loc[rows] = sub.fillna(fill)
    # A column that is missing for an entire kingdom would still be empty;
    # fall back to the all-strain value so nothing is left blank.
    filled = filled.fillna(filled.median())
    return filled, n_missing


def near_constant_features(block: pd.DataFrame,
                           share: float = NEAR_CONSTANT_SHARE) -> list[str]:
    """Rule 3: features whose most common value covers >= `share` of strains.
    A question that (almost) everyone answers the same way can't separate them."""
    top_share = block.apply(lambda col: col.value_counts(normalize=True).iloc[0])
    return sorted(top_share[top_share >= share].index.tolist())


def centre_within_kingdom(block: pd.DataFrame, kingdom: pd.Series) -> pd.DataFrame:
    """Rule 5: subtract each kingdom's average from its own strains.

    After this, a value says "how much more (or less) of this does the strain
    have than a typical member of ITS kingdom", the same yardstick the efficacy
    score uses. Only centring (no rescaling): rescaling would turn a gene that
    is rare in a kingdom into a giant number for the few strains carrying it."""
    out = block.copy()
    for k in kingdom.unique():
        rows = (kingdom == k).to_numpy()
        out.loc[rows] = out.loc[rows] - out.loc[rows].mean()
    return out


def prepare(db_path: Path = DB_PATH, blocks_dir: Path = BLOCKS,
            artifacts_dir: Path = ARTIFACTS, verbose: bool = True) -> dict:
    """Run rules 1 to 5 and write the blocks both R and Python read."""
    t = load_clean_tables(db_path)
    g, m, p = align_blocks(t["genomics"], t["metabolomics"], t["phenotype"])
    kingdom = p["kingdom"]
    ledger: list[dict] = []

    g_imp, n_g = impute_within_kingdom(g, kingdom, binary=True)
    ledger.append({"step": "impute_within_kingdom", "block": "genomics",
                   "cells": n_g, "note": "kingdom's most common value"})
    m_log = np.log1p(m.astype(float))                    # rule 4 (NaN stays NaN)
    m_imp, n_m = impute_within_kingdom(m_log, kingdom, binary=False)
    ledger.append({"step": "impute_within_kingdom", "block": "metabolomics",
                   "cells": n_m, "note": "kingdom's median of log(1+x)"})

    dropped = {"genomics": near_constant_features(g_imp),
               "metabolomics": near_constant_features(m_imp)}
    for block_name, cols in dropped.items():
        ledger.append({"step": "drop_near_constant", "block": block_name,
                       "cells": len(cols), "note": ", ".join(cols) or "none"})
    g_imp = g_imp.drop(columns=dropped["genomics"])
    m_imp = m_imp.drop(columns=dropped["metabolomics"])

    g_cen = centre_within_kingdom(g_imp, kingdom)
    m_cen = centre_within_kingdom(m_imp, kingdom)

    blocks_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    g_imp.round(6).to_csv(blocks_dir / "block_genomics.csv")
    m_imp.round(6).to_csv(blocks_dir / "block_metabolomics.csv")
    g_cen.round(6).to_csv(blocks_dir / "block_genomics_centred.csv")
    m_cen.round(6).to_csv(blocks_dir / "block_metabolomics_centred.csv")
    outcome = p[["kingdom", "is_effective", "suppression_score"]]
    outcome.to_csv(blocks_dir / "outcome.csv")
    feature_annotations().to_csv(artifacts_dir / "feature_annotations.csv", index=False)
    led = pd.DataFrame(ledger)
    led.to_csv(artifacts_dir / "prepare_ledger.csv", index=False)

    summary = {"strains": len(p), "genes": g_imp.shape[1], "metabolites": m_imp.shape[1],
               "effective": int(p["is_effective"].sum()),
               "imputed_gene_cells": n_g, "imputed_metabolite_cells": n_m,
               "dropped": dropped}
    if verbose:
        print("  ── Integration prep ledger ─────────────────────────────────")
        print(f"  aligned strains ........ {summary['strains']} in every block "
              f"({summary['effective']} effective)")
        print(f"  genomics block ......... {g.shape[1]} → {g_imp.shape[1]} genes "
              f"(dropped near-constant: {', '.join(dropped['genomics']) or 'none'})")
        print(f"  metabolomics block ..... {m.shape[1]} → {m_imp.shape[1]} metabolites "
              f"(log(1+x) applied)")
        print(f"  gaps filled ............ {n_g} gene calls, {n_m} metabolite readings "
              "(kingdom-wise, labels never used)")
        print("  versions written ....... as-measured + centred within kingdom")
        print("  ─────────────────────────────────────────────────────────────")
        print(f"  blocks  → {blocks_dir.relative_to(ROOT)}/")
        print(f"  ledger  → {(artifacts_dir / 'prepare_ledger.csv').relative_to(ROOT)}")
    return summary


def read_blocks(blocks_dir: Path = BLOCKS, centred: bool = True):
    """Read the prepared blocks back (used by `twin`, the figures and the tests)."""
    suffix = "_centred" if centred else ""
    paths = [blocks_dir / f"block_genomics{suffix}.csv",
             blocks_dir / f"block_metabolomics{suffix}.csv", blocks_dir / "outcome.csv"]
    for path in paths:
        if not path.exists():
            sys.exit(f"Missing {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}.\n"
                     "Prepare the blocks first:  python src/strainscope/integrate.py prepare")
    g, m, o = (pd.read_csv(path, index_col=0) for path in paths)
    return g, m, o


# =============================================================================
# TWIN: the Python counterpart, scored with the same yardstick
# =============================================================================

def balanced_error_rate(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """The average of the two per-class error rates.

    Why not plain accuracy? Only 24 % of strains are effective, so a lazy model
    that always says "not effective" is 76 % accurate and completely useless.
    BER asks "how often are you wrong about the effective ones, and how often
    about the others?" and averages the two. The lazy model scores 0.50,
    exactly what a coin would. Lower is better."""
    errors = [np.mean(y_pred[y_true == c] != c) for c in (0, 1)]
    return float(np.mean(errors))


def _lasso_args() -> dict:
    """How to ask scikit-learn for an L1 ('lasso') penalty on THIS machine.

    scikit-learn 1.8 renamed the switch: newer versions take `l1_ratio=1`,
    older ones `penalty="l1"`. Checking the installed version keeps the code
    working (and warning-free) on both."""
    import sklearn
    major, minor = (int(part) for part in sklearn.__version__.split(".")[:2])
    return {"l1_ratio": 1.0} if (major, minor) >= (1, 8) else {"penalty": "l1"}


def _scaled_concat(g: pd.DataFrame, m: pd.DataFrame) -> np.ndarray:
    """Concatenate two blocks so each contributes EQUALLY.

    Each column is standardised, then each block is divided by the square root
    of its column count. Otherwise the block with more columns would shout
    louder just because it has more voices. (This is "block scaling", the
    early-integration counterpart to DIABLO giving each block its own say.)"""
    parts = []
    for block in (g, m):
        x = block.to_numpy(dtype=float)
        sd = x.std(axis=0)
        sd[sd == 0] = 1.0
        parts.append((x - x.mean(axis=0)) / sd / np.sqrt(x.shape[1]))
    return np.hstack(parts)


def cross_validate_models(g: pd.DataFrame, m: pd.DataFrame, outcome: pd.DataFrame,
                          folds: int = CV_FOLDS, repeats: int = CV_REPEATS,
                          seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score every approach on exactly the same repeated, stratified folds.

    'Stratified' = every fold keeps the 24 % effective share. 'Repeated' = the
    whole 5-fold exercise is redone 10 times with different shuffles, so one
    lucky split cannot flatter a model. Every scaler is fitted on the training
    part of each fold only (inside a Pipeline), so no information from the
    held-out strains leaks into the model.

    Returns (scoreboard, l1_selection_counts)."""
    from sklearn.cross_decomposition import PLSRegression
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import RepeatedStratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    y = outcome["is_effective"].to_numpy()
    G, M = g.to_numpy(float), m.to_numpy(float)
    GM = _scaled_concat(g, m)
    K = outcome[["kingdom"]].to_numpy()
    # The "no signal" control (y-scrambling): every repeat gets its OWN random
    # shuffle of the labels, and the model is trained AND scored on shuffled
    # labels. Any score better than a coin here would mean the procedure finds
    # "signal" in pure noise, i.e. something is leaking.
    rng = np.random.default_rng(seed)
    y_shuffles = [rng.permutation(y) for _ in range(repeats)]

    def logistic():
        return make_pipeline(StandardScaler(),
                             LogisticRegression(C=0.5, class_weight="balanced", max_iter=5000))

    def sparse_logistic():
        # L1 ("lasso") penalty: most weights are pushed to exactly zero, so the
        # model SELECTS a short list of features (like DIABLO's keepX).
        return make_pipeline(StandardScaler(),
                             LogisticRegression(**_lasso_args(), solver="liblinear", C=0.05,
                                                class_weight="balanced", max_iter=5000))

    names = ["Genomics only", "Metabolomics only",
             "Early integration (concatenate, logistic)",
             "Early integration, sparse (lasso logistic)",
             "Early integration (PLS-DA, 2 components)",
             "Late integration (average of per-block models)",
             "Control: kingdom label only", "Control: shuffled labels"]
    scores = {n: {"ber": [], "auc": []} for n in names}
    feature_names = list(g.columns) + list(m.columns)
    l1_counts = pd.Series(0, index=feature_names, dtype=int)
    n_fits = 0

    cv = RepeatedStratifiedKFold(n_splits=folds, n_repeats=repeats, random_state=seed)
    for fold_number, (train, test) in enumerate(cv.split(G, y)):
        def score(name, prob, thr=0.5, truth=None):
            truth = y[test] if truth is None else truth
            scores[name]["auc"].append(roc_auc_score(truth, prob))
            scores[name]["ber"].append(balanced_error_rate(truth, (prob >= thr).astype(int)))

        pg = logistic().fit(G[train], y[train]).predict_proba(G[test])[:, 1]
        pm = logistic().fit(M[train], y[train]).predict_proba(M[test])[:, 1]
        score("Genomics only", pg)
        score("Metabolomics only", pm)
        score("Early integration (concatenate, logistic)",
              logistic().fit(GM[train], y[train]).predict_proba(GM[test])[:, 1])

        sl = sparse_logistic().fit(GM[train], y[train])
        score("Early integration, sparse (lasso logistic)", sl.predict_proba(GM[test])[:, 1])
        coefs = sl[-1].coef_[0]
        l1_counts += (np.abs(coefs) > 1e-9).astype(int)
        n_fits += 1

        # PLS-DA: regress the 0/1 label on the blocks through 2 latent
        # components; classify by which class's average prediction is closer
        # (the 1-D version of DIABLO's "centroids distance").
        pls = make_pipeline(StandardScaler(), PLSRegression(n_components=2))
        pls.fit(GM[train], y[train].astype(float))
        fitted = pls.predict(GM[train]).ravel()
        thr = (fitted[y[train] == 0].mean() + fitted[y[train] == 1].mean()) / 2
        score("Early integration (PLS-DA, 2 components)", pls.predict(GM[test]).ravel(), thr)

        score("Late integration (average of per-block models)", (pg + pm) / 2)

        onehot = make_pipeline(OneHotEncoder(handle_unknown="ignore"),
                               LogisticRegression(class_weight="balanced", max_iter=5000))
        score("Control: kingdom label only",
              onehot.fit(K[train], y[train]).predict_proba(K[test])[:, 1])
        y_shuf = y_shuffles[fold_number // folds]       # this repeat's shuffle
        score("Control: shuffled labels",
              logistic().fit(GM[train], y_shuf[train]).predict_proba(GM[test])[:, 1],
              truth=y_shuf[test])

    def per_repeat(values: list[float]) -> np.ndarray:
        # One number per repeat (the average over its 5 folds). The ± we report
        # is how much that number moves when the folds are reshuffled. It's the
        # same definition mixOmics uses, so R and Python uncertainties are comparable.
        return np.asarray(values).reshape(repeats, folds).mean(axis=1)

    board = pd.DataFrame([{
        "approach": n,
        "ber_mean": round(float(per_repeat(s["ber"]).mean()), 4),
        "ber_sd": round(float(per_repeat(s["ber"]).std(ddof=1)), 4),
        "auc_mean": round(float(per_repeat(s["auc"]).mean()), 4),
        "auc_sd": round(float(per_repeat(s["auc"]).std(ddof=1)), 4),
        "n_folds_scored": len(s["ber"]),
    } for n, s in scores.items()])
    stability = (l1_counts / n_fits).rename("selection_frequency").reset_index()
    stability = stability.rename(columns={"index": "feature"})
    return board, stability


def cross_block_correlations(g: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    """Spearman correlation between every gene and every metabolite.

    'Spearman' ranks the values first, so it measures 'when one goes up, does
    the other tend to go up?' without assuming a straight line; it's robust to the
    two-hump shape of our chemistry. High correlations between a gene and its
    own product are the biology we planted; strong correlations between
    unrelated pairs would be a warning sign. This table is also the seed of the
    Phase 5 knowledge graph."""
    rg = g.rank().to_numpy(float)
    rm = m.rank().to_numpy(float)
    rg = (rg - rg.mean(axis=0)) / np.where(rg.std(axis=0) == 0, 1, rg.std(axis=0))
    rm = (rm - rm.mean(axis=0)) / np.where(rm.std(axis=0) == 0, 1, rm.std(axis=0))
    rho = rg.T @ rm / len(g)
    producer = {met: gene for met, gene in SIGNAL_METABOLITES.items()}
    rows = [{"gene": gene, "metabolite": met, "spearman_rho": round(float(rho[i, j]), 4),
             "is_producer_pair": producer.get(met) == gene}
            for i, gene in enumerate(g.columns) for j, met in enumerate(m.columns)]
    return pd.DataFrame(rows)


def grade_signature(selected: list[str], annotations: pd.DataFrame) -> dict:
    """How good is a selected feature list, judged against the planted truth?

    precision = of the features it picked, how many truly drive efficacy;
    recall    = of the true drivers available, how many it picked.
    Only possible because the data is synthetic and the truth is known."""
    ann = annotations.set_index("feature")
    available_signal = set(ann.index[ann["role"] == "signal"])
    picked = set(selected)
    true_pos = picked & available_signal
    return {"n_selected": len(picked),
            "n_signal_selected": len(true_pos),
            "n_decoys_selected": len(picked - available_signal),
            "precision": round(len(true_pos) / len(picked), 3) if picked else float("nan"),
            "recall": round(len(true_pos) / len(available_signal), 3),
            "decoys_selected": ", ".join(sorted(picked - available_signal)) or "none"}


def twin(blocks_dir: Path = BLOCKS, artifacts_dir: Path = ARTIFACTS,
         repeats: int = CV_REPEATS, verbose: bool = True) -> dict:
    """The Python counterpart: scoreboard, lasso selection, correlations,
    and (if DIABLO has run) the agreement check between the two languages."""
    started = time.time()
    g, m, o = read_blocks(blocks_dir, centred=True)
    annotations = pd.read_csv(artifacts_dir / "feature_annotations.csv") \
        if (artifacts_dir / "feature_annotations.csv").exists() else feature_annotations()
    present = set(g.columns) | set(m.columns)
    annotations = annotations[annotations["feature"].isin(present)]

    board, stability = cross_validate_models(g, m, o, repeats=repeats)
    stability = stability.merge(annotations[["feature", "block", "role", "arsenal"]],
                                on="feature", how="left")
    stability = stability.sort_values("selection_frequency", ascending=False)
    python_signature = stability.loc[stability["selection_frequency"] >= 0.8, "feature"].tolist()

    corr = cross_block_correlations(g, m)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    board.to_csv(artifacts_dir / "python_scoreboard.csv", index=False)
    stability.to_csv(artifacts_dir / "python_selection.csv", index=False)
    corr.to_csv(artifacts_dir / "cross_block_correlation.csv", index=False)

    grades = [{"method": "Python (lasso, picked in >= 80 % of folds)",
               **grade_signature(python_signature, annotations)}]
    diablo_path = artifacts_dir / "diablo_signature.csv"
    agreement = None
    if diablo_path.exists():
        # The DIABLO signature to read is COMPONENT 1 (the R script explains why
        # component 2 is kept only for the 2-D map). "Robust" = picked in at least
        # 80 % of the cross-validation re-fits, the same rule as the lasso above.
        diablo = pd.read_csv(diablo_path)
        comp1 = diablo[diablo["component"] == 1]
        diablo_all = sorted(set(comp1["feature"]))
        diablo_features = sorted(set(comp1.loc[comp1["stability"] >= 0.8, "feature"]))
        grades.insert(0, {"method": "DIABLO comp. 1, robust (picked in >= 80 % of re-fits)",
                          **grade_signature(diablo_features, annotations)})
        grades.insert(0, {"method": "DIABLO comp. 1, everything selected",
                          **grade_signature(diablo_all, annotations)})
        both = set(diablo_features) & set(python_signature)
        either = set(diablo_features) | set(python_signature)
        agreement = {"in_both": len(both), "diablo_only": len(set(diablo_features) - both),
                     "python_only": len(set(python_signature) - both),
                     "jaccard": round(len(both) / len(either), 3) if either else float("nan")}
        pd.DataFrame([agreement]).to_csv(artifacts_dir / "language_agreement.csv", index=False)
    pd.DataFrame(grades).to_csv(artifacts_dir / "signature_report_card.csv", index=False)

    if verbose:
        print("  ── Python counterpart: cross-validated scoreboard ─────────────")
        print(f"  ({CV_FOLDS}-fold cross-validation × {repeats} repeats, same folds for every row; "
              "lower BER is better, higher AUC is better)")
        for _, r in board.iterrows():
            print(f"  {r['approach']:<48} BER {r['ber_mean']:.3f} ± {r['ber_sd']:.3f}   "
                  f"AUC {r['auc_mean']:.3f}")
        print("  ── Signature report card (graded against the planted truth) ───")
        for gr in grades:
            print(f"  {gr['method']:<52} {gr['n_selected']:>2} picked · "
                  f"{gr['n_signal_selected']:>2} true drivers · decoys: {gr['decoys_selected']}")
        if agreement:
            print(f"  ── Two languages, one answer? robust lists share {agreement['in_both']} features; "
                  f"{agreement['diablo_only']} DIABLO-only, {agreement['python_only']} Python-only "
                  f"(overlap score {agreement['jaccard']:.2f})")
        else:
            print("  (DIABLO results not found yet. Run the R step, then `twin` again "
                  "for the two-language agreement check)")
        top = corr[corr["is_producer_pair"]].sort_values("spearman_rho", ascending=False)
        print(f"  gene ↔ own-product correlations: median rho "
              f"{top['spearman_rho'].median():.2f} across {len(top)} producer pairs")
        print(f"  results → {artifacts_dir.relative_to(ROOT) if artifacts_dir.is_relative_to(ROOT) else artifacts_dir}/"
              f"   ({time.time() - started:.0f} s)")
    return {"scoreboard": board, "python_signature": python_signature,
            "agreement": agreement, "grades": grades}


# =============================================================================
# PUBLISH: results into the database, so SQL (and later the app) can use them
# =============================================================================

def publish(artifacts_dir: Path = ARTIFACTS, db_path: Path = DB_PATH,
            verbose: bool = True) -> list[str]:
    """Load every artifacts/integration/*.csv into DuckDB as int_<name>.

    `CREATE OR REPLACE` makes this idempotent. Note the order rule: src/strainscope/harmonize.py
    rebuilds the database from scratch (on purpose: derived results must never
    outlive the data they came from), so re-run `publish` after `harmonize`."""
    import duckdb
    if not db_path.exists():
        sys.exit("No database yet. Run:  python src/strainscope/harmonize.py")
    csvs = sorted(artifacts_dir.glob("*.csv"))
    if not csvs:
        sys.exit("No integration results yet. Run `prepare`, the R step and `twin` first.")
    con = duckdb.connect(str(db_path))
    created = []
    try:
        for csv in csvs:
            table = f"int_{csv.stem}"
            con.execute(f"CREATE OR REPLACE TABLE {table} AS "
                        f"SELECT * FROM read_csv_auto('{csv.as_posix()}', header=true)")
            created.append(table)
    finally:
        con.close()
    if verbose:
        print(f"  published {len(created)} tables into {db_path.relative_to(ROOT) if db_path.is_relative_to(ROOT) else db_path}:")
        for t in created:
            print(f"    {t}")
    return created


# =============================================================================
# THE R STEP, called from Python (for the one-command path)
# =============================================================================

def find_rscript() -> str | None:
    """Locate the Rscript program on any operating system.

    macOS/Linux installers put Rscript on the PATH. The Windows installer does
    NOT, so we also look in the standard install folders, newest first. The
    STRAINSCOPE_RSCRIPT environment variable overrides everything."""
    import os
    override = os.environ.get("STRAINSCOPE_RSCRIPT")
    if override and Path(override).exists():
        return override
    found = shutil.which("Rscript")
    if found:
        return found
    for base in (Path("C:/Program Files/R"), Path.home() / "AppData/Local/Programs/R"):
        if base.exists():
            candidates = sorted(base.glob("R-*/bin/Rscript.exe"), reverse=True)
            if candidates:
                return str(candidates[0])
    return None


def run_r_step() -> bool:
    """Run R/diablo_integration.R from the project root (so renv activates).
    Returns True if it ran successfully, False if R is unavailable or failed."""
    rscript = find_rscript()
    if rscript is None:
        print("  R not found; skipping DIABLO. Everything else still runs (Python-only path).\n"
              "  To include it: install R (docs/01-setup.md, Part I) or set STRAINSCOPE_RSCRIPT.")
        return False
    print(f"  running DIABLO with {rscript} (about 3 minutes) …")
    done = subprocess.run([rscript, str(R_SCRIPT.relative_to(ROOT))], cwd=ROOT)
    if done.returncode != 0:
        print("  the R step failed. Read its message above and see docs/04-integration.md §11.")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="StrainScope Phase 3: multi-omics integration (Python side).")
    parser.add_argument("step", choices=["prepare", "twin", "publish", "all"],
                        help="which step to run (or 'all' for the whole chain)")
    parser.add_argument("--repeats", type=int, default=CV_REPEATS,
                        help="cross-validation repeats for `twin` (default 10)")
    args = parser.parse_args()

    if args.step in ("prepare", "all"):
        prepare()
    if args.step == "all":
        run_r_step()
    if args.step in ("twin", "all"):
        twin(repeats=args.repeats)
    if args.step in ("publish", "all"):
        publish()


if __name__ == "__main__":
    main()
