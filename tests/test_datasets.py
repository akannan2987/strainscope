"""
tests/test_datasets.py: datasets of your own and the whole workflow on them (Phase 9).
=====================================================================================
src/strainscope/paths.py says where every script reads and writes (the
library, or a dataset's folder); src/strainscope/datasets.py checks three
tables, saves them as a dataset and follows its steps. These tests check that:
  * the library's paths are the ones Phases 1 to 8 always used, and a dataset
    has the same layout inside its own folder;
  * the generator refuses another seed for the library, and makes the same
    data for seed 42 and 600 strains either way;
  * good tables pass the checks, and each kind of mistake gets its own plain
    message with spreadsheet row numbers (a missing column, a bad gene call,
    a comma as decimal mark, a negative level, an unknown kingdom, a bad
    name, too few strains, one class too small, a layer that never varies),
    while strains missing from a table are left out with a warning;
  * a shared copy has lower limits;
  * datasets are saved, listed (on a shared copy only the tab's own), swept
    after an hour, and removed only when the folder really is a dataset;
  * every phase runs on a dataset of your own and writes only into its
    folder: the ranking has every strain, nothing is graded (no answer key),
    the graph's edges say "your data", the model card doesn't call the data
    simulated, and the library's committed results are untouched;
  * the steps are followed: done, to do, and "run again" after an earlier
    step ran later.
One real run of every phase on 120 strains (the workflow_dataset fixture in
tests/conftest.py) takes about a minute and is shared by these tests and the
app's.

Run:  pytest -q tests/test_datasets.py
"""
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strainscope import datasets as ds  # noqa: E402
from strainscope import paths  # noqa: E402
from strainscope import pipeline  # noqa: E402
from strainscope import service as sv  # noqa: E402


def tables(strains: int = 60, seed: int = 3) -> dict[str, pd.DataFrame]:
    """Three tables as they'd be read from CSV files (text), from the generator."""
    return {name: ds.read_table(df.to_csv(index=False).encode())[0] for name, df in ds.example(strains, seed).items()}


def check(t: dict, **kwargs) -> ds.DatasetCheck:
    return ds.check_tables(t["genomics"], t["metabolomics"], t["phenotype"], **kwargs)


def messages(result: ds.DatasetCheck, level: str) -> str:
    return " | ".join(m for lv, m in result.problems if lv == level)


# =============================================================================
# Where things live
# =============================================================================

def test_the_library_keeps_the_paths_of_phases_1_to_8(monkeypatch):
    monkeypatch.delenv(paths.ENV, raising=False)
    f = paths.folders()
    assert f.builtin and f.home is None
    assert f.raw == ROOT / "data" / "raw"
    assert f.db == ROOT / "data" / "processed" / "strainscope.duckdb"
    assert f.blocks == ROOT / "data" / "processed" / "integration"
    assert f.integration == ROOT / "artifacts" / "integration" and f.graph == ROOT / "artifacts" / "graph"
    assert paths.info()["kind"] == "library" and paths.info()["answer_key"] is True


def test_a_dataset_has_the_same_layout_in_its_own_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "DATASETS", tmp_path)
    f = paths.folders("trial")
    assert f.home == (tmp_path / "trial").resolve() and not f.builtin
    assert (f.raw, f.db, f.model) == (f.home / "raw", f.home / "processed" / "strainscope.duckdb",
                                     f.home / "artifacts" / "model")
    assert paths.folders(str(f.home)).home == f.home                        # a full path works too
    monkeypatch.setenv(paths.ENV, "trial")
    assert paths.folders().home == f.home                                   # and the environment variable
    assert paths.child_environment(None)[paths.ENV] == str(f.home)
    assert paths.rel(ROOT / "artifacts" / "model") == "artifacts/model"


def test_the_generator_keeps_the_library_at_seed_42(monkeypatch):
    from strainscope import generate_data as gd
    assert gd.settings([]) == (42, 600)
    with pytest.raises(SystemExit):
        gd.settings(["--seed", "7"])
    a, b = gd.generate(), gd.generate(42, 600)
    for name in a:
        pd.testing.assert_frame_equal(a[name], b[name])
    assert len(gd.generate(7, 80)["phenotype"].drop_duplicates("strain_id")) == 80


# =============================================================================
# The checks
# =============================================================================

def test_good_tables_pass_and_come_back_in_the_library_layout():
    result = check(tables())
    assert result.ok, result.errors
    g, m, p = (result.tables[t] for t in ds.TABLES)
    assert list(p.columns[:2]) == ["strain_id", "kingdom"] and "is_effective" in p.columns
    assert set(g.drop(columns="strain_id").stack().dropna().unique()) <= {0.0, 1.0}
    assert m.drop(columns="strain_id").dtypes.map(pd.api.types.is_float_dtype).all()
    assert result.summary["strains"] == 60 and result.summary["genes"] == 31
    assert "ituA" in result.summary["known_genes"]


def test_each_mistake_gets_its_own_message():
    t = tables()
    t["phenotype"] = t["phenotype"].drop(columns="kingdom")
    assert "needs a `kingdom` column" in messages(check(t), "error")

    t = tables()
    t["genomics"].loc[4, "ituA"] = "maybe"
    assert "Gene column `ituA` must hold 1 or 0" in messages(check(t), "error")
    assert "row 6" in messages(check(t), "error")                      # spreadsheet row: header is row 1

    t = tables()
    t["metabolomics"].loc[0, "iturin"] = "2,5"
    assert "full stop as the decimal mark" in messages(check(t), "error")

    t = tables()
    t["metabolomics"].loc[0, "iturin"] = "-1"
    assert "negative levels" in messages(check(t), "error")

    t = tables()
    t["phenotype"].loc[2, "kingdom"] = "Virus"
    assert "Bacteria, Fungi, Yeast or Oomycete" in messages(check(t), "error")

    t = tables()
    t["genomics"] = t["genomics"].rename(columns={"ituA": "itu-A"})
    assert "can't be used: itu-A" in messages(check(t), "error")

    t = tables()
    t["metabolomics"] = t["metabolomics"].rename(columns={"iturin": "ituA"})
    assert "both a gene and a compound" in messages(check(t), "error")


def test_kingdom_spellings_and_yes_no_are_understood():
    t = tables()
    t["phenotype"]["kingdom"] = t["phenotype"]["kingdom"].str.lower().replace("bacteria", "bacterial")
    t["genomics"]["ituA"] = t["genomics"]["ituA"].replace({"1.0": "yes", "0.0": "no"})
    result = check(t)
    assert result.ok, result.errors
    assert set(result.tables["phenotype"]["kingdom"]) <= set(ds.KINGDOMS)


def test_too_little_to_learn_from_is_refused():
    t = tables(60)
    small = {k: v[v["strain_id"].isin(v["strain_id"].unique()[:30])] for k, v in t.items()}
    assert "needs at least 40" in messages(check(small), "error")

    t = tables(60)
    t["phenotype"] = t["phenotype"].drop(columns="is_effective")
    assert "Each group needs at least 10" in messages(check(t, effective_at=99), "error")

    t = tables(60)
    for c in t["genomics"].columns[1:]:
        t["genomics"][c] = "1"
    assert "nothing to integrate" in messages(check(t), "error")


def test_strains_missing_from_a_table_are_left_out_with_a_warning():
    t = tables(60)
    t["metabolomics"] = t["metabolomics"].iloc[3:]
    result = check(t)
    assert result.ok and "missing from another table" in messages(result, "warning")
    ids = [set(result.tables[n]["strain_id"]) for n in ds.TABLES]
    assert ids[0] == ids[1] == ids[2]


def test_row_numbers_stay_the_files_own_when_strains_are_left_out():
    t = tables(60)
    first = t["phenotype"]["strain_id"].iloc[0]
    t["phenotype"] = t["phenotype"].iloc[1:]                 # the first strain has no trial result
    gene = [c for c in t["genomics"].columns if c != "strain_id"][0]
    t["genomics"].loc[1, gene] = "maybe"                     # the second strain, on spreadsheet row 3
    result = check(t)
    assert not result.ok and first in messages(result, "warning")
    assert f"`{gene}` must hold 1 or 0 (or yes/no); found maybe on row 3." in messages(result, "error")


def test_semicolons_between_values_are_named():
    table, problem = ds.read_table(b"strain_id;kingdom;suppression_score\nS1;Fungi;55,3\n", "phenotype.csv")
    assert table is None and "semicolons" in problem and "comma" in problem
    table, problem = ds.read_table(b"strain_id,kingdom\nS1,Fungi\n")
    assert problem is None and list(table.columns) == ["strain_id", "kingdom"]


def test_missing_optional_columns_are_notes_not_errors():
    t = tables()
    t["phenotype"] = t["phenotype"].drop(columns=["batch_id", "genus", "is_effective"])
    result = check(t)
    notes = messages(result, "note")
    assert result.ok and "no `batch_id`" in notes and "no `genus`" in notes and "no `is_effective`" in notes


def test_a_shared_copy_has_lower_limits():
    t = tables(60)
    extra = pd.DataFrame({f"g{i}": "0" for i in range(120)}, index=t["genomics"].index)
    t["genomics"] = pd.concat([t["genomics"], extra.astype("string")], axis=1)
    assert check(t).ok
    assert "takes up to 100" in messages(check(t, shared=True), "error")


# =============================================================================
# Saving, listing, removing
# =============================================================================

def test_datasets_are_saved_listed_and_removed(tmp_path):
    result = check(tables())
    home = ds.create("trial_1", result.tables, "yours", "a test", base=tmp_path)
    assert {p.name for p in (home / "raw").iterdir()} == {"genomics.csv", "metabolomics.csv", "phenotype.csv"}
    info = json.loads((home / "dataset.json").read_text())
    assert info["kind"] == "yours" and info["answer_key"] is False and info["strains"] == 60
    sim = ds.create("seed7", kind="simulated", seed=7, strains=300, quick=True, base=tmp_path)
    assert paths.info(sim)["repeats"] == ds.QUICK_REPEATS and paths.info(sim)["answer_key"] is True
    assert [d["name"] for d in ds.list_datasets(tmp_path)] in (["seed7", "trial_1"], ["trial_1", "seed7"])
    assert ds.check_name("trial_1", tmp_path) and ds.check_name("library") and ds.check_name("2x")
    assert ds.check_name("fine_name", tmp_path) is None
    with pytest.raises(ValueError):
        ds.remove(tmp_path, tmp_path)                       # not a dataset folder
    ds.remove(home, tmp_path)
    assert not home.exists() and [d["name"] for d in ds.list_datasets(tmp_path)] == ["seed7"]


def test_a_shared_copy_lists_only_the_tabs_own_and_sweeps_old_ones(tmp_path):
    a = ds.create("visit_a", kind="simulated", temporary=True, owner="tab-a", base=tmp_path)
    ds.create("visit_b", kind="simulated", temporary=True, owner="tab-b", base=tmp_path)
    assert [d["name"] for d in ds.list_datasets(tmp_path, owner="tab-a")] == ["visit_a"]
    info = paths.info(a)
    info["last_used"] = "2020-01-01T00:00:00+00:00"
    ds.write_info(a, info)
    assert ds.sweep(tmp_path) == ["visit_a"] and not a.exists()
    assert ds.sweep(tmp_path, max_age_hours=0, busy="visit_b") == []          # never the one in use


# =============================================================================
# Every phase on your own data
# =============================================================================

def test_every_phase_runs_on_your_data_inside_its_folder(workflow_dataset):
    home, output = workflow_dataset
    f = paths.folders(home)
    assert "All 4 steps finished" in output and "the library isn't touched" in output
    pred = pd.read_csv(f.model / "predictions.csv")
    assert len(pred) == 120 and pred["rank"].tolist() == list(range(1, 121))
    card = json.loads((f.model / "model_card.json").read_text())
    assert "SIMULATED" not in card["not_for"] and card["cross_validated_performance"]["repeats"] == ds.QUICK_REPEATS
    report = pd.read_csv(f.integration / "signature_report_card.csv")
    assert report["n_signal_selected"].isna().all()                          # no answer key: nothing graded
    edges = pd.read_csv(f.graph / "edges.csv")
    assert "your data (cleaned in Phase 2)" in set(edges["provenance"])
    assert "synthetic library (Phase 1, cleaned in Phase 2)" not in set(edges["provenance"])
    assert not list(f.integration.glob("diablo_*.csv"))                     # R was switched off
    tables = set(sv.database_tables(f.db)["table"])
    assert {"ml_predictions", "kg_edges", "int_python_scoreboard"} <= tables


def test_a_dataset_run_leaves_the_librarys_results_alone(workflow_dataset):
    from conftest import LIBRARY_FILES
    # every file in artifacts/, figures/ and data/raw/, the same size and untouched since before the run
    assert LIBRARY_FILES["before"] == LIBRARY_FILES["after"]


def test_the_steps_are_followed(workflow_dataset):
    home, _ = workflow_dataset
    steps = ds.progress(home)
    assert [s.script for s in steps] == ["harmonize.py", "integrate.py", "model.py", "graph.py"]
    assert all(s.state == "done" for s in steps) and all(s.seconds is not None for s in steps)
    assert any("winner" in line for line in steps[2].facts)
    ledger = paths.folders(home).processed / "cleaning_ledger.csv"
    table = paths.folders(home).raw / "genomics.csv"
    before = {p: (p.stat().st_atime, p.stat().st_mtime) for p in (ledger, table)}
    later = time.time() + 5
    try:
        os.utime(ledger, (later, later))                   # as if cleaning had run again just now
        states = [s.state for s in ds.progress(home)]
        assert states == ["done", "stale", "stale", "stale"]  # every step after it needs to run again
        os.utime(ledger, before[ledger])
        os.utime(table, (later, later))                    # as if a raw table had been changed in place
        states = [s.state for s in ds.progress(home)]
        assert states == ["stale", "stale", "stale", "stale"]  # cleaning reads it, so everything runs again
    finally:
        for path, times in before.items():
            os.utime(path, times)
    assert all(s.state == "done" for s in ds.progress(home))


def test_the_pipeline_command_chooses_the_dataset_plan(workflow_dataset, tmp_path, capsys):
    home, _ = workflow_dataset
    assert sv.plan_for(home) == "workflow" and sv.plan_for(None) == "everything"
    sim = ds.create("sim", kind="simulated", base=tmp_path)
    assert sv.plan_for(sim) == "simulate"
    assert pipeline.main(["--dataset", str(tmp_path / "nothing_here")]) == 1
    assert "no dataset called" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        pipeline.main(["database", "--dataset", str(home)])
    with pytest.raises(SystemExit):
        pipeline.main(["workflow"])                         # a dataset's plan needs its dataset
    checks = sv.status(paths.folders(home).db, paths.folders(home).artifacts)
    assert all(c.ok is not False for c in checks)


def test_a_forgotten_setting_never_writes_over_your_tables(workflow_dataset, monkeypatch, capsys):
    """STRAINSCOPE_DATASET left set in a terminal: a library plan stops before it
    starts, and the generator refuses a dataset of your own tables."""
    from strainscope import generate_data as gd
    home, _ = workflow_dataset
    raw = paths.folders(home).raw / "phenotype.csv"
    before = raw.read_bytes()
    monkeypatch.setenv(paths.ENV, str(home))
    assert pipeline.main(["database", "--quiet"]) == 1
    out = capsys.readouterr().out
    assert "Nothing was run" in out and f"--dataset {home}" in out and "Remove-Item Env:STRAINSCOPE_DATASET" in out
    assert pipeline.main(["compare"]) == 1
    assert f"compare --dataset {home}" in capsys.readouterr().out
    monkeypatch.setattr(paths, "HERE", paths.folders(home))
    with pytest.raises(SystemExit):
        gd.settings([])
    assert "holds your own tables" in capsys.readouterr().err
    assert raw.read_bytes() == before


def test_plain_words_speak_of_the_dataset(workflow_dataset):
    home, _ = workflow_dataset
    art = paths.folders(home).artifacts
    pred = sv.read_artifact("model/predictions.csv", art)
    words = sv.explain_in_words(pred["strain_id"].iloc[0], art)["text"]
    assert "your trial results" in words and "simulated" not in words


def test_compare_sets_a_datasets_missing_diablo_apart(workflow_dataset):
    if not pipeline.git_ready(ROOT):
        pytest.skip("needs Git")
    home, _ = workflow_dataset
    result = pipeline.compare(ROOT, dataset=home)
    assert "R is installed" in result["skipped"]["integration/diablo_signature.csv"]
    assert "DIABLO didn't run" in result["skipped"]["model/feature_importance.csv"]
    assert "model/predictions.csv" in result["differ"]          # other strains: of course it differs
