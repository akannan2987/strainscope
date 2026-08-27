"""
test_sources.py — offline tests for the real-data adapters.
===========================================================

WHY THESE TESTS MATTER (a beginner-friendly note)
-------------------------------------------------
The adapters split work into fetch() (talks to the internet) and tidy() (reads
files already on disk). That split is what makes honest testing possible: we
save tiny, hand-made "canned" API responses to disk and run tidy() on them —
no network needed, runs in milliseconds, works offline, and never bothers a
public server. If an API's response shape ever changes, updating the canned
sample here documents the change forever.

Run them (from the project root, venv active):
    pytest -q
"""

import csv
import json
import sys
from pathlib import Path

# Make the package importable when pytest runs from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strainscope.sources.bacdive import BacDive, _dig, _extract_ids   # noqa: E402
from strainscope.sources.kegg import KEGG, _parse_tsv            # noqa: E402
from strainscope.sources.pubchem import PubChem                  # noqa: E402


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------- helper units
def test_dig_walks_nested_dicts_safely():
    rec = {"a": {"b": [{"c": "found"}]}}
    assert _dig(rec, "a", "b", "c") == "found"
    assert _dig(rec, "a", "missing", default="") == ""      # never crashes


def test_extract_ids_accepts_both_api_shapes():
    # The LIVE BacDive API returns bare integer IDs (caught on the first real
    # fetch, 2026-08); earlier documentation showed dict entries. Both must work.
    assert _extract_ids([171624, 171625, 171626], limit=2) == ["171624", "171625"]
    assert _extract_ids([{"id": 5}, {"id": None}, {"id": 7}], limit=9) == ["5", "7"]


def test_parse_tsv_reads_kegg_lines():
    text = "cpd:C11002\tbeauvericin\ncpd:C00027\thydrogen peroxide"
    assert _parse_tsv(text) == [("cpd:C11002", "beauvericin"),
                                ("cpd:C00027", "hydrogen peroxide")]


# ------------------------------------------------------------- tidy() end-to-end
def test_bacdive_tidy_builds_strain_table(tmp_path, monkeypatch):
    src = BacDive()
    monkeypatch.setattr(src, "raw_dir", lambda: tmp_path)   # canned raw dir
    canned = {"117851": {
        "Name and taxonomic classification": {
            "genus": "Bacillus", "species": "subtilis",
            "full scientific name": "Bacillus subtilis", "type strain": "yes"},
        "Isolation, sampling and environmental information": {
            "isolation": {"sample type": "soil", "country": "Germany"}}}}
    (tmp_path / "records_Bacillus.json").write_text(json.dumps(canned))
    out_rows = []
    monkeypatch.setattr(src, "write_table",
                        lambda name, rows: out_rows.extend(rows) or tmp_path / name)
    src.tidy()
    assert out_rows[0]["genus"] == "Bacillus"
    assert out_rows[0]["isolation_source"] == "soil"
    assert out_rows[0]["country"] == "Germany"


def test_pubchem_tidy_marks_found_and_missing(tmp_path, monkeypatch):
    src = PubChem()
    monkeypatch.setattr(src, "raw_dir", lambda: tmp_path)
    canned = {
        "surfactin": {"query": "surfactin",
                      "properties": {"CID": 443592, "MolecularFormula": "C53H93N7O13",
                                     "MolecularWeight": "1036.3",
                                     "CanonicalSMILES": "CC...", "IUPACName": "..."}},
        "pyoverdine": {"query": "pyoverdine", "properties": None},
    }
    (tmp_path / "compounds.json").write_text(json.dumps(canned))
    out_rows = []
    monkeypatch.setattr(src, "write_table",
                        lambda name, rows: out_rows.extend(rows) or tmp_path / name)
    src.tidy()
    by_name = {r["metabolite"]: r for r in out_rows}
    assert by_name["surfactin"]["status"] == "found"
    assert by_name["surfactin"]["cid"] == 443592
    assert by_name["pyoverdine"]["status"] == "no_entry"
    # The honest not-a-small-molecule entries are always present:
    assert by_name["oligandrin"]["status"] == "not_a_small_molecule"


def test_kegg_tidy_builds_edges_with_names(tmp_path, monkeypatch):
    src = KEGG()
    monkeypatch.setattr(src, "raw_dir", lambda: tmp_path)
    (tmp_path / "compound_pathways.json").write_text(json.dumps({
        "beauvericin": {"query": "beauvericin", "kegg_id": "C11002",
                        "matched_name": "beauvericin",
                        "pathways": ["map01110"]}}))
    (tmp_path / "pathway_names.json").write_text(json.dumps(
        {"map01110": "Biosynthesis of secondary metabolites"}))
    written = {}
    def fake_write(name, rows):
        written[name] = rows
        return tmp_path / name
    monkeypatch.setattr(src, "write_table", fake_write)
    src.tidy()
    edges = written["real_compound_pathways.csv"]
    assert edges[0]["pathway_name"] == "Biosynthesis of secondary metabolites"
    assert edges[0]["attribution"] == "KEGG (academic use)"
