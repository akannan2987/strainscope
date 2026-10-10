"""
tests/test_integrate.py — offline tests for the Phase 3 integration code.
=========================================================================

Each test builds a TINY hand-made table, runs ONE function on it, and checks
the result. No R, no network, no real data — they run in about a second on any
machine, which is what lets them guard every future change.

One test is special: `test_r_and_python_agree_on_the_handoff_files` checks
that the file names Python WRITES are exactly the ones the R script READS.
That "contract" between two languages is the most fragile joint in the phase,
so it gets its own guard.

Run (from the project root, venv active):
    pytest -q
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strainscope import integrate as ig  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_align_blocks_orders_rows_identically():
    g = pd.DataFrame({"x": [1, 2]}, index=["S2", "S1"])
    m = pd.DataFrame({"y": [3, 4]}, index=["S1", "S2"])
    p = pd.DataFrame({"kingdom": ["Fungi", "Yeast"]}, index=["S1", "S2"])
    g2, m2, p2 = ig.align_blocks(g, m, p)
    assert list(g2.index) == list(m2.index) == list(p2.index) == ["S1", "S2"]
    assert g2.loc["S2", "x"] == 1                      # values travel with their strain


def test_align_blocks_refuses_mismatched_strains():
    g = pd.DataFrame({"x": [1]}, index=["S1"])
    m = pd.DataFrame({"y": [1]}, index=["S2"])
    p = pd.DataFrame({"kingdom": ["Fungi"]}, index=["S1"])
    with pytest.raises(ValueError, match="not present in every table"):
        ig.align_blocks(g, m, p)


def test_impute_within_kingdom_uses_each_kingdoms_own_values():
    kingdom = pd.Series(["A", "A", "A", "B", "B", "B"])
    genes = pd.DataFrame({"g": [1, 1, np.nan, 0, 0, np.nan]})
    chem = pd.DataFrame({"c": [10.0, 30.0, np.nan, 1.0, 3.0, np.nan]})
    g_filled, n_g = ig.impute_within_kingdom(genes, kingdom, binary=True)
    c_filled, n_c = ig.impute_within_kingdom(chem, kingdom, binary=False)
    assert g_filled["g"].tolist() == [1, 1, 1, 0, 0, 0]        # kingdom A says 1, B says 0
    assert c_filled["c"].tolist() == [10, 30, 20, 1, 3, 2]     # kingdom medians
    assert (n_g, n_c) == (2, 2)                                # the ledger counts


def test_near_constant_features_flags_only_the_uninformative():
    block = pd.DataFrame({"housekeeping": [1] * 97 + [0] * 3,     # 97 % the same
                          "useful": [1] * 60 + [0] * 40})
    assert ig.near_constant_features(block) == ["housekeeping"]


def test_centre_within_kingdom_zeroes_each_kingdoms_average():
    kingdom = pd.Series(["A", "A", "B", "B"])
    block = pd.DataFrame({"x": [1.0, 3.0, 10.0, 30.0]})
    out = ig.centre_within_kingdom(block, kingdom)
    assert out["x"].tolist() == [-1.0, 1.0, -10.0, 10.0]


def test_balanced_error_rate_sees_through_a_lazy_classifier():
    y = np.array([0] * 76 + [1] * 24)                  # 24 % effective, like ours
    lazy = np.zeros_like(y)                            # always "not effective"
    assert ig.balanced_error_rate(y, lazy) == 0.5      # a coin, not 76 % accurate
    assert ig.balanced_error_rate(y, y) == 0.0


def test_grade_signature_counts_true_drivers_and_decoys():
    ann = pd.DataFrame({"feature": ["a", "b", "c", "d"],
                        "role": ["signal", "signal", "decoy", "decoy"]})
    grade = ig.grade_signature(["a", "c"], ann)
    assert grade["n_signal_selected"] == 1 and grade["n_decoys_selected"] == 1
    assert grade["precision"] == 0.5 and grade["recall"] == 0.5
    assert grade["decoys_selected"] == "c"


def test_cross_block_correlations_find_a_gene_and_its_product():
    g = pd.DataFrame({"ituA": [0, 0, 1, 1, 1], "accA": [1, 0, 1, 0, 1]})
    m = pd.DataFrame({"iturin": [0.1, 0.2, 5.0, 6.0, 7.0]})
    corr = ig.cross_block_correlations(g, m).set_index(["gene", "metabolite"])
    assert corr.loc[("ituA", "iturin"), "spearman_rho"] > 0.8
    assert bool(corr.loc[("ituA", "iturin"), "is_producer_pair"]) is True
    assert bool(corr.loc[("accA", "iturin"), "is_producer_pair"]) is False


def test_feature_annotations_know_the_planted_truth():
    ann = ig.feature_annotations().set_index("feature")
    assert ann.loc["ituA", "role"] == "signal" and ann.loc["ituA", "arsenal"] == "Bacteria"
    assert ann.loc["kilT", "arsenal"] == "Yeast"
    assert ann.loc["chiA", "arsenal"] == "Cross-kingdom"
    assert ann.loc["accA", "role"] == "decoy"
    assert ann.loc["iturin", "producer_gene"] == "ituA"


def test_lasso_args_match_the_installed_scikit_learn():
    args = ig._lasso_args()
    assert args in ({"l1_ratio": 1.0}, {"penalty": "l1"})


def test_find_rscript_honours_the_override(tmp_path, monkeypatch):
    fake = tmp_path / "Rscript.exe"
    fake.write_text("")
    monkeypatch.setenv("STRAINSCOPE_RSCRIPT", str(fake))
    assert ig.find_rscript() == str(fake)


def _tiny_database(path: Path) -> None:
    """A 12-strain stand-in for the real database, with gaps on purpose."""
    import duckdb
    rng = np.random.default_rng(0)
    ids = [f"S{i:02d}" for i in range(12)]
    genomics = pd.DataFrame({"strain_id": ids, "ituA": rng.integers(0, 2, 12).astype(float),
                             "ssu_rRNA": [1.0] * 12, "accA": rng.integers(0, 2, 12)})
    genomics.loc[3, "ituA"] = np.nan
    metabolomics = pd.DataFrame({"strain_id": ids, "iturin": rng.lognormal(1, 1, 12),
                                 "bg_metabolite_1": rng.lognormal(2, 0.5, 12)})
    metabolomics.loc[5, "iturin"] = np.nan
    phenotype = pd.DataFrame({"strain_id": ids, "kingdom": ["Bacteria"] * 6 + ["Fungi"] * 6,
                              "is_effective": [1, 0, 0, 1, 0, 0] * 2,
                              "suppression_score": rng.uniform(20, 90, 12)})
    con = duckdb.connect(str(path))
    for name, df in {"genomics": genomics, "metabolomics": metabolomics,
                     "phenotype": phenotype}.items():
        con.register("t", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM t")
        con.unregister("t")
    con.close()


def test_prepare_writes_blocks_and_ledger_end_to_end(tmp_path):
    db = tmp_path / "tiny.duckdb"
    _tiny_database(db)
    summary = ig.prepare(db_path=db, blocks_dir=tmp_path / "blocks",
                         artifacts_dir=tmp_path / "art", verbose=False)
    assert summary["dropped"]["genomics"] == ["ssu_rRNA"]       # 100 % constant
    assert summary["imputed_gene_cells"] == 1 and summary["imputed_metabolite_cells"] == 1
    g = pd.read_csv(tmp_path / "blocks" / "block_genomics_centred.csv", index_col=0)
    assert g.notna().all().all() and list(g.columns) == ["ituA", "accA"]
    assert (tmp_path / "art" / "prepare_ledger.csv").exists()


def test_publish_loads_every_result_table(tmp_path):
    import duckdb
    db = tmp_path / "tiny.duckdb"
    _tiny_database(db)
    art = tmp_path / "art"
    art.mkdir()
    pd.DataFrame({"approach": ["x"], "ber_mean": [0.2]}).to_csv(art / "python_scoreboard.csv",
                                                               index=False)
    tables = ig.publish(artifacts_dir=art, db_path=db, verbose=False)
    assert tables == ["int_python_scoreboard"]
    con = duckdb.connect(str(db), read_only=True)
    assert con.execute("SELECT ber_mean FROM int_python_scoreboard").fetchone()[0] == 0.2
    con.close()
    assert ig.publish(artifacts_dir=art, db_path=db, verbose=False) == tables  # idempotent


def test_r_and_python_agree_on_the_handoff_files():
    r_code = (ROOT / "R" / "diablo_integration.R").read_text(encoding="utf-8")
    for name in ("block_genomics.csv", "block_metabolomics.csv",
                 "block_genomics_centred.csv", "block_metabolomics_centred.csv",
                 "outcome.csv"):
        assert name in r_code, f"R script no longer reads {name}"
    # …and what R WRITES is what Python (the twin and the figures) READS.
    py_code = (ROOT / "src" / "strainscope" / "integrate.py").read_text(encoding="utf-8")
    fig_code = (ROOT / "figures" / "make_phase3_figures.py").read_text(encoding="utf-8")
    assert "diablo_signature.csv" in r_code and "diablo_signature.csv" in py_code
    for name in ("diablo_sample_scores.csv", "diablo_error_by_component.csv",
                 "diablo_summary.csv"):
        assert name in r_code and name in fig_code, f"{name} is not shared by R and the figures"
