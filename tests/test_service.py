"""
tests/test_service.py: offline tests for the service layer behind the app (Phase 6).
====================================================================================
What they protect, in plain words:
  * the SQL guards hold: reading works; writing, reading files, changing the
    settings, running forever and returning millions of rows don't;
  * every recipe in docs/QUERY_COOKBOOK.md is found, with its question, and
    (when the database exists) runs;
  * an upload is checked the way a careful person would check it, with a
    clear message for each problem, and the saved model scores it;
  * an uploaded copy of a library strain gets exactly the explanation the
    knowledge graph gives the original;
  * the drawing of a strain's corner of the graph only uses real nodes and
    edges, and marks a compound made without its gene;
  * the pipeline runner stops at a failing step and never runs twice at once.

None of them needs the network. The upload explanations use the 40-strain
hand-made project of tests/test_graph.py; the scoring uses the committed model.

Run:  pytest -q tests/test_service.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from strainscope import graph as kg  # noqa: E402
from strainscope import service as sv  # noqa: E402
from test_graph import _small_project  # noqa: E402

REAL_DB = sv.DB_PATH.exists()


@pytest.fixture()
def tiny_db(tmp_path):
    """A database with one small table, enough for the SQL guards."""
    import duckdb
    db = tmp_path / "tiny.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE phenotype AS SELECT range AS n, 'Bacteria' AS kingdom FROM range(50)")
    con.close()
    return db


# =============================================================================
# SQL
# =============================================================================

def test_reading_works_and_writing_is_refused(tiny_db, tmp_path):
    ok = sv.query_database("SELECT COUNT(*) AS n FROM phenotype", tiny_db)
    assert ok.error is None and int(ok.table["n"].iloc[0]) == 50
    for sql, words in [("CREATE TABLE x AS SELECT 1", "read-only"),
                       ("DELETE FROM phenotype", "read-only"),
                       (f"COPY phenotype TO '{(tmp_path / 'leak.csv').as_posix()}'", "files"),
                       (f"SELECT * FROM read_csv('{(ROOT / 'requirements.txt').as_posix()}')", "files"),
                       ("SET enable_external_access = true", "DuckDB says"),
                       ("SET memory_limit = '64GB'", "locked")]:
        res = sv.query_database(sql, tiny_db)
        assert res.table is None and words in res.error, sql
    assert not (tmp_path / "leak.csv").exists()


def test_a_runaway_query_is_stopped(tiny_db):
    res = sv.query_database("SELECT COUNT(*) FROM range(100000000000) a, range(1000) b", tiny_db, timeout_s=0.5)
    assert res.table is None and res.error.startswith("Stopped after 0.5 seconds")
    assert res.seconds < 10


def test_rows_are_capped_and_friendly_messages(tiny_db, tmp_path):
    res = sv.query_database("SELECT * FROM phenotype", tiny_db, max_rows=10)
    assert len(res.table) == 10 and res.truncated
    assert not sv.query_database("SELECT * FROM phenotype", tiny_db, max_rows=50).truncated
    assert "Type a query" in sv.query_database("   ", tiny_db).error
    assert "no database" in sv.query_database("SELECT 1", tmp_path / "nothing.duckdb").error
    assert "Real tables appear" in sv.query_database("SELECT * FROM real_strains", tiny_db).error
    assert "couldn't be read" in sv.query_database("SELEC 1", tiny_db).error
    twice = sv.query_database("SELECT n, n FROM phenotype LIMIT 1", tiny_db)
    assert list(twice.table.columns) == ["n", "n_2"]            # duplicate names made unique


def test_the_terminal_console_uses_the_same_guards(tiny_db):
    from strainscope.sql import run_query
    import duckdb
    assert int(run_query("SELECT COUNT(*) AS n FROM phenotype", tiny_db)["n"].iloc[0]) == 50
    with pytest.raises(duckdb.Error):
        run_query(f"SELECT * FROM read_csv('{(ROOT / 'requirements.txt').as_posix()}')", tiny_db)


# =============================================================================
# The cookbook
# =============================================================================

def test_every_cookbook_recipe_is_found_with_its_question():
    text = sv.COOKBOOK.read_text(encoding="utf-8")
    recipes = sv.cookbook_recipes()
    assert len(recipes) == text.count("```sql")
    assert all(r.sql and r.question and r.section for r in recipes)
    assert not any(r.question.startswith("Recipe ") for r in recipes)   # every one has a real question
    assert recipes[0].tables == ["phenotype"]
    assert any("real_strains" in r.tables for r in recipes)


@pytest.mark.skipif(not REAL_DB, reason="needs data/processed/strainscope.duckdb (python src/strainscope/harmonize.py)")
def test_every_cookbook_recipe_runs():
    present = set(sv.database_tables()["table"])
    for r in sv.cookbook_recipes():
        if set(r.tables) <= present:
            res = sv.query_database(r.sql)
            assert res.error is None, f"{r.question}: {res.error}"


# =============================================================================
# Uploads
# =============================================================================

def _upload(rows: list[dict]) -> pd.DataFrame:
    """An upload as the app reads it: every cell as text, blanks as gaps."""
    template = sv.upload_template()
    table = pd.DataFrame(rows).reindex(columns=template.columns)
    return table.astype(object).where(table.notna(), None)


def test_the_template_matches_the_saved_model():
    from strainscope.model import load_model
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model, _ = load_model()
    prep = model.calibrated_classifiers_[0].estimator.steps[0][1]
    genes, metabs = sv.feature_columns()
    assert genes == list(prep.gene_cols) and metabs == list(prep.metab_cols)
    assert list(sv.upload_template().columns) == ["strain_id", "kingdom", "genus", *genes, *metabs]


def test_a_good_upload_passes_and_is_tidied():
    raw = _upload([{"strain_id": " A1 ", "kingdom": "bacteria", "ituA": "yes", "fenA": "0", "iturin": "12.5"},
                   {"strain_id": "A2", "kingdom": "Fungi", "dtxS": "1", "destruxin": "3"}])
    raw["notes"] = ["keep me", ""]
    check = sv.validate_upload(raw)
    assert check.ok, check.problems
    t = check.table
    assert list(t["strain_id"]) == ["A1", "A2"] and list(t["kingdom"]) == ["Bacteria", "Fungi"]
    assert t.loc[0, "ituA"] == 1.0 and t.loc[0, "fenA"] == 0.0 and np.isnan(t.loc[1, "ituA"])
    assert t.loc[0, "iturin"] == 12.5
    assert "notes" in t.columns                                        # extra columns travel along
    levels = {level for level, _ in check.problems}
    assert "error" not in levels and "note" in levels


@pytest.mark.parametrize("change, words", [
    (lambda d: d.drop(columns=["strain_id"]), "needs a `strain_id` column"),
    (lambda d: d.assign(strain_id=["S1", "S1"]), "appear more than once"),
    (lambda d: d.assign(ituA=["2", "1"]), "must hold 0 or 1"),
    (lambda d: d.assign(iturin=["-1", "3"]), "negative levels on row 2"),
    (lambda d: d.assign(iturin=["1,5", "3"]), "full stop as the decimal mark"),
    (lambda d: d[["strain_id", "kingdom"]], "None of the gene or metabolite columns"),
    (lambda d: d.iloc[0:0], "no strains"),
])
def test_bad_uploads_are_refused_with_a_clear_message(change, words):
    raw = _upload([{"strain_id": "S1", "kingdom": "Bacteria", "ituA": "1"},
                   {"strain_id": "S2", "kingdom": "Yeast", "kilT": "1"}])
    check = sv.validate_upload(change(raw))
    assert not check.ok and check.table is None
    assert any(words in message for level, message in check.problems if level == "error"), check.problems


def test_odd_but_usable_uploads_get_warnings(monkeypatch):
    raw = _upload([{"strain_id": "S1", "kingdom": "Archaea", "ituA": "1"},
                   {"strain_id": "S2", "kingdom": "", "kilT": "1"}]).drop(columns=["accF", "bg_metabolite_6"])
    check = sv.validate_upload(raw)
    assert check.ok
    warnings = " ".join(m for level, m in check.problems if level == "warning")
    assert "never seen (Archaea)" in warnings and "`kingdom` is empty on row 3" in warnings
    assert "2 column(s) are missing" in warnings
    monkeypatch.setattr(sv, "MAX_UPLOAD_ROWS", 1)
    assert "up to 1 at a time" in sv.validate_upload(raw).problems[0][1]


def test_the_saved_model_scores_an_upload():
    raw = _upload([{"strain_id": "STRONG", "kingdom": "Bacteria", "fenA": "1", "hcnA": "1", "pvdA": "1",
                    "phlD": "1", "fengycin": "30", "HCN": "20", "pyoverdine": "40", "DAPG": "25"},
                   {"strain_id": "EMPTY", "kingdom": "Bacteria"}])
    check = sv.validate_upload(raw)
    scores, notes = sv.score_upload(check.table)
    assert list(scores["rank"]) == [1, 2] and scores["probability"].between(0, 1).all()
    assert scores.loc[0, "strain_id"] == "STRONG" and scores.loc[0, "probability"] > scores.loc[1, "probability"]
    assert scores["library_rank"].between(1, 601).all()
    assert all(n.startswith("model built with") for n in notes)


def test_borderline_means_30_to_70_percent():
    assert [sv.confidence_band(p) for p in (0.0, 0.29, 0.3, 0.5, 0.7, 0.71, 1.0)] == \
        ["unlikely", "unlikely", "borderline", "borderline", "borderline", "likely", "likely"]
    lib = sv.read_artifact("model/predictions.csv")
    cookbook = int(lib["probability"].between(0.3, 0.7).sum())      # the Query Cookbook's definition
    assert (lib["probability"].map(sv.confidence_band) == "borderline").sum() == cookbook


def test_an_uploaded_copy_is_explained_like_the_original(tmp_path):
    """The upload path must reach exactly the conclusions Phase 5 reaches for
    the same facts. Every strain of the hand-made project is re-entered as an
    upload and explained again."""
    import duckdb
    paths = _small_project(tmp_path)
    kg.build(**paths, verbose=False)
    G = kg.load_graph(paths["artifacts_dir"])
    kg.attach_expectations(G, paths["db_path"])
    con = duckdb.connect(str(paths["db_path"]), read_only=True)
    rows = (con.execute("SELECT * FROM phenotype").fetchdf()[["strain_id", "kingdom", "genus"]]
            .merge(con.execute("SELECT * FROM genomics").fetchdf(), on="strain_id")
            .merge(con.execute("SELECT * FROM metabolomics").fetchdf(), on="strain_id"))
    con.close()
    copies = rows.assign(strain_id="COPY_" + rows["strain_id"])
    U = sv.graph_with_upload(G, copies, sv.library_medians(paths["db_path"]))
    cols = ["kind", "feature", "compound", "mode", "text"]
    for sid in rows["strain_id"]:
        original = pd.DataFrame(kg.explain_strain(G, kg.node_id("Strain", sid)))[cols]
        copy = sv.explain_strains(U, [kg.node_id("Strain", "COPY_" + sid)], source=sv.P_UPLOAD)
        assert copy[cols].fillna("").equals(original.fillna("")), sid
        assert not copy["provenance"].str.contains("synthetic library").any()
    assert not any(n.startswith("strain:COPY_") for n in G)                # the library graph is untouched


def test_the_strain_picture_uses_real_edges_and_marks_odd_readings(tmp_path):
    paths = _small_project(tmp_path)
    kg.build(**paths, verbose=False)
    G = kg.load_graph(paths["artifacts_dir"])
    kg.attach_expectations(G, paths["db_path"])
    for sid in ("S000", "S001", "S002"):
        expl = pd.DataFrame(kg.explain_strain(G, kg.node_id("Strain", sid)))
        nodes, edges = sv.neighbourhood(G, sid, expl)
        ids = set(nodes["node_id"])
        assert set(edges["from_id"]) <= ids and set(edges["to_id"]) <= ids
        assert not edges.duplicated(["from_id", "to_id", "relation"]).any()
        assert set(nodes["x"]) <= {0.0, 1.0, 2.0, 3.0, 4.0}
        for r in edges[edges["relation"].isin(["carries", "makes", "acts_by", "contributes_to", "produces"])].itertuples():
            assert any(e["relation"] == r.relation for e in (G.get_edge_data(r.from_id, r.to_id) or {}).values())
        missing = set(expl.loc[expl["kind"] == "missing", "feature"]) if len(expl) else set()
        assert set(nodes.loc[nodes["status"] == "lacks", "label"]) == missing
    # a strain that makes a compound without carrying its gene gets the dashed "without gene" line
    G2 = G.copy()
    G2.add_edge("strain:S001", "compound:iturin", key="produces|test", relation="produces",
                provenance="test", weight=9.0)
    _, edges = sv.neighbourhood(G2, "S001")
    assert (edges.loc[edges["to_id"] == "compound:iturin", "style"] == "without gene").all()


# =============================================================================
# Health check and the pipeline runner
# =============================================================================

def test_status_without_a_database(tmp_path):
    checks = {c.name: c for c in sv.status(tmp_path / "none.duckdb")}
    assert checks["Database"].ok is False and "Data page" in checks["Database"].fix
    assert checks["Real tables (optional)"].ok is None
    assert checks["Phase 5 results"].ok is True                     # the committed results are still there
    assert checks["AI features (optional)"].ok in (None, True)     # optional: never a failure


def test_a_failing_step_stops_the_pipeline(monkeypatch):
    monkeypatch.setitem(sv.PIPELINES, "broken", {"title": "t", "takes": "", "what": "",
                                                 "steps": [("no_such_script.py",), ("generate_data.py",)]})
    out = list(sv.run_pipeline("broken"))
    assert out[-1][0] is None and out[-1][1] == "failed" and "Step 1" in out[-1][2]
    assert not any(line.startswith("$ python src/strainscope/generate_data.py") for _, _, line in out)


def test_only_one_pipeline_runs_at_a_time():
    assert sv._PIPELINE_LOCK.acquire(blocking=False)
    try:
        out = list(sv.run_pipeline("database"))
        assert out == [(None, "failed", "Another build is running. Wait for it to finish, then try again.")]
    finally:
        sv._PIPELINE_LOCK.release()
