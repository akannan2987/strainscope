"""
src/strainscope/model.py (StrainScope Phase 4): machine learning, measured carefully.
=====================================================================================

WHAT THIS MODULE DOES (in one sentence)
---------------------------------------
It trains several kinds of prediction model to answer "will this strain be
effective?", scores them all on exactly the same repeated cross-validation
folds without letting any information leak from the test strains, checks
whether their probabilities can be taken at face value (calibration), asks
which features they rely on (graded against the planted truth), studies the
strains they get wrong, and saves the winning model with a model card.

THE VERBS (run them from the project root, venv active)
------------------------------------------------------
    python src/strainscope/model.py compare     # every model x the same 50 folds -> scoreboard
    python src/strainscope/model.py calibrate   # is "80 %" really 80 %? before/after for the winner
    python src/strainscope/model.py explain     # which features matter + which strains are hard
    python src/strainscope/model.py final       # fit the winner on all strains, save model + card
    python src/strainscope/model.py publish     # artifacts/model/*.csv -> DuckDB tables (ml_*)

or all five in order:

    python src/strainscope/model.py all         # about 2-4 minutes on a laptop

WHERE THINGS GO
---------------
  artifacts/model/           small result tables, the model file and its card
                             (committed: the app and the MCP server read them)
  data/processed/strainscope.duckdb   gains ml_* tables after `publish`

THE DECISIONS, WRITTEN DOWN (each is explained in docs/05-machine-learning.md)
-----------------------------------------------------------------------------
1. LEAK-PROOF PREPARATION. Gap filling, the near-constant rule and centring
   within kingdom (Phase 3's rules) are LEARNED from the training strains of
   each fold only, inside a scikit-learn Pipeline, then applied to the test
   strains. Phase 3 prepared all strains at once (a small, label-free leak it
   documented); this phase closes it and measures how small it was.
2. SAME FOLDS FOR EVERY MODEL: 5-fold stratified cross-validation, repeated 10
   times with seed 42, the same yardstick as Phase 3.
3. TUNING INSIDE THE LOOP. The elastic net's one setting (C, how strongly it is
   held back) is chosen by a small inner cross-validation on the training part
   of each fold, never by looking at the test strains ("nested
   cross-validation").
4. RARE WINNERS ARE WEIGHTED UP. Only ~24 % of strains are effective, so every
   model gives the rare class more weight ("class_weight='balanced'"), and the
   main score is the balanced error rate, which a lazy "always no" model
   cannot game.
5. CHOOSE THE SIMPLEST GOOD MODEL. Among models within one standard deviation
   of the best, the simplest wins (the same one-SD rule as Phase 3).
6. CALIBRATE BEFORE TRUSTING PROBABILITIES. Up-weighting the rare class makes
   probabilities too high; the final model is wrapped in Platt scaling
   (method="sigmoid") so "30 %" means about 30 %.
7. JUDGE IMPORTANCE ON UNSEEN STRAINS. Feature importance is measured by
   shuffling one feature at a time in the TEST strains and watching the score
   drop (permutation importance), then graded against the planted truth.
8. OUT-OF-FOLD PREDICTIONS FOR KNOWN STRAINS. The ranking saved for the app uses
   each strain's OUT-OF-FOLD probability (from models that never saw it), not
   the final model's in-sample guess, which would be flattered.

SAFETY NOTE ON THE MODEL FILE
-----------------------------
artifacts/model/strainscope_model.joblib is a Python "pickle": loading one runs
code stored inside it. Only load model files you produced yourself (like this
one, rebuilt by `final`); never load one downloaded from an unknown source.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

# Make `strainscope` importable no matter where the script is run from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strainscope.generate_data import EFFECTIVE_THRESHOLD  # noqa: E402
from strainscope.integrate import (  # noqa: E402  (after the path fix)
    DB_PATH, ROOT, align_blocks, balanced_error_rate, feature_annotations,
    grade_signature, load_clean_tables)

ARTIFACTS = ROOT / "artifacts" / "model"
INTEGRATION = ROOT / "artifacts" / "integration"
MODEL_FILE = ARTIFACTS / "strainscope_model.joblib"
CARD_FILE = ARTIFACTS / "model_card.json"

SEED = 42                     # the project's one seed: same folds as Phase 3
CV_FOLDS, CV_REPEATS = 5, 10  # 5-fold cross-validation, repeated 10 times
NEAR_CONSTANT_SHARE = 0.95    # Phase 3's rule 3
ELASTIC_NET_C = (0.05, 0.2, 1.0)   # the small grid searched INSIDE each fold
TOP_N = 50                    # "if the team can test 50 strains next season ..."
MIN_IMPORTANCE = 0.002        # an AUC drop smaller than this is too small to matter

# The candidate models, simplest first. The order matters for decision 5.
CANDIDATES = ("elastic_net", "random_forest", "gradient_boosting")
MODEL_NAMES = {
    "baseline": "Baseline: always the base rate (no features)",
    "elastic_net": "Elastic net logistic regression (tuned inside each fold)",
    "random_forest": "Random forest (200 trees)",
    "gradient_boosting": "Gradient boosting (histogram-based)",
    "control_shuffled": "Control: shuffled labels (logistic regression)",
}
SIMPLICITY = {
    "elastic_net": "a weighted sum of features you can read line by line",
    "random_forest": "an average of 200 decision trees",
    "gradient_boosting": "a chain of small trees, each correcting the last",
}


# =============================================================================
# 1. LEAK-PROOF PREPARATION: Phase 3's rules, learned per fold
# =============================================================================

class KingdomPrep(TransformerMixin, BaseEstimator):
    """Phase 3's preparation rules as a scikit-learn step that LEARNS from the
    strains it is fitted on and only APPLIES that knowledge to new strains.

    fit(training strains) learns:
      * the gap-filling values per kingdom (most common gene call; median of
        log(1+x) for each metabolite), plus all-strain fallbacks;
      * which features are near-constant (>= 95 % one value) -> dropped;
      * each kingdom's average of every kept feature (for centring).
    transform(any strains) applies exactly those numbers.

    It's like a teacher who sets the marking scheme from last year's papers
    only, then marks this year's exam with it. Setting the scheme while
    peeking at this year's answers would flatter the class, and that's a leak.

    The input is a table with a `kingdom` column plus the raw gene (0/1, may
    be missing) and metabolite (abundance, may be missing) columns (the clean
    tables of Phase 2), so a brand-new strain can be scored as it comes.
    The outcome (effective or not) is never looked at: `y` is ignored.
    """

    def __init__(self, gene_cols=(), metab_cols=(), near_constant_share=NEAR_CONSTANT_SHARE,
                 centre=True):
        self.gene_cols = gene_cols
        self.metab_cols = metab_cols
        self.near_constant_share = near_constant_share
        self.centre = centre

    # -- helpers ---------------------------------------------------------------
    # The work is done on plain numpy arrays: this step is re-learned inside
    # every fold (and every inner fold of the tuning), so it must be quick.
    def _split(self, X: pd.DataFrame):
        if not isinstance(X, pd.DataFrame) or "kingdom" not in X.columns:
            raise ValueError("KingdomPrep needs a table with a 'kingdom' column "
                             "plus the gene and metabolite columns.")
        kingdom = X["kingdom"].astype(str).to_numpy()
        genes = X[list(self.gene_cols)].to_numpy(dtype=float)
        # log(1 + x) for abundances (Phase 3 rule 4); a negative reading is impossible
        metabs = np.log1p(np.clip(X[list(self.metab_cols)].to_numpy(dtype=float), 0, None))
        return kingdom, np.hstack([genes, metabs])

    def _fill(self, kingdom: np.ndarray, values: np.ndarray) -> np.ndarray:
        out = values.copy()
        for k in np.unique(kingdom):
            rows = kingdom == k
            fill = self.fill_.get(k, self.fill_global_)       # unseen kingdom -> all strains
            block = out[rows]
            gaps = np.isnan(block)
            block[gaps] = np.broadcast_to(fill, block.shape)[gaps]
            out[rows] = block
        return out

    def _fill_values(self, values: np.ndarray, n_genes: int) -> np.ndarray:
        """Gap-filling numbers for one group of strains: for a gene (0/1 call) the
        most common value ("carried by more than half"); for a metabolite the median."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # an all-empty column -> NaN
            gene_fill = (np.nanmean(values[:, :n_genes], axis=0) > 0.5).astype(float)
            gene_fill[np.all(np.isnan(values[:, :n_genes]), axis=0)] = np.nan
            metab_fill = np.nanmedian(values[:, n_genes:], axis=0)
        return np.concatenate([gene_fill, metab_fill])

    # -- the scikit-learn interface ---------------------------------------------
    def fit(self, X, y=None):
        kingdom, values = self._split(X)
        n_genes = len(self.gene_cols)
        self.columns_ = list(self.gene_cols) + list(self.metab_cols)
        # all-strain fallback; a column empty for every strain falls back to 0
        self.fill_global_ = np.nan_to_num(self._fill_values(values, n_genes), nan=0.0)
        self.fill_ = {}
        for k in np.unique(kingdom):
            kfill = self._fill_values(values[kingdom == k], n_genes)
            # a column with no readings at all for this kingdom uses the all-strain value
            self.fill_[k] = np.where(np.isnan(kfill), self.fill_global_, kfill)

        filled = self._fill(kingdom, values)
        # Phase 3 rule 3: drop a feature whose single most common value covers
        # >= 95 % of the training strains (it cannot tell strains apart)
        top_share = np.array([np.unique(col, return_counts=True)[1].max() / len(col)
                              for col in filled.T])
        keep = top_share < self.near_constant_share
        self.keep_mask_ = keep
        self.kept_ = [c for c, k in zip(self.columns_, keep) if k]
        self.dropped_ = sorted(c for c, k in zip(self.columns_, keep) if not k)

        kept = filled[:, keep]
        self.centre_global_ = kept.mean(axis=0)
        self.centres_ = {k: kept[kingdom == k].mean(axis=0) for k in np.unique(kingdom)}
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X):
        kingdom, values = self._split(X)
        kept = self._fill(kingdom, values)[:, self.keep_mask_]
        if self.centre:
            for k in np.unique(kingdom):
                rows = kingdom == k
                # a kingdom never seen in training is centred on all strains
                kept[rows] = kept[rows] - self.centres_.get(k, self.centre_global_)
        return kept

    def get_feature_names_out(self, input_features=None):
        return np.asarray(self.kept_, dtype=object)


# =============================================================================
# 2. THE DATA AND THE MODELS
# =============================================================================

def build_dataset(db_path: Path = DB_PATH):
    """The clean tables (Phase 2) as one modelling table.

    Returns (X, y, outcome, gene_cols, metab_cols):
      X        kingdom + raw genes + raw metabolites, one row per strain
      y        1 = effective, 0 = not (numpy array)
      outcome  kingdom, suppression_score, is_effective (for the error analysis)"""
    t = load_clean_tables(db_path)
    g, m, p = align_blocks(t["genomics"], t["metabolomics"], t["phenotype"])
    X = pd.concat([p[["kingdom"]], g, m], axis=1)
    y = p["is_effective"].astype(int).to_numpy()
    outcome = p[["kingdom", "suppression_score", "is_effective"]].copy()
    return X, y, outcome, list(g.columns), list(m.columns)


def _elasticnet_args(l1_ratio: float) -> dict:
    """How to ask THIS scikit-learn for an elastic-net penalty.

    scikit-learn 1.8 retired the `penalty=` switch: newer versions read the mix
    of lasso (L1) and ridge (L2) from `l1_ratio` alone; older versions also
    need `penalty="elasticnet"`. Same model either way; this keeps the code
    working, warning-free, on both (Phase 3 met the same rename for the lasso)."""
    import sklearn
    major, minor = (int(part) for part in sklearn.__version__.split(".")[:2])
    if (major, minor) >= (1, 8):
        return {"l1_ratio": l1_ratio}
    return {"penalty": "elasticnet", "l1_ratio": l1_ratio}


def make_model(key: str, gene_cols, metab_cols, params: dict | None = None):
    """Build one model as a Pipeline: KingdomPrep first, the learner last.

    Putting the preparation INSIDE the pipeline is what makes it leak-proof:
    whenever cross-validation fits the pipeline on a training fold, the
    preparation is re-learned from that fold alone."""
    from sklearn.dummy import DummyClassifier
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GridSearchCV, StratifiedKFold
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    # Import the preparation step by its package name. When this file is run as
    # a script, Python calls it `__main__`; a model saved with that name could
    # only be loaded by this very script. Under its package name,
    # `strainscope.model`, the saved model loads anywhere the project's `src/`
    # folder is importable (the app, the tests).
    from strainscope.model import KingdomPrep as PackagedPrep

    params = params or {}
    prep = ("prep", PackagedPrep(tuple(gene_cols), tuple(metab_cols)))
    if key == "baseline":
        # predicts the training base rate for everyone: the floor to beat
        return Pipeline([prep, ("model", DummyClassifier(strategy="prior"))])
    if key in ("logistic", "control_shuffled"):
        return Pipeline([prep, ("scale", StandardScaler()),
                         ("model", LogisticRegression(C=0.5, class_weight="balanced",
                                                      max_iter=5000))])
    if key == "elastic_net":
        learner = LogisticRegression(**_elasticnet_args(0.5), solver="saga",
                                     C=params.get("C", 0.2), class_weight="balanced",
                                     max_iter=20000, tol=1e-3, random_state=SEED)
        pipe = Pipeline([prep, ("scale", StandardScaler()), ("model", learner)])
        if "C" in params:
            return pipe
        # Nested cross-validation: choose C on the TRAINING strains of each
        # outer fold only, with a small inner 3-fold cross-validation.
        inner = StratifiedKFold(n_splits=3, shuffle=True, random_state=SEED)
        return GridSearchCV(pipe, {"model__C": list(ELASTIC_NET_C)}, cv=inner,
                            scoring="balanced_accuracy")
    if key == "random_forest":
        return Pipeline([prep, ("model", RandomForestClassifier(
            n_estimators=200, min_samples_leaf=2, max_features="sqrt",
            class_weight="balanced_subsample", n_jobs=-1, random_state=SEED))])
    if key == "gradient_boosting":
        return Pipeline([prep, ("model", HistGradientBoostingClassifier(
            learning_rate=0.1, max_iter=100, max_depth=3, min_samples_leaf=20,
            l2_regularization=1.0, class_weight="balanced", random_state=SEED))])
    raise ValueError(f"unknown model key: {key}")


# =============================================================================
# 3. SCORING: the same yardstick for every model
# =============================================================================

METRICS = ("ber", "ber_base_rate", "auc", "ap", "brier", "accuracy")


def fold_metrics(y_true: np.ndarray, prob: np.ndarray, threshold: float = 0.5,
                 base_rate: float | None = None) -> dict:
    """All the scores for one test fold.

    ber       balanced error rate (lower is better; a coin or a lazy model = 0.50),
              flagging a strain when its probability reaches `threshold`
    ber_base_rate  the same, but flagging a strain when its probability beats the
              training base rate (~0.24): "more likely than an average strain".
              Fairer to models whose probabilities rarely climb past 0.5.
    auc       chance an effective strain is ranked above a non-effective one
    ap        average precision: how pure the top of the ranking is (base rate = 0.24)
    brier     mean squared distance between probability and truth (lower is better)
    accuracy  share correct (shown to make the point that it is misleading here)"""
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
    pred = (prob >= threshold).astype(int)
    two_classes = len(np.unique(y_true)) == 2
    out = {"ber": balanced_error_rate(y_true, pred),
            "auc": roc_auc_score(y_true, prob) if two_classes else np.nan,
            "ap": average_precision_score(y_true, prob) if two_classes else np.nan,
            "brier": brier_score_loss(y_true, prob),
            "accuracy": float(np.mean(pred == y_true))}
    if base_rate is not None:
        out["ber_base_rate"] = balanced_error_rate(y_true, (prob >= base_rate).astype(int))
    return out


def summarise(values: list[float], repeats: int, folds: int) -> tuple[float, float]:
    """Mean and standard deviation ACROSS REPEATS (each repeat = the average of
    its folds), the same definition as Phase 3 and mixOmics, so every ± in the
    project measures the same thing: how much the score moves when the folds
    are reshuffled."""
    per_repeat = np.asarray(values, dtype=float).reshape(repeats, folds).mean(axis=1)
    sd = float(per_repeat.std(ddof=1)) if repeats > 1 else float("nan")
    return float(per_repeat.mean()), sd


def expected_calibration_error(y_true: np.ndarray, prob: np.ndarray, bins: int = 10) -> float:
    """Average gap between "what the model said" and "what happened", over ten
    equal-width probability bins, weighted by how many strains fall in each.
    0 = perfectly calibrated."""
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(prob, edges[1:-1]), 0, bins - 1)
    total = 0.0
    for b in range(bins):
        mask = idx == b
        if mask.any():
            total += mask.mean() * abs(prob[mask].mean() - y_true[mask].mean())
    return float(total)


def reliability_table(y_true: np.ndarray, prob: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """The data behind a reliability diagram: per probability bin, the average
    predicted probability, the share that were really effective, and the count."""
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(prob, edges[1:-1]), 0, bins - 1)
    rows = []
    for b in range(bins):
        mask = idx == b
        rows.append({"bin": b + 1, "bin_low": round(edges[b], 2), "bin_high": round(edges[b + 1], 2),
                     "n": int(mask.sum()),
                     "mean_predicted": round(float(prob[mask].mean()), 4) if mask.any() else np.nan,
                     "observed_rate": round(float(y_true[mask].mean()), 4) if mask.any() else np.nan})
    return pd.DataFrame(rows)


def _splits(X: pd.DataFrame, y: np.ndarray, folds: int, repeats: int):
    from sklearn.model_selection import RepeatedStratifiedKFold
    cv = RepeatedStratifiedKFold(n_splits=folds, n_repeats=repeats, random_state=SEED)
    return list(cv.split(X, y))


def _quiet():
    """Silence scikit-learn's convergence chatter inside the loops (results are
    checked by the scores themselves; the tests check the settings converge)."""
    from sklearn.exceptions import ConvergenceWarning
    warnings.filterwarnings("ignore", category=ConvergenceWarning)


# =============================================================================
# 4. COMPARE: every model on the same folds, plus the leak check
# =============================================================================

def compare(db_path: Path = DB_PATH, artifacts_dir: Path = ARTIFACTS,
            folds: int = CV_FOLDS, repeats: int = CV_REPEATS, verbose: bool = True) -> dict:
    """Score every model on exactly the same repeated folds, keep each strain's
    out-of-fold probability, pick the winner, and measure the Phase 3 leak."""
    _quiet()
    started = time.time()
    X, y, outcome, genes, metabs = build_dataset(db_path)
    splits = _splits(X, y, folds, repeats)
    keys = ["baseline", *CANDIDATES, "control_shuffled"]
    scores = {k: {m: [] for m in METRICS} for k in keys}
    oof = {k: np.full((repeats, len(y)), np.nan) for k in keys}
    chosen_c: list[float] = []
    rng = np.random.default_rng(SEED)
    y_shuffles = [rng.permutation(y) for _ in range(repeats)]

    for i, (train, test) in enumerate(splits):
        rep = i // folds
        for key in keys:
            target = y_shuffles[rep] if key == "control_shuffled" else y
            model = make_model(key, genes, metabs).fit(X.iloc[train], target[train])
            prob = model.predict_proba(X.iloc[test])[:, 1]
            for name, value in fold_metrics(target[test], prob,
                                            base_rate=float(target[train].mean())).items():
                scores[key][name].append(value)
            oof[key][rep, test] = prob
            if key == "elastic_net":
                chosen_c.append(model.best_params_["model__C"])

    rows = []
    for key in keys:
        row = {"model_key": key, "model": MODEL_NAMES[key]}
        for name in METRICS:
            mean, sd = summarise(scores[key][name], repeats, folds)
            row[f"{name}_mean"], row[f"{name}_sd"] = round(mean, 4), round(sd, 4)
        rows.append(row)
    board = pd.DataFrame(rows)

    # Decision 5: the simplest candidate within one SD of the best.
    cand = board.set_index("model_key").loc[list(CANDIDATES)]
    best_key = cand["ber_mean"].idxmin()
    limit = cand.loc[best_key, "ber_mean"] + cand.loc[best_key, "ber_sd"]
    winner = next(k for k in CANDIDATES if cand.loc[k, "ber_mean"] <= limit)
    board["is_winner"] = board["model_key"] == winner
    board["n_folds_scored"] = len(splits)

    # Out-of-fold probabilities, one row per strain (mean and spread over repeats).
    oof_table = outcome.reset_index()[["strain_id", "kingdom", "suppression_score", "is_effective"]]
    for key in [*CANDIDATES, "baseline"]:
        oof_table[f"p_{key}"] = np.round(np.nanmean(oof[key], axis=0), 4)
        oof_table[f"p_{key}_sd"] = np.round(np.nanstd(oof[key], axis=0), 4)
        correct = (oof[key] >= 0.5).astype(int) == y[None, :]
        oof_table[f"correct_share_{key}"] = np.round(correct.mean(axis=0), 2)

    c_counts = Counter(chosen_c)
    tuning = pd.DataFrame([{"setting": "C", "value": c, "times_chosen": c_counts.get(c, 0),
                            "share": round(c_counts.get(c, 0) / len(chosen_c), 3)}
                           for c in ELASTIC_NET_C])
    leaks = leak_check(X, y, genes, metabs, splits, folds, repeats)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    board.to_csv(artifacts_dir / "scoreboard.csv", index=False)
    oof_table.to_csv(artifacts_dir / "oof_predictions.csv", index=False)
    tuning.to_csv(artifacts_dir / "tuning_choices.csv", index=False)
    leaks.to_csv(artifacts_dir / "leak_check.csv", index=False)

    if verbose:
        print("  ── Phase 4: the model scoreboard ───────────────────────────────")
        print(f"  ({folds}-fold cross-validation × {repeats} repeats, the same folds for every row;"
              " preparation re-learned inside every fold)")
        print(f"  {'model':<58} {'BER':>13}  {'BER@base':>8}  {'AUC':>5}  {'AP':>5}  "
              f"{'Brier':>5}  {'acc.':>5}")
        for _, r in board.iterrows():
            mark = "  ← winner" if r["is_winner"] else ""
            print(f"  {r['model']:<58} {r['ber_mean']:.3f} ± {r['ber_sd']:.3f}  "
                  f"{r['ber_base_rate_mean']:>8.3f}  {r['auc_mean']:.3f}  {r['ap_mean']:.3f}  "
                  f"{r['brier_mean']:.3f}  {r['accuracy_mean']:.3f}{mark}")
        best_name = MODEL_NAMES[best_key].split(" (")[0]
        print(f"  winner: {MODEL_NAMES[winner].split(' (')[0]} ("
              + ("the best score)" if winner == best_key else
                 f"within one SD of the best, {best_name}, and simpler)")
              + f": {SIMPLICITY[winner]}")
        top_c = max(c_counts, key=c_counts.get)
        print("  elastic net's C chosen inside the folds: "
              + ", ".join(f"{c} ×{c_counts.get(c, 0)}" for c in ELASTIC_NET_C)
              + f"  → final C = {top_c}")
        print("  ── The leak check ───────────────────────────────────────────────")
        for _, r in leaks.iterrows():
            print(f"  {r['setup']:<66} AUC {r['auc_mean']:.3f}   BER {r['ber_mean']:.3f}")
        print(f"  results → {_rel(artifacts_dir)}/   ({time.time() - started:.0f} s)")
    return {"scoreboard": board, "winner": winner, "chosen_c": c_counts, "leak_check": leaks}


def leak_check(X, y, genes, metabs, splits, folds, repeats) -> pd.DataFrame:
    """Measure two kinds of leak on the same folds.

    A. Phase 3's documented leak (label-FREE): the preparation learned from all
       600 strains before splitting, versus re-learned inside each fold.
       Expected: almost no difference, since nothing about the outcome leaked.
    B. A classic label-USING leak, shown on SHUFFLED labels (so there is truly
       nothing to find): pick the 5 features most correlated with the labels
       using ALL strains, then cross-validate, versus picking them inside each
       fold. The leaky version "finds" signal in pure noise; that is what a
       real leak looks like."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    def logistic():
        return make_pipeline(StandardScaler(),
                             LogisticRegression(C=0.5, class_weight="balanced", max_iter=5000))

    def top_k(Z, target, k=5):
        Zc = (Z - Z.mean(axis=0)) / np.where(Z.std(axis=0) == 0, 1, Z.std(axis=0))
        corr = np.abs(Zc.T @ (target - target.mean())) / len(target)
        return np.argsort(corr)[::-1][:k]

    prep_all = KingdomPrep(tuple(genes), tuple(metabs)).fit(X)
    Z_all = prep_all.transform(X)
    rng = np.random.default_rng(SEED + 1)
    y_noise = rng.permutation(y)
    selected_all = top_k(Z_all, y_noise)

    res = {name: {"auc": [], "ber": []} for name in (
        "A1 Phase 3 recipe: prepared on all strains (label-free)",
        "A2 Leak-proof: prepared inside each fold",
        "B1 Noise labels, features picked using ALL strains (a real leak)",
        "B2 Noise labels, features picked inside each fold (correct)")}
    names = list(res)
    for train, test in splits:
        def add(name, prob, truth):
            m = fold_metrics(truth, prob)
            res[name]["auc"].append(m["auc"])
            res[name]["ber"].append(m["ber"])
        add(names[0], logistic().fit(Z_all[train], y[train]).predict_proba(Z_all[test])[:, 1], y[test])
        proper = make_model("logistic", genes, metabs).fit(X.iloc[train], y[train])
        add(names[1], proper.predict_proba(X.iloc[test])[:, 1], y[test])
        add(names[2], logistic().fit(Z_all[train][:, selected_all], y_noise[train])
            .predict_proba(Z_all[test][:, selected_all])[:, 1], y_noise[test])
        prep_fold = KingdomPrep(tuple(genes), tuple(metabs)).fit(X.iloc[train])
        Z_tr, Z_te = prep_fold.transform(X.iloc[train]), prep_fold.transform(X.iloc[test])
        sel = top_k(Z_tr, y_noise[train])
        add(names[3], logistic().fit(Z_tr[:, sel], y_noise[train])
            .predict_proba(Z_te[:, sel])[:, 1], y_noise[test])
    rows = []
    for name in names:
        auc_m, auc_s = summarise(res[name]["auc"], repeats, folds)
        ber_m, ber_s = summarise(res[name]["ber"], repeats, folds)
        rows.append({"setup": name, "auc_mean": round(auc_m, 4), "auc_sd": round(auc_s, 4),
                     "ber_mean": round(ber_m, 4), "ber_sd": round(ber_s, 4)})
    return pd.DataFrame(rows)


# =============================================================================
# 5. CALIBRATE: can the winner's probabilities be taken at face value?
# =============================================================================

def _read(artifacts_dir: Path, name: str) -> pd.DataFrame:
    path = artifacts_dir / name
    if not path.exists():
        sys.exit(f"Missing {_rel(path)}. Run the earlier steps first:\n"
                 "  python src/strainscope/model.py compare")
    return pd.read_csv(path)


def winner_settings(artifacts_dir: Path = ARTIFACTS) -> tuple[str, dict]:
    """The winning model and its final settings, read from `compare`'s outputs.
    For the elastic net, C = the value chosen most often inside the folds."""
    board = _read(artifacts_dir, "scoreboard.csv")
    winner = board.loc[board["is_winner"], "model_key"].iloc[0]
    params: dict = {}
    if winner == "elastic_net":
        tuning = _read(artifacts_dir, "tuning_choices.csv")
        params["C"] = float(tuning.sort_values(["times_chosen", "value"],
                                               ascending=[False, True])["value"].iloc[0])
    return winner, params


def make_calibrated(winner: str, genes, metabs, params: dict):
    """The winner wrapped in Platt scaling ("sigmoid" calibration).

    CalibratedClassifierCV splits its training strains 5 ways, trains the
    model on 4 parts and learns, on the 5th, a smooth S-shaped curve that maps
    the model's raw score to a probability that matches reality. Five such
    pairs are averaged. Everything happens inside the training strains."""
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import StratifiedKFold
    return CalibratedClassifierCV(make_model(winner, genes, metabs, params), method="sigmoid",
                                  cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED))


def calibrate(db_path: Path = DB_PATH, artifacts_dir: Path = ARTIFACTS,
              folds: int = CV_FOLDS, repeats: int = CV_REPEATS, verbose: bool = True) -> dict:
    """Raw winner vs calibrated winner, on the same folds.

    The raw model up-weights the rare class (decision 4), which helps it SORT
    strains but pushes its probabilities up. The calibrated model is scored
    with a decision threshold equal to the training base rate ("more likely
    than an average strain"), which keeps the two classes balanced."""
    _quiet()
    started = time.time()
    X, y, outcome, genes, metabs = build_dataset(db_path)
    winner, params = winner_settings(artifacts_dir)
    splits = _splits(X, y, folds, repeats)
    versions = {"raw": [], "calibrated": []}
    oof = {v: np.full((repeats, len(y)), np.nan) for v in versions}
    pooled = {v: ([], []) for v in versions}

    for i, (train, test) in enumerate(splits):
        rep = i // folds
        base_rate = float(y[train].mean())
        raw = make_model(winner, genes, metabs, params).fit(X.iloc[train], y[train])
        cal = make_calibrated(winner, genes, metabs, params).fit(X.iloc[train], y[train])
        for version, model, thr in (("raw", raw, 0.5), ("calibrated", cal, base_rate)):
            prob = model.predict_proba(X.iloc[test])[:, 1]
            m = fold_metrics(y[test], prob, thr)
            m["ece"] = expected_calibration_error(y[test], prob)
            m["mean_predicted"] = float(prob.mean())
            m["observed_rate"] = float(y[test].mean())
            versions[version].append(m)
            oof[version][rep, test] = prob
            pooled[version][0].extend(y[test])
            pooled[version][1].extend(prob)

    rows, curves = [], []
    for version, ms in versions.items():
        row = {"version": version, "model_key": winner,
               "threshold": "0.5" if version == "raw" else "training base rate"}
        for name in ("ber", "auc", "brier", "ece", "mean_predicted", "observed_rate"):
            mean, sd = summarise([m[name] for m in ms], repeats, folds)
            row[f"{name}_mean"], row[f"{name}_sd"] = round(mean, 4), round(sd, 4)
        rows.append(row)
        pooled_y, pooled_p = np.asarray(pooled[version][0]), np.asarray(pooled[version][1])
        # The calibration error measured once on ALL out-of-fold predictions
        # pooled (6,000 for 10 repeats): far steadier than the per-fold value,
        # which is inflated by noise when only ~120 strains share ten bins.
        row["ece_pooled"] = round(expected_calibration_error(pooled_y, pooled_p), 4)
        table = reliability_table(pooled_y, pooled_p)
        table.insert(0, "version", version)
        curves.append(table)
    summary = pd.DataFrame(rows)
    curve = pd.concat(curves, ignore_index=True)
    cal_oof = outcome.reset_index()[["strain_id", "kingdom", "suppression_score", "is_effective"]]
    cal_oof["p_raw"] = np.round(oof["raw"].mean(axis=0), 4)
    cal_oof["p_calibrated"] = np.round(oof["calibrated"].mean(axis=0), 4)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(artifacts_dir / "calibration_summary.csv", index=False)
    curve.to_csv(artifacts_dir / "calibration_curve.csv", index=False)
    cal_oof.to_csv(artifacts_dir / "calibrated_oof.csv", index=False)

    if verbose:
        r, c = summary.iloc[0], summary.iloc[1]
        print("  ── Calibration: does \"30 %\" mean 30 %? ─────────────────────────")
        print(f"  winner: {_short(winner)}" + (f", final setting C = {params['C']} "
                                               "(the value chosen most often inside the folds)"
                                               if params else ""))
        print(f"  strains really effective in the test folds: {r['observed_rate_mean']:.1%} on average")
        print(f"  raw model        says {r['mean_predicted_mean']:.1%} on average · "
              f"calibration error {r['ece_pooled']:.3f} · Brier {r['brier_mean']:.3f} · "
              f"BER {r['ber_mean']:.3f} (threshold 0.5)")
        print(f"  calibrated model says {c['mean_predicted_mean']:.1%} on average · "
              f"calibration error {c['ece_pooled']:.3f} · Brier {c['brier_mean']:.3f} · "
              f"BER {c['ber_mean']:.3f} (threshold = base rate)")
        print("  (calibration error = average gap between predicted and observed rates, "
              "pooled over all out-of-fold predictions; 0 = perfect)")
        print(f"  ranking quality is unchanged: AUC {r['auc_mean']:.3f} → {c['auc_mean']:.3f}")
        print(f"  results → {_rel(artifacts_dir)}/   ({time.time() - started:.0f} s)")
    return {"summary": summary, "curve": curve, "winner": winner}


# =============================================================================
# 6. EXPLAIN: which features matter, and which strains are hard
# =============================================================================

def permutation_importance_cv(model_key: str, X, y, genes, metabs, params: dict,
                              folds: int = CV_FOLDS, n_permutations: int = 10) -> pd.DataFrame:
    """Shuffle one column at a time in the TEST strains and measure how much
    the AUC drops. A feature the model truly uses hurts when scrambled; a
    feature it ignores does not. One repeat of 5 folds, 10 shuffles each.

    "Reliably important" needs two things:
      * a drop of at least MIN_IMPORTANCE (0.002 AUC): smaller effects exist
        on paper but change no ranking anyone would act on;
      * a drop clearly above zero ACROSS THE FIVE FOLDS (mean minus two
        standard errors > 0). The uncertainty is judged on the five fold
        averages, not on the 50 individual shuffles: shuffles within one fold
        share the same fitted model and test strains, so treating them as 50
        independent measurements would overstate the certainty."""
    from sklearn.inspection import permutation_importance
    per_fold = {col: [] for col in X.columns}
    for train, test in _splits(X, y, folds, 1):
        model = make_model(model_key, genes, metabs, params).fit(X.iloc[train], y[train])
        result = permutation_importance(model, X.iloc[test], y[test], scoring="roc_auc",
                                        n_repeats=n_permutations, random_state=SEED, n_jobs=1)
        for j, col in enumerate(X.columns):
            per_fold[col].append(float(result.importances_mean[j]))
    rows = []
    for col, values in per_fold.items():
        values = np.asarray(values)
        mean, sd = float(values.mean()), float(values.std(ddof=1))
        se = sd / np.sqrt(len(values))
        rows.append({"feature": col, "importance_mean": round(mean, 5),
                     "importance_sd": round(sd, 5),
                     "reliably_important": bool(mean >= MIN_IMPORTANCE and mean - 2 * se > 0)})
    return pd.DataFrame(rows)


def explain(db_path: Path = DB_PATH, artifacts_dir: Path = ARTIFACTS,
            integration_dir: Path = INTEGRATION, folds: int = CV_FOLDS,
            n_permutations: int = 10, verbose: bool = True) -> dict:
    """Feature importance for the winner and for the best tree model, graded
    against the planted truth and compared with Phase 3's DIABLO signature;
    then the error analysis on the winner's out-of-fold predictions."""
    _quiet()
    started = time.time()
    X, y, outcome, genes, metabs = build_dataset(db_path)
    winner, params = winner_settings(artifacts_dir)
    board = _read(artifacts_dir, "scoreboard.csv").set_index("model_key")
    trees = [k for k in ("random_forest", "gradient_boosting") if k != winner]
    tree_key = min(trees, key=lambda k: board.loc[k, "ber_mean"])

    ann = feature_annotations().set_index("feature")
    dropped = KingdomPrep(tuple(genes), tuple(metabs)).fit(X).dropped_
    tables, grades = [], []
    for key, kparams in ((winner, params), (tree_key, {})):
        imp = permutation_importance_cv(key, X, y, genes, metabs, kparams, folds, n_permutations)
        imp.insert(0, "model_key", key)
        imp["role"] = [("context (kingdom label, used for centring)" if f == "kingdom"
                        else ann.loc[f, "role"]) for f in imp["feature"]]
        imp["arsenal"] = [("Kingdom label" if f == "kingdom" else ann.loc[f, "arsenal"])
                          for f in imp["feature"]]
        imp["block"] = [("context" if f == "kingdom" else ann.loc[f, "block"])
                        for f in imp["feature"]]
        imp["dropped_by_preparation"] = imp["feature"].isin(dropped)
        imp = imp.sort_values("importance_mean", ascending=False)
        imp["rank"] = np.arange(1, len(imp) + 1)
        tables.append(imp)
        picked = [f for f in imp.loc[imp["reliably_important"], "feature"] if f != "kingdom"]
        present = ann[~ann.index.isin(dropped)].reset_index()
        grades.append({"method": f"{MODEL_NAMES[key].split(' (')[0]}: reliably important features",
                       **grade_signature(picked, present)})
    importance = pd.concat(tables, ignore_index=True)

    diablo_path = integration_dir / "diablo_signature.csv"
    agreement = {}
    if diablo_path.exists():
        diablo = pd.read_csv(diablo_path)
        diablo_robust = set(diablo.loc[(diablo["component"] == 1) & (diablo["stability"] >= 0.8),
                                       "feature"])
        win = importance[importance["model_key"] == winner]
        model_set = set(win.loc[win["reliably_important"], "feature"]) - {"kingdom"}
        agreement = {"in_both": len(model_set & diablo_robust),
                     "model_only": len(model_set - diablo_robust),
                     "diablo_only": len(diablo_robust - model_set),
                     "model_only_features": ", ".join(sorted(model_set - diablo_robust)) or "none",
                     "diablo_only_features": ", ".join(sorted(diablo_robust - model_set)) or "none"}
        importance["in_phase3_signature"] = importance["feature"].isin(diablo_robust)
    report_card = pd.DataFrame(grades)

    errors, hard = error_analysis(X, y, outcome, _read(artifacts_dir, "oof_predictions.csv"), winner)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    importance.to_csv(artifacts_dir / "feature_importance.csv", index=False)
    report_card.to_csv(artifacts_dir / "importance_report_card.csv", index=False)
    errors.to_csv(artifacts_dir / "error_by_group.csv", index=False)
    hard.to_csv(artifacts_dir / "hard_strains.csv", index=False)
    if agreement:
        pd.DataFrame([agreement]).to_csv(artifacts_dir / "phase3_agreement.csv", index=False)

    if verbose:
        print("  ── What the models rely on (shuffle a feature in unseen strains, watch AUC drop) ─")
        for key in (winner, tree_key):
            top = importance[(importance["model_key"] == key)].head(6)
            print(f"  {MODEL_NAMES[key].split(' (')[0]:<26} top 6: "
                  + ", ".join(f"{f} ({v:.3f})" for f, v in zip(top["feature"], top["importance_mean"])))
        for g in grades:
            print(f"  {g['method']:<58} {g['n_selected']:>2} picked · "
                  f"{g['n_signal_selected']:>2} true drivers · decoys: {g['decoys_selected']}")
        if agreement:
            print(f"  vs Phase 3 (DIABLO robust signature): {agreement['in_both']} shared · "
                  f"{agreement['model_only']} only here ({agreement['model_only_features']}) · "
                  f"{agreement['diablo_only']} only in DIABLO")
        print("  ── Where the winner goes wrong (out-of-fold, majority of 10 repeats) ─")
        margin = errors[errors["group_type"] == "distance from the 65 % cut-off"]
        for _, r in margin.iterrows():
            print(f"  {r['group']:<34} {r['n_errors']:>3} of {r['n_strains']:>3} strains wrong "
                  f"({r['error_rate']:.0%})")
        kingdom_rows = errors[errors["group_type"] == "kingdom"]
        print("  by kingdom: " + " · ".join(f"{r['group']} {r['error_rate']:.0%}"
                                           for _, r in kingdom_rows.iterrows()))
        n_all = int(hard["missed_by_all_models"].sum())
        print(f"  {len(hard)} strains are wrong in at least 8 of 10 repeats; "
              f"{n_all} of them are missed by all three models")
        print(f"  results → {_rel(artifacts_dir)}/   ({time.time() - started:.0f} s)")
    return {"importance": importance, "report_card": report_card, "agreement": agreement,
            "errors": errors, "hard": hard}


def error_analysis(X: pd.DataFrame, y: np.ndarray, outcome: pd.DataFrame,
                   oof: pd.DataFrame, winner: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Which strains does the winner get wrong, and what do they have in common?

    A strain counts as an error when the winner's out-of-fold prediction was
    wrong in the majority of the 10 repeats. Errors are grouped by kingdom, by
    how far the strain's real score sits from the 65 % cut-off that defines
    "effective", and by how many of its readings were missing."""
    oof = oof.set_index("strain_id").loc[outcome.index]
    wrong = oof[f"correct_share_{winner}"].to_numpy() < 0.5
    distance = (outcome["suppression_score"] - EFFECTIVE_THRESHOLD).abs().to_numpy()
    n_missing = X.drop(columns="kingdom").isna().sum(axis=1).to_numpy()
    groups = {
        "kingdom": outcome["kingdom"].to_numpy(),
        f"distance from the {EFFECTIVE_THRESHOLD} % cut-off": pd.cut(
            distance, [0, 2, 5, 10, np.inf], right=False,
            labels=["within 2 points", "2 to 5 points", "5 to 10 points", "more than 10 points"]
        ).astype(str),
        "missing readings": np.where(n_missing == 0, "none", np.where(n_missing == 1, "one",
                                                                       "two or more")),
        "true class": np.where(y == 1, "effective", "not effective"),
    }
    order = {"kingdom": ["Bacteria", "Fungi", "Yeast", "Oomycete"],
             f"distance from the {EFFECTIVE_THRESHOLD} % cut-off":
                 ["within 2 points", "2 to 5 points", "5 to 10 points", "more than 10 points"],
             "missing readings": ["none", "one", "two or more"],
             "true class": ["effective", "not effective"]}
    rows = []
    for gtype, values in groups.items():
        for g in order[gtype]:
            mask = values == g
            if mask.any():
                rows.append({"group_type": gtype, "group": g, "n_strains": int(mask.sum()),
                             "n_errors": int(wrong[mask].sum()),
                             "error_rate": round(float(wrong[mask].mean()), 4)})
    errors = pd.DataFrame(rows)

    shares = oof[[f"correct_share_{k}" for k in CANDIDATES]].to_numpy()
    missed_by_all = (shares < 0.5).all(axis=1)
    hard_mask = oof[f"correct_share_{winner}"].to_numpy() <= 0.2
    hard = pd.DataFrame({
        "strain_id": outcome.index, "kingdom": outcome["kingdom"].to_numpy(),
        "suppression_score": outcome["suppression_score"].to_numpy(),
        "is_effective": y, "probability": oof[f"p_{winner}"].to_numpy(),
        "correct_share": oof[f"correct_share_{winner}"].to_numpy(),
        "distance_to_cutoff": np.round(distance, 2), "n_missing": n_missing,
        "missed_by_all_models": missed_by_all})[hard_mask]
    hard = hard.sort_values("distance_to_cutoff").reset_index(drop=True)
    return errors, hard


# =============================================================================
# 7. FINAL: the winner on all strains, the ranking, the model card
# =============================================================================

def final(db_path: Path = DB_PATH, artifacts_dir: Path = ARTIFACTS, verbose: bool = True) -> dict:
    """Fit the calibrated winner on all 600 strains and save it with its card.

    The ranking written to predictions.csv uses each strain's OUT-OF-FOLD
    calibrated probability (from `calibrate`): for strains we already know,
    that is the number to trust. The saved model is for strains not seen yet."""
    import joblib
    import sklearn
    _quiet()
    started = time.time()
    X, y, outcome, genes, metabs = build_dataset(db_path)
    winner, params = winner_settings(artifacts_dir)
    model = make_calibrated(winner, genes, metabs, params).fit(X, y)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifacts_dir / MODEL_FILE.name, compress=3)

    cal = _read(artifacts_dir, "calibrated_oof.csv").set_index("strain_id").loc[outcome.index]
    base_rate = float(y.mean())
    pred = outcome.reset_index()[["strain_id", "kingdom", "suppression_score", "is_effective"]]
    pred["probability"] = cal["p_calibrated"].to_numpy()
    pred["predicted_effective"] = (pred["probability"] >= base_rate).astype(int)
    pred = pred.sort_values("probability", ascending=False).reset_index(drop=True)
    pred.insert(0, "rank", np.arange(1, len(pred) + 1))
    pred.to_csv(artifacts_dir / "predictions.csv", index=False)

    top = pred.head(TOP_N)
    hits = int(top["is_effective"].sum())
    expected = TOP_N * base_rate
    board = _read(artifacts_dir, "scoreboard.csv").set_index("model_key")
    calib = _read(artifacts_dir, "calibration_summary.csv").set_index("version")
    kept = model.calibrated_classifiers_[0].estimator.named_steps["prep"].kept_
    card = {
        "model": _short(winner), "model_key": winner, "settings": params,
        "settings_chosen_by": "the value chosen most often by the inner cross-validation "
                              "of `compare` (nested cross-validation)",
        "wrapped_in": "CalibratedClassifierCV(method='sigmoid', cv=5)",
        "intended_use": "rank candidate microbial strains for further testing; research use",
        "not_for": "regulatory decisions or any real-world claim (the training data is SIMULATED)",
        "training_data": {"strains": int(len(y)), "effective": int(y.sum()),
                          "base_rate": round(base_rate, 4), "features_used": len(kept),
                          "features_dropped": sorted(set(genes + metabs) - set(kept)),
                          "source": "data/processed/strainscope.duckdb (clean Phase 2 tables)"},
        "decision_threshold": round(base_rate, 4),
        "threshold_meaning": "flag a strain when its calibrated probability exceeds the base rate",
        "cross_validated_performance": {
            "folds": CV_FOLDS,
            "repeats": int(board.loc[winner, "n_folds_scored"]) // CV_FOLDS,
            "ber": board.loc[winner, "ber_mean"], "ber_sd": board.loc[winner, "ber_sd"],
            "auc": board.loc[winner, "auc_mean"], "average_precision": board.loc[winner, "ap_mean"],
            "calibration_error_raw": calib.loc["raw", "ece_pooled"],
            "calibration_error_calibrated": calib.loc["calibrated", "ece_pooled"],
            "brier_calibrated": calib.loc["calibrated", "brier_mean"]},
        "top_n_check": {"n": TOP_N, "truly_effective": hits, "expected_by_chance": round(expected, 1)},
        "input_format": "a table with a 'kingdom' column plus the raw gene and metabolite "
                        "columns of the clean Phase 2 tables; gaps are allowed",
        "versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__,
                     "numpy": np.__version__, "pandas": pd.__version__},
        "seed": SEED,
        "safety": "a joblib/pickle file runs code when loaded, so load only files you built yourself",
    }
    (artifacts_dir / CARD_FILE.name).write_text(json.dumps(card, indent=2, default=float),
                                                encoding="utf-8")
    summary = pd.DataFrame([
        ("model", _short(winner)), ("settings", json.dumps(params)),
        ("strains", len(y)), ("base_rate", round(base_rate, 4)),
        ("features_used", len(kept)), ("cv_ber", board.loc[winner, "ber_mean"]),
        ("cv_ber_sd", board.loc[winner, "ber_sd"]), ("cv_auc", board.loc[winner, "auc_mean"]),
        ("cv_average_precision", board.loc[winner, "ap_mean"]),
        ("ece_raw", calib.loc["raw", "ece_pooled"]),
        ("ece_calibrated", calib.loc["calibrated", "ece_pooled"]),
        ("top_n", TOP_N), ("top_n_truly_effective", hits),
        ("top_n_expected_by_chance", round(expected, 1)),
        ("scikit_learn_version", sklearn.__version__),
        ("model_file_kb", round((artifacts_dir / MODEL_FILE.name).stat().st_size / 1024, 1)),
    ], columns=["key", "value"])
    summary.to_csv(artifacts_dir / "model_summary.csv", index=False)

    if verbose:
        print("  ── The final model ─────────────────────────────────────────────")
        print(f"  {_short(winner)}" + (f", C = {params['C']}" if params else "")
              + ", calibrated (Platt scaling), fitted on all "
              f"{len(y)} strains · {len(kept)} features")
        print(f"  ranking check: of the top {TOP_N} strains (out-of-fold probabilities), "
              f"{hits} are truly effective; chance alone would give {expected:.0f}")
        print(f"  saved → {_rel(artifacts_dir / MODEL_FILE.name)} "
              f"({summary.set_index('key').loc['model_file_kb', 'value']} KB) + "
              f"{_rel(artifacts_dir / CARD_FILE.name)}")
        print(f"  ranking → {_rel(artifacts_dir / 'predictions.csv')}   ({time.time() - started:.0f} s)")
        print("  Reminder: the data is SIMULATED. This proves the workflow, not real-world accuracy.")
    return {"card": card, "predictions": pred}


def load_model(model_path: Path = MODEL_FILE, card_path: Path = CARD_FILE):
    """Load the saved model and its card (used by the app to score uploads).

    The model contains the project's own preparation step, so the folder `src/`
    must be importable (every StrainScope script arranges that at its top).

    Warns when the installed scikit-learn differs from the one that built the
    file: models saved this way are only guaranteed to load in the same
    version. The cure is to rebuild it: `python src/strainscope/model.py final`."""
    import joblib
    import sklearn
    card = json.loads(Path(card_path).read_text(encoding="utf-8"))
    built_with = card.get("versions", {}).get("scikit-learn")
    if built_with != sklearn.__version__:
        warnings.warn(f"model built with scikit-learn {built_with}, running {sklearn.__version__}: "
                      "rebuild it with  python src/strainscope/model.py final", stacklevel=2)
    return joblib.load(model_path), card


def score_strains(table: pd.DataFrame, model=None, card: dict | None = None) -> pd.DataFrame:
    """Calibrated probability that each strain in `table` is effective.

    `table` needs a `kingdom` column and the raw gene/metabolite columns (gaps
    allowed), exactly the format of the clean Phase 2 tables."""
    if model is None:
        model, card = load_model()
    prob = model.predict_proba(table)[:, 1]
    threshold = (card or {}).get("decision_threshold", 0.5)
    return pd.DataFrame({"probability": np.round(prob, 4),
                         "predicted_effective": (prob >= threshold).astype(int)},
                        index=table.index)


# =============================================================================
# 8. PUBLISH: results into the database (ml_* tables)
# =============================================================================

def publish(artifacts_dir: Path = ARTIFACTS, db_path: Path = DB_PATH,
            verbose: bool = True) -> list[str]:
    """Load every artifacts/model/*.csv into DuckDB as ml_<name>.

    Idempotent (`CREATE OR REPLACE`). As in Phase 3: src/strainscope/harmonize.py
    rebuilds the database from scratch, so re-run `publish` after it."""
    import duckdb
    if not db_path.exists():
        sys.exit("No database yet. Run:  python src/strainscope/harmonize.py")
    csvs = sorted(artifacts_dir.glob("*.csv"))
    if not csvs:
        sys.exit("No model results yet. Run:  python src/strainscope/model.py compare")
    con = duckdb.connect(str(db_path))
    created = []
    try:
        for csv in csvs:
            table = f"ml_{csv.stem}"
            con.execute(f"CREATE OR REPLACE TABLE {table} AS "
                        f"SELECT * FROM read_csv_auto('{csv.as_posix()}', header=true)")
            created.append(table)
    finally:
        con.close()
    if verbose:
        print(f"  published {len(created)} tables into {_rel(db_path)}:")
        for t in created:
            print(f"    {t}")
    return created


def _short(key: str) -> str:
    """A model's name without the bracketed detail, e.g. 'Random forest'."""
    return MODEL_NAMES[key].split(" (")[0]


def _rel(path: Path) -> str:
    path = Path(path)
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="StrainScope Phase 4: machine learning, measured carefully.")
    parser.add_argument("step", choices=["compare", "calibrate", "explain", "final", "publish", "all"],
                        help="which step to run (or 'all' for the whole chain)")
    parser.add_argument("--repeats", type=int, default=CV_REPEATS,
                        help="cross-validation repeats for compare/calibrate (default 10)")
    args = parser.parse_args()
    if args.step in ("compare", "all"):
        compare(repeats=args.repeats)
    if args.step in ("calibrate", "all"):
        calibrate(repeats=args.repeats)
    if args.step in ("explain", "all"):
        explain()
    if args.step in ("final", "all"):
        final()
    if args.step in ("publish", "all"):
        publish()


if __name__ == "__main__":
    main()
