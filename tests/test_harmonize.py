"""
test_harmonize.py — offline tests for the Phase 2 cleaning functions.
=====================================================================

Each test builds a TINY hand-made dirty table, runs ONE cleaning function on
it, and checks the outcome — including the ledger counts, because "the ledger
tells the truth" is itself behaviour worth guarding. (It was the ledger that
caught this phase's biggest bug: a textbook outlier fence that would have
flattened real biology. See cap_outliers' docstring.)

Run (from the project root, venv active):
    pytest -q
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strainscope.harmonize import (                     # noqa: E402
    Ledger, cap_outliers, clip_impossible_scores, correct_batch_effect,
    drop_duplicate_strains, harmonize_text, load_to_duckdb)


def test_drop_duplicates_keeps_first_and_counts():
    df = pd.DataFrame({"strain_id": ["S1", "S2", "S1"], "x": [1, 2, 99]})
    led = Ledger()
    out = drop_duplicate_strains(df, "genomics", led)
    assert list(out["strain_id"]) == ["S1", "S2"]
    assert out.loc[0, "x"] == 1                       # first occurrence kept
    assert led.entries[0]["rows_in"] == 3 and led.entries[0]["rows_out"] == 2


def test_harmonize_text_fixes_space_case_and_typo():
    df = pd.DataFrame({
        "strain_id": ["S1", "S2", "S3"],
        "genus": ["Psuedomonas", "trichoderma", "Bacillus "],
        "collection_site": [" rhizosphere", "Soil", "ENDOSPHERE "]})
    led = Ledger()
    out = harmonize_text(df, led)
    assert list(out["genus"]) == ["Pseudomonas", "Trichoderma", "Bacillus"]
    assert list(out["collection_site"]) == ["rhizosphere", "soil", "endosphere"]
    assert led.entries[0]["cells_changed"] == 6       # every cell was dirty


def test_clip_impossible_scores_bounds_and_counts():
    df = pd.DataFrame({"strain_id": ["S1", "S2", "S3"],
                       "suppression_score": [-2.0, 55.0, 104.5]})
    led = Ledger()
    out = clip_impossible_scores(df, led)
    assert out["suppression_score"].tolist() == [0.0, 55.0, 100.0]
    assert led.entries[0]["cells_changed"] == 2


def test_cap_outliers_spares_the_bimodal_high_mode():
    # 10 trace values (~1), 5 real producers (~20) and ONE absurd spike (500).
    # A bimodality-safe rule must cap the spike and leave the producers alone.
    values = [1.0] * 10 + [20.0, 21.0, 22.0, 23.0, 24.0] + [500.0]
    df = pd.DataFrame({"strain_id": [f"S{i}" for i in range(16)], "m": values})
    led = Ledger()
    out = cap_outliers(df, ["m"], led)
    assert out["m"].max() < 500                        # the spike was capped
    assert (out["m"] >= 20).sum() >= 5                 # producers untouched
    assert led.entries[0]["cells_changed"] == 1


def test_correct_batch_effect_equalises_batch_medians():
    # Batch 2 runs exactly 2x hot; after correction the medians should agree.
    df = pd.DataFrame({"strain_id": [f"S{i}" for i in range(8)],
                       "m": [10, 12, 11, 13, 20, 24, 22, 26]})
    batch = pd.Series([1, 1, 1, 1, 2, 2, 2, 2])
    led = Ledger()
    out = correct_batch_effect(df, batch, ["m"], led)
    med1 = out.loc[batch == 1, "m"].median()
    med2 = out.loc[batch == 2, "m"].median()
    assert abs(med1 - med2) < 1.0                      # drift removed


def test_load_to_duckdb_creates_tables_and_autoloads_real(tmp_path, monkeypatch):
    import strainscope.harmonize as hz
    # Point the module at a throwaway real/ folder with one CSV in it.
    real_dir = tmp_path / "real"; real_dir.mkdir()
    (real_dir / "real_demo.csv").write_text("a,b\n1,x\n2,y\n")
    monkeypatch.setattr(hz, "REAL", real_dir)
    clean = {"phenotype": pd.DataFrame({"strain_id": ["S1"], "kingdom": ["Fungi"]})}
    tables = load_to_duckdb(clean, db_path=tmp_path / "test.duckdb")
    assert "phenotype" in tables and "real_demo" in tables


def test_load_to_duckdb_is_idempotent(tmp_path):
    clean = {"phenotype": pd.DataFrame({"strain_id": ["S1"]})}
    db = tmp_path / "test.duckdb"
    t1 = load_to_duckdb(clean, db_path=db)
    t2 = load_to_duckdb(clean, db_path=db)             # second run: no error,
    assert t1 == t2                                    # identical result


def test_sql_console_run_query_reads_the_database(tmp_path):
    # The console's engine must answer a query against a freshly built DB —
    # read-only, so it can never modify or lock what the pipeline builds.
    from strainscope.sql import run_query
    clean = {"phenotype": pd.DataFrame({"strain_id": ["S1", "S2"],
                                        "is_effective": [1, 0]})}
    db = tmp_path / "t.duckdb"
    load_to_duckdb(clean, db_path=db)
    df = run_query("SELECT SUM(is_effective)::INT AS eff FROM phenotype", db_path=db)
    assert df["eff"].iloc[0] == 1
