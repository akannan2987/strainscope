"""
tests/test_model.py: offline tests for the Phase 4 machine-learning code.
=========================================================================
What they protect, in plain words:
  * the preparation step learns ONLY from the strains it is fitted on, never
    looks at the outcome, fills gaps from each strain's own kingdom, copes
    with a kingdom it has never seen, and drops near-constant features;
  * the scores mean what the guide says they mean (a lazy model scores 0.50,
    a perfectly calibrated model has calibration error 0, the ± is measured
    across repeats);
  * every model keeps its preparation INSIDE the pipeline (the leak-proof rule);
  * the whole chain (compare, calibrate, explain, final, publish) runs end to
    end on a small hand-made database, and the saved model loads again under
    its package name and scores brand-new strains;
  * the figure script and model.py agree on the names of the result files.

None of them needs the network or the real database. The end-to-end test uses
90 hand-made strains and takes a few seconds.

Run:  pytest -q tests/test_model.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strainscope import model as ml  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GENES = ("ituA", "accA", "ssu_rRNA")
METABS = ("iturin", "bg_metabolite_1")


def _table(rows):
    return pd.DataFrame(rows, columns=["kingdom", *GENES, *METABS])


def test_prep_fills_gaps_from_each_strains_own_kingdom():
    X = _table([
        ["Bacteria", 1, 0, 1, np.e - 1, 1.0],
        ["Bacteria", 1, 1, 1, np.e - 1, 1.0],
        ["Bacteria", np.nan, 0, 1, np.nan, 1.0],      # gaps in a bacterium
        ["Fungi", 0, 0, 1, 0.0, 1.0],
        ["Fungi", 0, 1, 1, 0.0, 1.0],
        ["Fungi", np.nan, 0, 1, np.nan, 1.0],         # the same gaps in a fungus
    ])
    prep = ml.KingdomPrep(GENES, METABS, centre=False).fit(X)
    out = pd.DataFrame(prep.transform(X), columns=prep.kept_)
    assert out.loc[2, "ituA"] == 1 and out.loc[5, "ituA"] == 0      # each kingdom's own mode
    assert out.loc[2, "iturin"] == pytest.approx(1.0)                 # median of log(1+x), bacteria
    assert out.loc[5, "iturin"] == pytest.approx(0.0)                 # ... and fungi


def test_prep_drops_near_constant_features_and_centres_within_kingdom():
    X = _table([[k, i % 2, (i // 2) % 2, 1, float(i), 2.0] for i, k in
                enumerate(["Bacteria"] * 4 + ["Fungi"] * 4)])
    prep = ml.KingdomPrep(GENES, METABS).fit(X)
    assert set(prep.dropped_) == {"ssu_rRNA", "bg_metabolite_1"}     # one value for everyone
    Z = prep.transform(X)
    kingdom = X["kingdom"].to_numpy()
    for k in ("Bacteria", "Fungi"):
        assert np.allclose(Z[kingdom == k].mean(axis=0), 0.0)        # centred within kingdom


def test_prep_learns_only_from_the_rows_it_is_fitted_on_and_ignores_the_label():
    rng = np.random.default_rng(1)
    X = _table([[k, rng.integers(0, 2), rng.integers(0, 2), 1, rng.lognormal(), rng.lognormal()]
                for k in ["Bacteria"] * 10 + ["Fungi"] * 10])
    train, test = X.index[::2], X.index[1::2]
    a = ml.KingdomPrep(GENES, METABS).fit(X.loc[train])
    changed = X.copy()
    changed.loc[test, "iturin"] = 1e6                                  # wild values in the test rows
    b = ml.KingdomPrep(GENES, METABS).fit(changed.loc[train])
    assert np.allclose(a.transform(X.loc[train]), b.transform(X.loc[train]))
    y1, y2 = np.zeros(len(train)), np.ones(len(train))
    c = ml.KingdomPrep(GENES, METABS).fit(X.loc[train], y1)
    d = ml.KingdomPrep(GENES, METABS).fit(X.loc[train], y2)
    assert np.allclose(c.transform(X), d.transform(X))                # the outcome is never used


def test_prep_scores_a_kingdom_it_has_never_seen():
    X = _table([[k, i % 2, 1 - i % 2, 1, float(i), float(i)] for i, k in
                enumerate(["Bacteria"] * 4 + ["Fungi"] * 4)])
    prep = ml.KingdomPrep(GENES, METABS).fit(X)
    new = _table([["Archaea", np.nan, 1, 1, np.nan, 3.0]])
    out = prep.transform(new)
    assert out.shape == (1, len(prep.kept_)) and np.isfinite(out).all()


def test_fold_metrics_see_through_a_lazy_model():
    y = np.array([0] * 76 + [1] * 24)
    lazy = np.full(100, 0.2)                     # "never effective", whatever the strain
    m = ml.fold_metrics(y, lazy, base_rate=0.24)
    assert m["ber"] == pytest.approx(0.5) and m["ber_base_rate"] == pytest.approx(0.5)
    assert m["accuracy"] == pytest.approx(0.76)  # looks good, means nothing
    assert m["auc"] == pytest.approx(0.5)


def test_calibration_error_is_zero_when_probabilities_match_reality():
    y = np.array([1, 0, 0, 0, 1, 1, 1, 0])
    prob = np.array([0.25, 0.25, 0.25, 0.25, 0.75, 0.75, 0.75, 0.75])
    assert ml.expected_calibration_error(y, prob) == pytest.approx(0.0)
    table = ml.reliability_table(y, prob)
    assert table["n"].sum() == len(y)
    assert ml.expected_calibration_error(y, np.full(8, 0.9)) == pytest.approx(0.4)


def test_summarise_measures_the_spread_across_repeats():
    values = [0.1, 0.1, 0.3, 0.3]                # 2 repeats x 2 folds
    mean, sd = ml.summarise(values, repeats=2, folds=2)
    assert mean == pytest.approx(0.2) and sd == pytest.approx(np.std([0.1, 0.3], ddof=1))


def test_elasticnet_args_match_the_installed_scikit_learn():
    import sklearn
    major, minor = (int(p) for p in sklearn.__version__.split(".")[:2])
    args = ml._elasticnet_args(0.5)
    assert args["l1_ratio"] == 0.5
    assert ("penalty" in args) == ((major, minor) < (1, 8))


def test_every_model_keeps_its_preparation_inside_the_pipeline():
    for key in ("baseline", "elastic_net", "random_forest", "gradient_boosting", "control_shuffled"):
        model = ml.make_model(key, GENES, METABS)
        pipe = model.estimator if hasattr(model, "estimator") else model   # unwrap the tuner
        assert pipe.steps[0][0] == "prep"
        assert type(pipe.steps[0][1]).__module__ == "strainscope.model"     # loads anywhere


def test_preparation_keeps_its_package_name_even_when_run_as_a_script():
    """Regression test. Run as a script, model.py is called `__main__`; a model
    saved with that name loads nowhere else. make_model must therefore use the
    preparation step under its package name, `strainscope.model`."""
    import runpy
    namespace = runpy.run_path(str(ROOT / "src" / "strainscope" / "model.py"),
                               run_name="__main__script__")
    pipe = namespace["make_model"]("random_forest", GENES, METABS)
    assert type(pipe.steps[0][1]).__module__ == "strainscope.model"


def _small_database(path: Path) -> None:
    """90 hand-made strains in two kingdoms: ituA (and its product iturin)
    drives efficacy; accA and bg_metabolite_1 are decoys; ssu_rRNA is in
    everyone. A few gaps on purpose."""
    import duckdb
    rng = np.random.default_rng(7)
    n = 90
    ids = [f"S{i:03d}" for i in range(n)]
    kingdom = np.array(["Bacteria"] * 45 + ["Fungi"] * 45)
    itua = rng.integers(0, 2, n).astype(float)
    iturin = np.where(itua == 1, rng.lognormal(3, 0.4, n), rng.lognormal(0.5, 0.4, n))
    score = 45 + 22 * itua + 2 * np.log1p(iturin) + rng.normal(0, 4, n)
    genomics = pd.DataFrame({"strain_id": ids, "ituA": itua,
                             "accA": rng.integers(0, 2, n).astype(float), "ssu_rRNA": 1.0})
    genomics.loc[[3, 50], "ituA"] = np.nan
    metabolomics = pd.DataFrame({"strain_id": ids, "iturin": iturin,
                                 "bg_metabolite_1": rng.lognormal(2, 0.5, n)})
    metabolomics.loc[[7, 61], "iturin"] = np.nan
    phenotype = pd.DataFrame({"strain_id": ids, "kingdom": kingdom,
                              "suppression_score": np.round(score, 2),
                              "is_effective": (score >= 65).astype(int)})
    con = duckdb.connect(str(path))
    for name, df in {"genomics": genomics, "metabolomics": metabolomics,
                     "phenotype": phenotype}.items():
        con.register("t", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM t")
        con.unregister("t")
    con.close()


def test_the_whole_chain_runs_end_to_end_and_the_model_reloads(tmp_path):
    import duckdb
    db = tmp_path / "small.duckdb"
    out = tmp_path / "model"
    _small_database(db)

    result = ml.compare(db_path=db, artifacts_dir=out, folds=3, repeats=2, verbose=False)
    assert result["winner"] in ml.CANDIDATES
    board = pd.read_csv(out / "scoreboard.csv").set_index("model_key")
    assert board.loc["baseline", "ber_mean"] == pytest.approx(0.5)
    assert board.loc[result["winner"], "auc_mean"] > 0.8            # the planted signal is found
    assert (out / "leak_check.csv").exists() and (out / "oof_predictions.csv").exists()

    ml.calibrate(db_path=db, artifacts_dir=out, folds=3, repeats=2, verbose=False)
    ml.explain(db_path=db, artifacts_dir=out, integration_dir=tmp_path / "none", folds=3,
               n_permutations=3, verbose=False)
    imp = pd.read_csv(out / "feature_importance.csv")
    winner_imp = imp[imp["model_key"] == result["winner"]].set_index("feature")
    assert winner_imp.loc["ituA", "importance_mean"] > winner_imp.loc["accA", "importance_mean"]

    ml.final(db_path=db, artifacts_dir=out, verbose=False)
    model, card = ml.load_model(out / "strainscope_model.joblib", out / "model_card.json")
    assert card["training_data"]["strains"] == 90
    new = pd.DataFrame([{"kingdom": "Fungi", "ituA": 1.0, "accA": 0.0, "ssu_rRNA": 1.0,
                         "iturin": 30.0, "bg_metabolite_1": 5.0},
                        {"kingdom": "Fungi", "ituA": 0.0, "accA": 0.0, "ssu_rRNA": 1.0,
                         "iturin": 1.0, "bg_metabolite_1": 5.0}])
    scored = ml.score_strains(new, model, card)
    assert scored["probability"].between(0, 1).all()
    assert scored.loc[0, "probability"] > scored.loc[1, "probability"]   # the carrier ranks higher

    created = ml.publish(artifacts_dir=out, db_path=db, verbose=False)
    again = ml.publish(artifacts_dir=out, db_path=db, verbose=False)     # idempotent
    assert created == again and "ml_scoreboard" in created
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM ml_predictions").fetchone()[0] == 90
    finally:
        con.close()


def test_figure_script_reads_only_files_that_model_py_writes():
    """The contract between the two scripts: every artifacts/model file the
    figure script reads must be one that model.py writes."""
    import re
    fig_code = (ROOT / "figures" / "make_phase4_figures.py").read_text(encoding="utf-8")
    model_code = (ROOT / "src" / "strainscope" / "model.py").read_text(encoding="utf-8")
    read = set(re.findall(r'MODEL_DIR / "([a-z_]+\.(?:csv|json))"', fig_code))
    assert read, "the figure script should read result files"
    missing = sorted(name for name in read if name not in model_code)
    assert not missing, f"figure script reads files model.py never writes: {missing}"
