"""
tests/test_pipeline.py: the one-command pipeline (Phase 8).
============================================================
src/strainscope/pipeline.py runs the scripts of Phases 1 to 5 in order and
can compare the rebuilt results with the committed ones. These tests check
that:
  * every plan names scripts that exist, and `everything` runs Phases 1 to 5
    in the right order with their `all` steps;
  * a run prints each step and a summary, `--from` starts later, a failing
    step stops the rest and says how to carry on, `--quiet` still shows the
    end of a failed step, and Ctrl+C stops the running step;
  * `compare` finds a changed number, forgives rounding, leaves out the lines
    that describe the computer, says why it skipped what it skipped, lists
    every difference with --all, and on an ARM processor sets the random
    forest's numbers apart;
  * the committed result tables put ties in a fixed order, so a rebuild on
    any processor writes them the same way;
  * the app's Data page offers the rebuild on your own computer only.
The tests run tiny stand-in steps instead of the real scripts, so they take
seconds and never touch the results in artifacts/.

Run:  pytest -q tests/test_pipeline.py
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strainscope import pipeline  # noqa: E402
from strainscope import service as sv  # noqa: E402

HAS_GIT = shutil.which("git") is not None


@pytest.fixture()
def stand_in_steps(monkeypatch):
    """Replace each step's command with a tiny Python one-liner. A step whose
    script name contains 'fail' exits with code 3; 'slow' sleeps."""
    def command(step):
        name = step[0]
        if "fail" in name:
            code = "print('checking'); print('something is wrong'); raise SystemExit(3)"
        elif "slow" in name:
            code = "import time; print('working', flush=True); time.sleep(30)"
        else:
            code = f"print('ran {name}')"
        return [sys.executable, "-c", code]
    monkeypatch.setattr(sv, "step_command", command)

    def plan(*names):
        monkeypatch.setitem(sv.PIPELINES, "test", {"title": "A test plan", "takes": "a moment",
                                                   "what": "runs stand-in steps",
                                                   "steps": [(n,) for n in names]})
        return "test"
    return plan


# =============================================================================
# The plans
# =============================================================================

def test_every_step_names_a_script_that_exists():
    for name, spec in sv.PIPELINES.items():
        for step in spec["steps"]:
            assert (ROOT / "src" / "strainscope" / step[0]).exists(), f"{name}: {step[0]}"


def test_everything_runs_phases_1_to_5_in_order():
    assert sv.PIPELINES["everything"]["steps"] == [
        ("generate_data.py",), ("harmonize.py",), ("integrate.py", "all"), ("model.py", "all"), ("graph.py", "all")]
    assert list(sv.PIPELINES)[0] == "everything"


def test_list_shows_every_plan_and_step(capsys):
    assert pipeline.main(["--list"]) == 0
    out = capsys.readouterr().out
    for name, spec in sv.PIPELINES.items():
        assert f"\n  {name}" in out
        for step in spec["steps"]:
            assert sv.step_label(step) in out
    assert "everything (the default)" in out and "compare:" in out


# =============================================================================
# Running a plan
# =============================================================================

def test_a_run_prints_each_step_and_a_summary(stand_in_steps, capsys):
    plan = stand_in_steps("one.py", "two.py", "three.py")
    assert pipeline.run(plan) == 0
    out = capsys.readouterr().out
    assert "[1/3] python src/strainscope/one.py" in out and "ran two.py" in out
    assert out.count("✓ step") == 3 and "All 3 steps finished in" in out
    assert "what the app can read" in out          # the health check comes last


def test_from_starts_at_a_later_step(stand_in_steps, capsys):
    plan = stand_in_steps("one.py", "two.py", "three.py")
    assert pipeline.run(plan, start=2) == 0
    out = capsys.readouterr().out
    assert "ran one.py" not in out and "ran three.py" in out and "Steps 2 to 3 finished in" in out


def test_a_failing_step_stops_the_rest_and_says_how_to_carry_on(stand_in_steps, capsys):
    plan = stand_in_steps("one.py", "fail.py", "three.py")
    assert pipeline.run(plan, quiet=True) == 1
    out = capsys.readouterr().out
    assert "ran three.py" not in out and "[3/3]" not in out
    assert "✗ Step 2 (python src/strainscope/fail.py) stopped with exit code 3" in out
    assert "--from 2" in out
    assert "something is wrong" in out             # --quiet still shows the end of the failed step


def test_quiet_hides_what_the_steps_print(stand_in_steps, capsys):
    plan = stand_in_steps("one.py")
    assert pipeline.run(plan, quiet=True) == 0
    assert "ran one.py" not in capsys.readouterr().out


def test_from_outside_the_plan_is_refused(capsys):
    with pytest.raises(SystemExit) as stop:
        pipeline.main(["database", "--from", "9"])
    assert stop.value.code == 2 and "1 to 5" in capsys.readouterr().err
    with pytest.raises(ValueError):
        next(sv.pipeline_events("database", start=0))


def test_ctrl_c_stops_the_run_and_says_where(stand_in_steps, monkeypatch, capsys):
    plan = stand_in_steps("one.py", "two.py")

    def interrupted(name, root, start, dataset=None):
        yield {"event": "start", "step": 1, "label": "python src/strainscope/one.py"}
        raise KeyboardInterrupt
    monkeypatch.setattr(sv, "pipeline_events", interrupted)
    assert pipeline.run(plan) == 130
    assert "Stopped by you during step 1" in capsys.readouterr().out


def test_stopping_halfway_stops_the_step_and_frees_the_lock(stand_in_steps):
    plan = stand_in_steps("slow.py")
    events = sv.pipeline_events(plan)
    assert next(events)["event"] == "start" and next(events)["text"] == "working"
    started = time.time()
    events.close()                                   # what Ctrl+C does to the generator
    assert time.time() - started < 10
    assert sv._PIPELINE_LOCK.acquire(blocking=False)
    sv._PIPELINE_LOCK.release()


# =============================================================================
# compare: rebuilt results against the committed ones
# =============================================================================

def test_numbers_match_within_the_tolerance():
    assert pipeline.same_cell("0.9211", "0.9212") and pipeline.same_cell("abc", "abc")
    assert pipeline.same_cell("nan", "nan") and pipeline.same_cell("", "")
    assert not pipeline.same_cell("0.9211", "0.9311") and not pipeline.same_cell("fenA", "ituA")


def test_compare_tables_names_the_row_and_column():
    old = "strain_id,probability\nSTRAIN_0001,0.5\nSTRAIN_0002,0.25\n"
    assert pipeline.compare_tables(old, old) == []
    assert pipeline.compare_tables(old, old.replace("0.25", "0.2504")) == []
    problems = pipeline.compare_tables(old, old.replace("0.25", "0.35"))
    assert problems == ["row 2 (STRAIN_0002), probability: 0.25 committed, 0.35 now"]
    assert "rows committed" in pipeline.compare_tables(old, old + "STRAIN_0003,0.1\n")[0]
    summary = "key,value\nseed,42\nruntime_seconds,253\n"
    assert pipeline.compare_tables(summary, summary.replace("253", "301"), {"runtime_seconds"}) == []


def test_compare_json_leaves_out_the_package_versions():
    card = {"model": "Elastic net", "versions": {"numpy": "2.5.2"}, "top_n_check": {"truly_effective": 47}}
    other = {**card, "versions": {"numpy": "2.5.4"}}
    assert pipeline.compare_json(json.dumps(card), json.dumps(other)) == []
    worse = {**card, "top_n_check": {"truly_effective": 45}}
    assert pipeline.compare_json(json.dumps(card), json.dumps(worse)) == ["top_n_check.truly_effective: 47 committed, 45 now"]


@pytest.mark.skipif(not HAS_GIT, reason="needs Git")
def test_compare_reads_the_committed_files_from_git(tmp_path):
    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=tmp_path,
                       check=True, capture_output=True)
    files = {"artifacts/model/scoreboard.csv": "model_key,auc_mean\nelastic_net,0.948\n",
             "artifacts/model/model_summary.csv": "key,value\nmodel_file_kb,18.9\n",
             "artifacts/graph/nodes.csv": "node_id,label\nstrain:STRAIN_0001,STRAIN_0001\n",
             "artifacts/model/strainscope_model.joblib": "bytes"}
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "results")
    assert pipeline.git_ready(tmp_path)
    (tmp_path / "artifacts/model/model_summary.csv").write_text("key,value\nmodel_file_kb,18.8\n", encoding="utf-8")
    (tmp_path / "artifacts/model/new.csv").write_text("a\n1\n", encoding="utf-8")
    result = pipeline.compare(tmp_path, tmp_path / "no.duckdb")
    assert result["differ"] == {}
    assert sorted(result["matched"]) == ["model/model_summary.csv", "model/scoreboard.csv"]
    assert "real reference data" in result["skipped"]["graph/nodes.csv"]
    assert "package versions" in result["skipped"]["model/strainscope_model.joblib"]
    assert "new file" in result["skipped"]["model/new.csv"]
    (tmp_path / "artifacts/model/scoreboard.csv").write_text("model_key,auc_mean\nelastic_net,0.900\n", encoding="utf-8")
    result = pipeline.compare(tmp_path, tmp_path / "no.duckdb")
    assert result["differ"] == {"model/scoreboard.csv": ["row 1 (elastic_net), auc_mean: 0.948 committed, 0.900 now"]}
    assert pipeline.print_compare(result) == 1


def test_compare_needs_git_history(tmp_path):
    assert not pipeline.git_ready(tmp_path)


@pytest.mark.skipif(not HAS_GIT, reason="needs Git")
def test_compare_sets_the_random_forest_apart_on_an_arm_processor(tmp_path, monkeypatch, capsys):
    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=tmp_path,
                       check=True, capture_output=True)
    board = "model_key,ber_mean\nelastic_net,0.1275\nrandom_forest,0.3632\n"
    oof = "strain_id,p_elastic_net,p_random_forest\nSTRAIN_0001,0.1756,0.1223\n"
    (tmp_path / "artifacts/model").mkdir(parents=True)
    (tmp_path / "artifacts/model/scoreboard.csv").write_text(board, encoding="utf-8")
    (tmp_path / "artifacts/model/oof_predictions.csv").write_text(oof, encoding="utf-8")
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "results")
    (tmp_path / "artifacts/model/scoreboard.csv").write_text(board.replace("0.3632", "0.367"), encoding="utf-8")
    (tmp_path / "artifacts/model/oof_predictions.csv").write_text(oof.replace("0.1223", "0.1194"),
                                                                    encoding="utf-8")
    monkeypatch.setattr(pipeline, "ARM", False)            # an Intel or AMD processor: two differences
    assert sorted(pipeline.compare(tmp_path, tmp_path / "no.duckdb")["differ"]) == [
        "model/oof_predictions.csv", "model/scoreboard.csv"]
    monkeypatch.setattr(pipeline, "ARM", True)             # an ARM processor: set apart, still a match
    result = pipeline.compare(tmp_path, tmp_path / "no.duckdb")
    assert result["differ"] == {} and sorted(result["expected"]) == ["model/oof_predictions.csv",
                                                                     "model/scoreboard.csv"]
    assert pipeline.print_compare(result) == 0
    out = capsys.readouterr().out
    assert "as expected on this ARM processor" in out and "All 0 other compared files match" in out
    (tmp_path / "artifacts/model/scoreboard.csv").write_text(
        board.replace("0.3632", "0.367").replace("0.1275", "0.2"), encoding="utf-8")
    result = pipeline.compare(tmp_path, tmp_path / "no.duckdb")   # the winner's numbers must still match
    assert result["differ"] == {"model/scoreboard.csv": ["row 1 (elastic_net), ber_mean: 0.1275 committed, 0.2 now"]}


def test_compare_all_lists_every_difference(capsys):
    result = {"matched": [], "skipped": {}, "expected": {},
              "differ": {"model/scoreboard.csv": [f"row {i} (x), y: 1 committed, 2 now" for i in range(1, 6)]}}
    assert pipeline.print_compare(result) == 1
    out = capsys.readouterr().out
    assert "row 3 (x)" in out and "row 4 (x)" not in out and "... and 2 more (--all lists them)" in out
    pipeline.print_compare(result, show_all=True)
    out = capsys.readouterr().out
    assert "row 5 (x)" in out and "more" not in out


def test_committed_tables_put_ties_in_a_fixed_order():
    """Rows with the same number go in name order, so a rebuild on any processor
    writes the same file (Phase 8 found ties in another order on ARM Macs)."""
    import pandas as pd
    art = ROOT / "artifacts"

    def in_order(table, keys, ascending):
        again = table.sort_values(keys, ascending=ascending, kind="mergesort")
        return again.index.equals(table.index)
    pred = pd.read_csv(art / "model/predictions.csv")
    assert in_order(pred, ["probability", "strain_id"], [False, True])
    sel = pd.read_csv(art / "integration/python_selection.csv")
    assert in_order(sel, ["selection_frequency", "feature"], [False, True])
    imp = pd.read_csv(art / "model/feature_importance.csv")
    for _, part in imp.groupby("model_key", sort=False):
        assert in_order(part, ["importance_mean", "feature"], [False, True])
        assert part["rank"].tolist() == list(range(1, len(part) + 1))
    hard = pd.read_csv(art / "model/hard_strains.csv")
    assert in_order(hard, ["distance_to_cutoff", "strain_id"], [True, True])


# =============================================================================
# The app's button
# =============================================================================

def test_the_data_page_offers_the_rebuild_on_your_own_computer_only(monkeypatch):
    pytest.importorskip("streamlit")
    sys.path.insert(0, str(ROOT / "app"))
    import ui
    from test_app import open_app
    at = open_app("views/data.py")
    button = at.button(key="build_everything")
    assert button.label == "Rebuild everything from scratch" and not button.disabled
    monkeypatch.setattr(ui, "PUBLIC", True)
    at = open_app("views/data.py")
    assert at.button(key="build_everything").disabled


def test_the_rebuild_button_runs_the_plan_and_compares(stand_in_steps, monkeypatch):
    pytest.importorskip("streamlit")
    sys.path.insert(0, str(ROOT / "app"))
    from test_app import open_app
    monkeypatch.setattr(pipeline, "compare", lambda root, db: {"matched": ["model/scoreboard.csv"] * 31,
                                                               "differ": {}, "skipped": {}})
    monkeypatch.setattr(pipeline, "git_ready", lambda root: True)   # also in a copy without Git history
    at = open_app("views/data.py")
    at.button(key="build_everything").click().run()
    assert not at.exception
    assert any("All 31 compared result files match" in s.value for s in at.success)
