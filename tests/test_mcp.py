"""
tests/test_mcp.py: the MCP server (Phase 7b).
=============================================
What they protect, in plain words:
  * every tool answers from the same functions as the terminal and the app,
    with the numbers the guides quote (STRAIN_0485 first of 600, 46.2
    expected among the best 50, four kingdoms);
  * input is checked: a strain id must look right and exist, a question
    can't be empty or too long, numbers stay within their limits, and every
    refusal says why in a sentence;
  * nothing can change the database or read a file: query_database accepts
    one SELECT (or WITH) and nothing else;
  * no tool ever contacts a language model: the assistant app writes the
    reply, StrainScope only supplies the material;
  * every call is logged (tool, arguments, outcome, time) and no result is;
  * nothing a tool prints can reach stdout, which carries the protocol;
  * the server speaks real MCP: in-process, and as a separate program over
    stdio, the way an assistant app starts it.

None of them needs the network or an assistant app.

Run:  pytest -q tests/test_mcp.py
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import stand_in  # noqa: E402
from strainscope import mcp_server as M  # noqa: E402
from strainscope import service as sv  # noqa: E402

pytestmark = pytest.mark.skipif(not sv.DB_PATH.exists(),
                                reason="needs data/processed/strainscope.duckdb (python src/strainscope/harmonize.py)")

TOOL_NAMES = ["ask_docs", "ask_data", "ask_graph", "describe_database", "query_database", "get_signature",
              "rank_strain", "explain_strain", "shortlist"]


@pytest.fixture(autouse=True)
def log_to_tmp(tmp_path, monkeypatch):
    """Every test writes its call log to a fresh file, never to data/processed/."""
    monkeypatch.setattr(M, "LOG_PATH", tmp_path / "mcp_calls.log")
    return tmp_path / "mcp_calls.log"


def log_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# =============================================================================
# The tools, called directly
# =============================================================================

def test_the_tools_are_the_ones_the_guide_lists():
    assert [t.__name__ for t in M.TOOLS] == TOOL_NAMES
    for tool in M.TOOLS:
        args, first = M.describe(tool)
        assert first.endswith(".") and len(first) > 30, tool.__name__


def test_rank_strain_gives_the_top_strain():
    r = M.rank_strain("STRAIN_0485")
    assert (r["rank"], r["of"], r["band"], r["data"]) == (1, 600, "likely", "simulated")
    assert r["probability"] > 0.99 and r["trial"]["is_effective"] is True
    assert M.rank_strain("strain_0485")["rank"] == 1                    # written in lower case, still found


@pytest.mark.parametrize("bad, words", [("STRAIN_9999", "no STRAIN_9999"), ("0485", "isn't a strain id"),
                                        ("", "isn't a strain id"), ("STRAIN_485", "isn't a strain id"),
                                        ("STRAIN_0485; DROP TABLE x", "isn't a strain id")])
def test_a_bad_strain_id_is_refused_with_a_reason(bad, words):
    with pytest.raises(M.Refused, match=words):
        M.rank_strain(bad)


@pytest.mark.parametrize("question", ["", "   ", "x" * (M.MAX_QUESTION + 1)])
def test_an_empty_or_long_question_is_refused(question):
    for tool in (M.ask_docs, M.ask_data, M.ask_graph):
        with pytest.raises(M.Refused):
            tool(question)


def test_the_three_assistants_answer_as_in_the_app():
    docs = M.ask_docs("What is a balanced error rate?")
    assert docs["verdict"] == "answered" and docs["sections"][0]["heading"] == "Balanced error rate (BER)"
    assert docs["sections"][0]["url"].startswith("https://github.com/akannan2987/strainscope/blob/master/docs/")
    data = M.ask_data("How many strains are there in each kingdom?")
    assert data["source"] == "recipe" and data["row_count"] == 4 and "note" not in data
    graph = M.ask_graph("How does iturin suppress disease?")
    assert graph["verdict"] == "answered" and len(graph["facts"]) == 7 and graph["route"]


def test_no_tool_ever_contacts_a_language_model(model, monkeypatch):
    cfg = stand_in(model)                                               # a model switched on and reachable
    monkeypatch.setenv("STRAINSCOPE_ASK_BACKEND", "local")
    monkeypatch.setenv("STRAINSCOPE_ASK_URL", cfg.url)
    M.ask_docs("What is a balanced error rate?")
    M.ask_graph("How does iturin suppress disease?")
    M.ask_data("Which strains carry ituA, fenA and srfA together, and in which kingdom?")
    assert model.calls == []


def test_describe_database_lists_tables_columns_and_notes():
    d = M.describe_database()
    tables = {t["table"]: t for t in d["tables"]}
    assert {"phenotype", "genomics", "ml_predictions", "kg_edges"} <= set(tables)
    assert "kingdom" in tables["phenotype"]["columns"] and tables["phenotype"]["rows"] == 600
    assert d["notes"] and "SELECT" in d["rules"]


def test_query_database_runs_one_select_and_caps_the_rows():
    r = M.query_database("SELECT kingdom, COUNT(*) AS strains FROM phenotype GROUP BY kingdom ORDER BY strains DESC")
    assert r["columns"] == ["kingdom", "strains"] and r["rows"][0] == {"kingdom": "Bacteria", "strains": 267}
    capped = M.query_database("SELECT strain_id FROM phenotype", max_rows=5)
    assert capped["row_count"] == 5 and capped["truncated"] is True


@pytest.mark.parametrize("sql", [
    "DELETE FROM phenotype",
    "DROP TABLE phenotype",
    "SELECT 1; DELETE FROM phenotype",
    "COPY phenotype TO 'out.csv'",
    "SELECT * FROM read_csv('data/raw/phenotype.csv')",
    "UPDATE phenotype SET kingdom = 'x'",
    "",
    "SELECT " + ", ".join(["1"] * M.MAX_SQL),
])
def test_query_database_refuses_anything_but_one_read(sql):
    with pytest.raises(M.Refused):
        M.query_database(sql)


@pytest.mark.parametrize("max_rows", [0, M.MAX_ROWS + 1, "many", 2.5])
def test_query_database_keeps_max_rows_within_limits(max_rows):
    with pytest.raises(M.Refused, match="max_rows"):
        M.query_database("SELECT 1", max_rows=max_rows)


def test_a_query_the_database_rejects_comes_back_as_a_sentence():
    with pytest.raises(M.Refused, match="couldn't run it"):
        M.query_database("SELECT no_such_column FROM phenotype")


def test_get_signature_returns_diablos_picks_and_the_report_card():
    s = M.get_signature()
    features = {row["feature"] for row in s["signature"]}
    assert {"fenA", "ituA"} <= features and len(s["signature"]) == 52
    assert any("robust" in row["method"] for row in s["report_card"])


def test_explain_strain_and_shortlist_quote_the_same_numbers_as_the_guides():
    e = M.explain_strain("STRAIN_0485")
    assert "at rank 1 of 600" in e["in_plain_words"]
    assert e["reasons"][0]["route"].startswith("STRAIN_0485 > fenA > fengycin")
    s = M.shortlist(50)
    assert (s["expected_effective"], s["effective_in_trial"], len(s["strains"])) == (46.2, 47, 50)


@pytest.mark.parametrize("n", [0, 601, "lots"])
def test_shortlist_keeps_n_within_the_library(n):
    with pytest.raises(M.Refused, match="n must be"):
        M.shortlist(n)


def test_every_result_is_plain_json():
    for result in (M.rank_strain("STRAIN_0001"), M.explain_strain("STRAIN_0001"), M.shortlist(10),
                   M.get_signature(), M.describe_database(), M.ask_data("Which strains are borderline?"),
                   M.query_database("SELECT * FROM genomics LIMIT 5")):
        json.dumps(result, allow_nan=False)                             # no NaN, no numpy numbers


# =============================================================================
# The call log, and stdout
# =============================================================================

def test_every_call_is_logged_and_no_result_is(log_to_tmp):
    M.rank_strain("STRAIN_0485")
    with pytest.raises(M.Refused):
        M.rank_strain("STRAIN_9999")
    M.query_database("SELECT strain_id FROM phenotype", max_rows=3)
    lines = log_lines(log_to_tmp)
    assert [(e["tool"], e["outcome"]) for e in lines] == [("rank_strain", "ok"), ("rank_strain", "refused"),
                                                         ("query_database", "ok")]
    assert all(e["time"].endswith("+00:00") and e["seconds"] >= 0 for e in lines)
    assert lines[1]["note"].startswith("There's no STRAIN_9999") and lines[2]["rows"] == 3
    text = log_to_tmp.read_text(encoding="utf-8")
    assert not any(word in text for word in ("probability", "Bacteria", "likely", "rank\": 1"))   # no results


def test_a_log_that_cannot_be_written_never_stops_a_tool(monkeypatch, tmp_path):
    monkeypatch.setattr(M, "LOG_PATH", tmp_path / "a-file" / "mcp_calls.log")
    (tmp_path / "a-file").write_text("not a folder")
    assert M.rank_strain("STRAIN_0485")["rank"] == 1


def test_nothing_a_tool_prints_reaches_stdout(monkeypatch, capsys):
    def noisy(question, write=False):
        print("a stray message")
        return {"verdict": "answered"}
    monkeypatch.setattr(sv, "ask_docs", noisy)
    assert M.ask_docs("anything at all")["verdict"] == "answered"
    out, err = capsys.readouterr()
    assert out == "" and "a stray message" in err


# =============================================================================
# The command line
# =============================================================================

def test_call_runs_a_tool_from_the_terminal(capsys):
    assert M.main(["call", "rank_strain", "strain_id=STRAIN_0485"]) == 0
    assert json.loads(capsys.readouterr().out)["rank"] == 1
    assert M.main(["call", "rank_strain", "strain_id=STRAIN_9999"]) == 1
    assert "Refused: There's no STRAIN_9999" in capsys.readouterr().out
    assert M.main(["call", "no_such_tool"]) == 2
    assert M.main(["call", "rank_strain", "id=STRAIN_0485"]) == 2


def test_tools_and_config_need_no_assistant(capsys):
    assert M.main(["tools"]) == 0
    out = capsys.readouterr().out
    assert "9 tools, all read-only" in out and "query_database(sql: str, max_rows: int = 50)" in out
    assert M.main(["config"]) == 0
    out = capsys.readouterr().out
    block = json.loads(out[out.index("{"):out.rindex("}") + 1])
    entry = block["mcpServers"]["strainscope"]
    assert Path(entry["command"]).is_absolute() and entry["args"] == [str(ROOT / "src" / "strainscope" / "mcp_server.py")]
    assert "claude mcp add --transport stdio --scope user strainscope -- " in out


# =============================================================================
# Real MCP: in-process, and over stdio as an assistant app does
# =============================================================================

def test_the_server_lists_read_only_tools_and_answers_over_mcp():
    pytest.importorskip("mcp")
    import anyio
    from mcp import Client

    async def run():
        async with Client(M.build_server()) as client:
            tools = (await client.list_tools()).tools
            assert [t.name for t in tools] == TOOL_NAMES
            assert all(t.annotations.read_only_hint and not t.annotations.destructive_hint for t in tools)
            schema = {t.name: t.input_schema for t in tools}
            assert schema["rank_strain"]["required"] == ["strain_id"]
            assert schema["query_database"]["properties"]["max_rows"]["default"] == 50
            ok = await client.call_tool("rank_strain", {"strain_id": "STRAIN_0485"})
            assert not ok.is_error and json.loads(ok.content[0].text)["rank"] == 1
            bad = await client.call_tool("query_database", {"sql": "DROP TABLE phenotype"})
            assert bad.is_error and "Only one SELECT" in bad.content[0].text
            assert client.server_info.name == "strainscope" and client.instructions.startswith("StrainScope ranks")
    anyio.run(run)


def test_the_check_talks_to_the_server_over_stdio(capsys):
    pytest.importorskip("mcp")
    assert M.main(["check"]) == 0
    out = capsys.readouterr().out
    assert "MCP check passed." in out and "9 tools, all marked read-only" in out
