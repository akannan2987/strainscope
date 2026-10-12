"""
tests/test_app.py: the app itself, clicked through without a browser (Phase 6).
================================================================================
Streamlit ships a test runner (AppTest) that runs the app's scripts the way a
browser session would, but in memory: it can open a page, set a widget, press
a button and read what was drawn. These tests check that:
  * every page opens without an error, with or without the database, and
    the test really lands on it (it checks the page's title);
  * the strain page explains the top strain with the graph's own words;
  * the SQL console answers a question and refuses to change anything;
  * an upload shows up on the Ranking and Strain pages when chosen;
  * the shared ("public") mode hides the buttons that download or rewrite;
  * every chart can be drawn from the committed results.

Run:  pytest -q tests/test_app.py
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(ROOT / "src"))

from streamlit.testing.v1 import AppTest  # noqa: E402

import charts  # noqa: E402
import ui  # noqa: E402  (the same module object the app imports)
from strainscope import graph as kg  # noqa: E402
from strainscope import service as sv  # noqa: E402

# Each page and the title it shows. A test that asks for a page and quietly
# gets the Home page instead would prove nothing, so open_app() checks the title.
TITLES = {"views/home.py": "StrainScope", "views/ranking.py": "Ranking", "views/strain.py": "STRAIN_",
          "views/knowledge_graph.py": "Knowledge graph", "views/integration.py": "Integration",
          "views/data.py": "Data", "views/sql_console.py": "SQL console"}
PAGES = list(TITLES)
HAS_DB = ui.DB_PATH.exists()
needs_db = pytest.mark.skipif(not HAS_DB, reason="needs the database (python src/strainscope/harmonize.py)")


def open_app(page: str | None = None, **state) -> AppTest:
    at = AppTest.from_file(str(APP / "streamlit_app.py"), default_timeout=90)
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    if page:
        at.switch_page(page)
        at.run()
        assert not at.exception, at.exception[0].value
        assert at.title and at.title[0].value.startswith(TITLES[page]), \
            f"asked for {page} but the app shows {[t.value for t in at.title]}"
    return at


def texts(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown) + " " + " ".join(c.value for c in at.caption)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_opens(page):
    at = open_app(page)
    assert not at.exception, at.exception[0].value
    assert len(at.title) == 1


@pytest.mark.parametrize("page", PAGES)
def test_every_page_opens_without_a_database(page, monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "DB_PATH", tmp_path / "missing.duckdb")
    at = open_app(page)
    assert not at.exception, at.exception[0].value
    if page == "views/home.py":
        assert any(b.label.startswith("Build the database now") for b in at.button)


def test_the_strain_page_explains_the_top_strain():
    at = open_app("views/strain.py", current_strain="STRAIN_0485")
    assert at.title[0].value == "STRAIN_0485"
    body = texts(at)
    assert "carries fenA and produces fengycin" in body
    assert "no known mechanism links it to disease suppression" in body          # the accE flag
    assert [m.value for m in at.metric][:1] == ["1 of 600"]


@needs_db
def test_the_sql_console_answers_and_refuses():
    at = open_app("views/sql_console.py")
    at.text_area(key="sql_text").set_value("SELECT kingdom, COUNT(*) AS n FROM phenotype GROUP BY kingdom")
    next(b for b in at.button if b.label == "Run").click()
    at.run()
    assert at.dataframe[-1].value.shape == (4, 2)
    at.text_area(key="sql_text").set_value("DROP TABLE phenotype")
    next(b for b in at.button if b.label == "Run").click()
    at.run()
    assert "read-only" in at.error[0].value


def test_a_recipe_goes_into_the_editor():
    at = open_app("views/sql_console.py")
    if not HAS_DB:
        pytest.skip("needs the database")
    first = sv.cookbook_recipes()[1]
    at.selectbox(key="recipe").set_value(1)
    next(b for b in at.button if b.label == "Put this recipe in the editor").click()
    at.run()
    assert at.text_area(key="sql_text").value == first.sql


def test_an_upload_is_shown_when_chosen():
    raw = sv.upload_template().reindex(range(2)).astype(object)
    raw.loc[0, ["strain_id", "kingdom", "fenA", "fengycin"]] = ["MINE_1", "Bacteria", "1", "40"]
    raw.loc[1, ["strain_id", "kingdom", "kilT"]] = ["MINE_2", "Yeast", "1"]
    result = sv.score_and_explain(raw.where(raw.notna(), None))
    assert result["check"].ok
    upload = {"name": "mine.csv", **{k: result[k] for k in ("scores", "explanations", "graph")}}
    at = open_app("views/ranking.py", upload=upload, source="upload")
    assert at.title[0].value == "Ranking: your strains"
    assert set(at.dataframe[0].value["strain_id"]) == {"MINE_1", "MINE_2"}
    at.switch_page("views/strain.py")
    at.run()
    assert not at.exception
    assert at.title[0].value in {"MINE_1", "MINE_2"}
    assert "from your upload" in texts(at)


def test_public_mode_hides_fetching(monkeypatch):
    monkeypatch.setattr(ui, "PUBLIC", True)
    at = open_app("views/data.py")
    labels = {b.label for b in at.button}
    assert "Fetch real data and rebuild" not in labels
    assert "Ask the public databases what a fetch would bring" not in labels


def test_every_chart_draws_from_the_committed_results():
    read = sv.read_artifact
    pred = read("model/predictions.csv")
    figures = [
        charts.top_n_figure(pred, 50),
        charts.probability_strip(pred, "STRAIN_0485"),
        charts.model_scoreboard_figure(read("model/scoreboard.csv")),
        charts.calibration_figure(read("model/calibration_curve.csv")),
        charts.importance_figure(read("model/feature_importance.csv").query("model_key == 'elastic_net'")),
        charts.signature_figure(read("integration/diablo_signature.csv"), read("integration/feature_annotations.csv")),
        charts.integration_scoreboard_figure(read("integration/python_scoreboard.csv"), 0.155),
        charts.correlation_heatmap(read("integration/cross_block_correlation.csv")),
    ]
    layout = charts.knowledge_layout(read("graph/nodes.csv"), read("graph/edges.csv"))
    figures.append(charts.network_figure(layout, read("graph/edges.csv")))
    G = sv.load_full_graph()
    figures.append(charts.path_figure(kg.path(G, "ituA", "disease suppression")))
    nodes, edges = sv.neighbourhood(G, "STRAIN_0485")
    figures.append(charts.neighbourhood_figure(nodes, edges))
    assert all(len(f.data) > 0 for f in figures)
    # the top-N chart tells the same story as the model card: 47 of the top 50
    assert int(pred.nsmallest(50, "rank")["is_effective"].sum()) == sv.model_card()["top_n_check"]["truly_effective"]
