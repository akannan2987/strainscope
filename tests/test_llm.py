"""
tests/test_llm.py: the shared connection to a language model (Phase 7).
=======================================================================
What they protect, in plain words:
  * the settings are read the same way for every feature, and anything
    unexpected means "off";
  * a shared copy has a daily cap on model requests unless the owner sets
    another, and a used-up cap means no request at all;
  * the checks that run on every written answer: it must cite what it was
    given, and it may not bring numbers of its own;
  * the request for a written answer asks for citations three ways, and its
    worked example brings no number and nothing from StrainScope with it;
  * a request goes where the settings say and carries the key only in its
    header.

Run:  pytest -q tests/test_llm.py
"""
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from conftest import stand_in  # noqa: E402
from strainscope import llm  # noqa: E402


def test_settings_are_off_unless_switched_on():
    assert llm.settings({}).backend == "none" and not llm.settings({}).on
    assert llm.settings({"STRAINSCOPE_ASK_BACKEND": "LOCAL "}).url == llm.LOCAL_URL
    assert llm.settings({"STRAINSCOPE_ASK_BACKEND": "cloud"}).backend == "none"
    hosted = llm.settings({"STRAINSCOPE_ASK_BACKEND": "hosted", "STRAINSCOPE_ASK_URL": "https://x.example/v1/",
                           "STRAINSCOPE_ASK_MODEL": "m", "STRAINSCOPE_ASK_KEY": "k"})
    assert hosted.url == "https://x.example/v1" and "k" not in hosted.describe()


def test_a_shared_copy_has_a_daily_cap_by_default():
    assert llm.daily_limit({}) is None
    assert llm.daily_limit({"STRAINSCOPE_MODE": "public"}) == llm.SHARED_DAILY_LIMIT
    assert llm.daily_limit({"STRAINSCOPE_MODE": "public", "STRAINSCOPE_AI_DAILY_LIMIT": "30"}) == 30
    assert llm.daily_limit({"STRAINSCOPE_AI_DAILY_LIMIT": "0"}) == 0
    assert llm.daily_limit({"STRAINSCOPE_AI_DAILY_LIMIT": "lots"}) is None


def test_the_cap_counts_and_starts_again_the_next_day():
    cap = llm.DailyCap(2)
    assert cap.take() and cap.take() and not cap.take()
    assert cap.describe() == "2 of 2 model requests used today (UTC)"
    cap.day = cap.day - dt.timedelta(days=1)          # pretend the count is from yesterday
    assert cap.take() and cap.used == 1


def test_a_used_up_cap_sends_nothing(model):
    text, note = llm.chat([{"role": "user", "content": "hi"}], stand_in(model), cap=llm.DailyCap(0))
    assert text is None and "used its 0 model requests" in note and model.calls == []


def test_a_request_goes_where_the_settings_say(model):
    text, note = llm.chat([{"role": "user", "content": "hi"}], stand_in(model, "hosted", "key-xyz"))
    assert text == model.reply and note is None
    call = model.calls[0]
    assert call["path"] == "/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer key-xyz" and "key-xyz" not in json.dumps(call["body"])


def test_citations_must_point_at_what_was_given():
    assert llm.citation_problem("It works [1][2].", 2) is None
    assert llm.citation_problem("It works.", 2) == "it cites nothing"
    assert llm.citation_problem("It works [3].", 2) == "it cites something it wasn't given"


def test_numbers_an_answer_brings_with_it_are_found():
    source = "fenA makes fengycin at 7.6 times the usual level; 47 of 50 were effective"
    assert llm.invented_numbers("fengycin at 7.6 times [1], 47 of 50 [2]", source) == set()
    assert llm.invented_numbers("about 90 % of strains [1]", source) == {"90"}
    assert llm.numbers("see [12] and 3.5") == {"3.5"}


def test_a_written_answer_is_asked_for_citations_three_ways():
    m = llm.cited_messages("RULES.", "Question: q\n\nFacts:\n[1] a fact.", "facts", "fact", "Facts")
    assert [x["role"] for x in m] == ["system", "user", "assistant", "user"]
    assert m[0]["content"].startswith("RULES. End every sentence with the numbers of the facts it uses")
    assert m[1]["content"].startswith("Question: What does the pump do?\n\nFacts:\n[1] ")
    assert m[3]["content"].startswith("Question: q") and m[3]["content"].endswith("such as [3] or [3][4].")


def test_the_worked_example_follows_the_rules_and_brings_nothing_along():
    assert llm.citation_problem(llm.EXAMPLE_ANSWER, 2) is None           # it shows a correct answer
    assert llm.numbers(llm.EXAMPLE_ANSWER + " " + llm.EXAMPLE_QUESTION) == set()   # no number a model could copy
    for word in ("strain", "gene", "iturin", "disease", "StrainScope"):
        assert word.lower() not in (llm.EXAMPLE_QUESTION + llm.EXAMPLE_ANSWER).lower()
