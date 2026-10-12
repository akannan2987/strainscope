"""
tests/test_narrate.py: results in plain words (Phase 7).
========================================================
What they protect, in plain words:
  * for every one of the 600 library strains, every number in the text can
    be found in the results it was written from (nothing is invented);
  * the wording follows the facts: the band, the strongest route, the
    statistics-only flag, the missing weapons and, for the library, what
    the trial said, including the cases where the model was wrong;
  * a chance is never rounded to a certainty;
  * an upload gets its place among the library's 600 and no trial sentence;
  * the "test N strains" paragraph adds up to the numbers on the Ranking page.

Run:  pytest -q tests/test_narrate.py
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strainscope import narrate  # noqa: E402
from strainscope import service as sv  # noqa: E402


@pytest.fixture(scope="module")
def results():
    pred = sv.read_artifact("model/predictions.csv").sort_values("rank")
    reasons = sv.read_artifact("graph/explanations.csv")
    return pred, reasons, sv.model_card()


def story_of(results, strain_id, **row_changes):
    pred, reasons, card = results
    row = {**pred[pred["strain_id"] == strain_id].iloc[0].to_dict(), **row_changes}
    return narrate.strain(row, reasons[reasons["strain_id"] == strain_id], len(pred), card)


def test_every_number_comes_from_the_results(results):
    pred, reasons, card = results
    for row in pred.to_dict("records"):
        story = narrate.strain(row, reasons[reasons["strain_id"] == row["strain_id"]], len(pred), card)
        assert narrate.numbers_of(story.text) <= story.numbers, row["strain_id"]


def test_the_top_strain_in_plain_words(results):
    text = story_of(results, "STRAIN_0485").text
    assert "at rank 1 of 600" in text and "over 99 %" in text and "counts as likely" in text
    assert "Its strongest reason: it carries fenA and produces fengycin at 7.6 times the usual level" in text
    assert "lipopeptides punch holes in the pathogen's cell membrane" in text
    assert "10 routes like these" in text
    assert "leans a little on accE" in text
    assert "it was effective, as the model expected" in text


def test_the_wording_follows_the_band_and_the_trial(results):
    pred = results[0]
    wrong = pred[(pred["probability"] > 0.7) & (pred["is_effective"] == 0)].iloc[0]["strain_id"]
    assert "the model was wrong about this one" in story_of(results, wrong).text
    missed = pred[(pred["probability"] < 0.3) & (pred["is_effective"] == 1)].iloc[0]["strain_id"]
    assert "one the model missed" in story_of(results, missed).text
    middle = pred[pred["probability"].between(0.3, 0.7)].iloc[0]["strain_id"]
    assert "read it as a maybe" in story_of(results, middle).text
    last = story_of(results, pred.iloc[-1]["strain_id"]).text
    assert "under 1 %" in last and "Its strongest route to disease suppression" in last
    assert "A route isn't enough on its own" in last


def test_a_chance_is_never_rounded_to_a_certainty():
    assert narrate.percent(0.9998) == "over 99 %" and narrate.percent(0.001) == "under 1 %"
    assert narrate.percent(0.734) == "73 %"


def test_an_upload_gets_its_library_place_and_no_trial(results):
    pred, reasons, card = results
    row = {"strain_id": "MINE_1", "kingdom": "Bacteria", "genus": "unknown", "rank": 1, "probability": 0.81,
           "library_rank": 57}
    mine = reasons[reasons["strain_id"] == "STRAIN_0485"].assign(strain_id="MINE_1")
    text = narrate.strain(row, mine, 2, card, uploaded=True).text
    assert "at rank 1 of the 2 strains in your file" in text and "would rank 57" in text
    assert "simulated trial" not in text and "(unknown)" not in text


def test_a_strain_with_no_route_says_so():
    row = {"strain_id": "MINE_2", "kingdom": "Yeast", "rank": 2, "probability": 0.05}
    text = narrate.strain(row, pd.DataFrame(), 2, None, uploaded=True).text
    assert "finds no route from it to disease suppression" in text


def test_the_shortlist_matches_the_ranking_page(results):
    pred = results[0]
    text = narrate.shortlist(pred, 50).text
    assert "add up to 46.2" in text and "47 of the 50 were effective (94 %)" in text
    assert "about 12, because 24 % of the library" in text and "98 of the 145 effective strains" in text
    assert "rates 50 of them likely, 0 borderline and 0 unlikely" in text
    upload = narrate.shortlist(pred.head(3), 3, uploaded=True).text
    assert upload.startswith("If you test your 3 best-ranked strains") and "simulated trial" not in upload


def test_the_command_line_says_it_in_plain_words():
    import os
    import subprocess
    script = str(ROOT / "src" / "strainscope" / "narrate.py")
    env = {**os.environ, "PYTHONUTF8": "1"}
    one = subprocess.run([sys.executable, script, "STRAIN_0485"], capture_output=True, text=True, encoding="utf-8",
                         cwd=ROOT, env=env)
    top = subprocess.run([sys.executable, script, "--top", "50"], capture_output=True, text=True, encoding="utf-8",
                         cwd=ROOT, env=env)
    assert one.returncode == 0 and "at rank 1 of 600" in one.stdout
    assert top.returncode == 0 and "add up to 46.2" in top.stdout
