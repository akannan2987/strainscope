"""
src/strainscope/datasets.py (StrainScope Phase 9): datasets of your own.
========================================================================

WHAT THIS MODULE DOES (in one sentence)
---------------------------------------
It checks three tables of your own (genes, compounds, trial results) cell by
cell, saves them as a dataset with a folder of its own, and keeps track of
which phases have run on it, so the whole workflow of Phases 2 to 5 can run
on your strains instead of the simulated library.

WHAT A DATASET IS
-----------------
A labelled box: your three tables, the database cleaned from them and every
result computed from them, in one folder under data/processed/datasets/
(src/strainscope/paths.py draws the layout). The built-in library is never
touched by a dataset, and Git never sees a dataset (everything under data/
stays on your computer). There are two kinds:

  yours      three CSV files you give it. There is no answer key, so nothing
             is graded against a planted truth; the knowledge graph links
             the genes and compounds it knows by name to their mechanisms.
  simulated  a fresh library from src/strainscope/generate_data.py with a
             seed and size you choose. The answer key applies, as in the
             library. Seed 42 and 600 strains rebuilds the library itself.

THE THREE TABLES (the same layout as the library's data/raw/ files)
------------------------------------------------------------------
  genomics.csv       strain_id, then one column per gene: 1 = carries it,
                     0 = doesn't, empty = not known (yes/no, true/false work too)
  metabolomics.csv   strain_id, then one column per compound: the level the
                     lab measured (a number, 0 or more), empty = not measured
  phenotype.csv      strain_id, kingdom (Bacteria, Fungi, Yeast or Oomycete),
                     suppression_score (the trial result, % of disease
                     suppressed), and if you have them: is_effective (1/0),
                     genus, collection_site, isolation_date, batch_id,
                     growth_promotion

Any gene and compound names work (letters, digits and _ ; starting with a
letter). Names StrainScope knows, like ituA or iturin, get their mechanism in
the knowledge graph. The checks below say exactly what was found and what was
assumed, with spreadsheet row numbers, before anything is saved.

COMMANDS (from the project folder, virtual environment active)
--------------------------------------------------------------
    python src/strainscope/datasets.py template my_tables        three empty tables to fill in
    python src/strainscope/datasets.py example my_tables         120 simulated strains to try it with
    python src/strainscope/datasets.py check my_tables           check the three files in a folder
    python src/strainscope/datasets.py new trial --from my_tables     save them as dataset "trial"
    python src/strainscope/datasets.py new demo --simulate --seed 7 --strains 300
    python src/strainscope/datasets.py list                       every dataset and how far it got
    python src/strainscope/datasets.py show trial                 one dataset, step by step
    python src/strainscope/datasets.py remove trial               delete it (asks first)

and to run every phase on one:

    python src/strainscope/pipeline.py --dataset trial

The app's Workflow page does the same with buttons. The guide is
docs/10-workflow-and-your-data.md.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Make `strainscope` importable no matter where the script is run from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strainscope import paths  # noqa: E402  (after the path fix)

TABLES = ("genomics", "metabolomics", "phenotype")
WHAT = {"genomics": "the genes table", "metabolomics": "the compounds table",
        "phenotype": "the trial-results table"}
KINGDOMS = ("Bacteria", "Fungi", "Yeast", "Oomycete")
KINGDOM_SPELLINGS = {
    "bacteria": "Bacteria", "bacterium": "Bacteria", "bacterial": "Bacteria",
    "fungi": "Fungi", "fungus": "Fungi", "fungal": "Fungi",
    "yeast": "Yeast", "yeasts": "Yeast",
    "oomycete": "Oomycete", "oomycetes": "Oomycete",
}
YES_NO = {"1": 1.0, "1.0": 1.0, "true": 1.0, "yes": 1.0, "y": 1.0,
          "0": 0.0, "0.0": 0.0, "false": 0.0, "no": 0.0, "n": 0.0}
OPTIONAL = ("is_effective", "genus", "collection_site", "isolation_date", "batch_id", "growth_promotion")
PHENOTYPE_ORDER = ("strain_id", "kingdom", "genus", "collection_site", "isolation_date", "batch_id",
                   "suppression_score", "growth_promotion", "is_effective")
NAME_RULE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,39}")      # a gene, compound or dataset name
EFFECTIVE_AT = 65.0          # the library's line: at least 65 % of disease suppressed
MIN_STRAINS = 40             # fewer, and five-fold cross-validation has too little to learn from
MIN_PER_CLASS = 10           # effective and not effective, each
QUICK_REPEATS = 2            # cross-validation repeats with quick settings (the full run uses 10)
NEAR_CONSTANT = 0.95         # Phase 3's rule: one value in 95 % of strains tells nothing apart

# How much one dataset may hold. On your own computer the limits only protect
# you from a mistake; on a shared copy (the online app) they keep one
# visitor's run short enough for the next one.
LIMITS = {
    "local": {"strains": 5_000, "genes": 300, "compounds": 300, "megabytes": 20},
    "shared": {"strains": 1_000, "genes": 100, "compounds": 100, "megabytes": 5},
}
SHARED_MAX_AGE_HOURS = 1     # a shared copy deletes a visitor's dataset after an hour without use
SHARED_MAX_DATASETS = 20     # ... and keeps at most this many at once (the oldest go first)


# =============================================================================
# 1. CHECKING THREE TABLES
# =============================================================================

@dataclass
class DatasetCheck:
    """The result of checking three tables: whether they can be used, every
    problem found (errors stop, warnings and notes explain what was assumed),
    the tables ready to save (None when there are errors) and a summary."""
    ok: bool
    problems: list[tuple[str, str]] = field(default_factory=list)
    tables: dict[str, pd.DataFrame] | None = None
    summary: dict = field(default_factory=dict)

    @property
    def errors(self) -> list[str]:
        return [m for level, m in self.problems if level == "error"]


def _rows(index, limit: int = 5) -> str:
    """'rows 3, 7 and 9' (spreadsheet row numbers: the header is row 1)."""
    nums = [str(int(i) + 2) for i in list(index)[:limit]]
    extra = len(index) - len(nums)
    if extra:
        return f"rows {', '.join(nums)} and {extra} more"
    if len(nums) == 1:
        return f"row {nums[0]}"
    return f"rows {', '.join(nums[:-1])} and {nums[-1]}"


def _names(values, limit: int = 6) -> str:
    values = [str(v) for v in values]
    return ", ".join(values[:limit]) + (f" and {len(values) - limit} more" if len(values) > limit else "")


def _blank(text: pd.Series) -> pd.Series:
    return text.isna() | (text == "")


def _first_line(source) -> str | None:
    """The header line of a file (a path or bytes), or None if it can't be peeked at."""
    try:
        if isinstance(source, (bytes, bytearray)):
            raw = bytes(source[:4096])
        else:
            with open(source, "rb") as fh:
                raw = fh.read(4096)
        lines = raw.decode("utf-8-sig", errors="replace").splitlines()
        return lines[0] if lines else None
    except (OSError, TypeError, ValueError):
        return None


def read_table(source, label: str = "") -> tuple[pd.DataFrame | None, str | None]:
    """Read one CSV file (a path or uploaded bytes) as text, so the checks
    see exactly what was typed. Returns (table, None) or (None, a message)."""
    import io
    first = _first_line(source)
    if first and ";" in first and "," not in first:
        return None, (f"{label or 'The file'} has semicolons between its values, and StrainScope reads commas. "
                      "Save it again as 'CSV UTF-8 (comma delimited)', or set your spreadsheet program's list "
                      "separator to a comma (docs/10-workflow-and-your-data.md, section 12).")
    try:
        data = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
        table = pd.read_csv(data, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8-sig")
    except UnicodeDecodeError:
        return None, (f"{label or 'The file'} isn't UTF-8 text. In a spreadsheet program, save it as "
                      "'CSV UTF-8 (comma delimited)'.")
    except Exception as err:                                        # noqa: BLE001
        return None, f"{label or 'The file'} couldn't be read as CSV: {err}"
    return table, None


def check_tables(genomics: pd.DataFrame, metabolomics: pd.DataFrame, phenotype: pd.DataFrame,
                 effective_at: float = EFFECTIVE_AT, shared: bool = False) -> DatasetCheck:
    """Check three tables read as text (read_table) and return them ready to
    save, in the library's raw layout: genes as 1/0/empty, compounds as
    numbers, the trial results with is_effective. Nothing is cleaned here:
    duplicates, odd spellings of a genus, impossible scores and lab drift are
    left for Phase 2, which cleans them and counts every change. What can't
    be read at all is an error, and nothing is saved until there are none."""
    limits = LIMITS["shared" if shared else "local"]
    problems: list[tuple[str, str]] = []
    raw = {"genomics": genomics.copy(), "metabolomics": metabolomics.copy(), "phenotype": phenotype.copy()}

    # -- the headers --------------------------------------------------------------
    for name, df in raw.items():
        headers = [str(c).strip() for c in df.columns]
        # strain_id (and, in the trial results, the known columns) in any case
        fixed = []
        for h in headers:
            low = h.lower()
            if low == "strain_id" or (name == "phenotype" and low in PHENOTYPE_ORDER):
                fixed.append(low)
            else:
                fixed.append(h)
        df.columns = fixed
        dup = sorted({c for c in fixed if fixed.count(c) > 1})
        if dup:
            problems.append(("error", f"In {WHAT[name]}, these columns appear twice: {_names(dup)}."))
        if "strain_id" not in fixed:
            problems.append(("error", f"{WHAT[name].capitalize()} needs a `strain_id` column (the first "
                                      "column of every table). Download the template to see the layout."))
        if len(df) == 0:
            problems.append(("error", f"{WHAT[name].capitalize()} has a header but no strains."))
    for col in ("kingdom", "suppression_score"):
        if col not in raw["phenotype"].columns:
            problems.append(("error", f"The trial-results table needs a `{col}` column."))
    if any(level == "error" for level, _ in problems):
        return DatasetCheck(False, problems)

    genes = [c for c in raw["genomics"].columns if c != "strain_id"]
    compounds = [c for c in raw["metabolomics"].columns if c != "strain_id"]
    for name, cols, word in (("genomics", genes, "gene"), ("metabolomics", compounds, "compound")):
        if len(cols) < 2:
            problems.append(("error", f"{WHAT[name].capitalize()} needs at least two {word} columns "
                                      "(integration reads two layers, each with several columns)."))
        bad = [c for c in cols if not NAME_RULE.fullmatch(c)]
        if bad:
            problems.append(("error", f"These {word} names in {WHAT[name]} can't be used: {_names(bad)}. A name "
                                      "starts with a letter and holds only letters, digits and _ (at most 40), "
                                      "so it works everywhere, in SQL too: for example `srfAA_2` instead of "
                                      "`srfAA-2`, `x16S` instead of `16S`."))
        limit = limits["genes" if word == "gene" else "compounds"]
        if len(cols) > limit:
            problems.append(("error", f"{WHAT[name].capitalize()} has {len(cols)} {word} columns; "
                                      f"{'this shared copy' if shared else 'StrainScope'} takes up to {limit}."))
    both = sorted(set(genes) & set(compounds))
    if both:
        problems.append(("error", f"A name can't be both a gene and a compound: {_names(both)}. "
                                  "Rename one of each pair."))
    reserved = sorted(set(genes + compounds) & set(PHENOTYPE_ORDER))
    if reserved:
        problems.append(("error", f"These names are kept for the trial-results table: {_names(reserved)}."))
    extra = [c for c in raw["phenotype"].columns if c not in PHENOTYPE_ORDER]
    if extra:
        problems.append(("note", f"Columns of the trial-results table that StrainScope doesn't use were left out: "
                                 f"{_names(extra)}."))
    if any(level == "error" for level, _ in problems):
        return DatasetCheck(False, problems)

    # -- strain ids: present in every table ---------------------------------------
    repeated = {}
    for name, df in raw.items():
        ids = df["strain_id"].astype("string").str.strip()
        empty = _blank(ids)
        if empty.any():
            problems.append(("error", f"`strain_id` is empty in {WHAT[name]} on {_rows(df.index[empty])}."))
        df["strain_id"] = ids
        dup = sorted(set(ids[~empty & ids.duplicated()]))
        if dup:
            repeated[name] = dup
    if repeated:
        where = [WHAT[n] for n in repeated]
        where = where[0] if len(where) == 1 else ", ".join(where[:-1]) + " and " + where[-1]
        dup = sorted(set().union(*repeated.values()))
        problems.append(("note", f"{len(dup)} strain(s) appear more than once ({_names(dup, 4)}), in {where}. "
                                 "Cleaning (Phase 2) keeps the first row of each and counts the rest in "
                                 "its ledger."))
    if any(level == "error" for level, _ in problems):
        return DatasetCheck(False, problems)
    sets = {name: set(df["strain_id"]) for name, df in raw.items()}
    everywhere = sets["genomics"] & sets["metabolomics"] & sets["phenotype"]
    for name, df in raw.items():
        left_out = sorted(sets[name] - everywhere)
        if left_out:
            problems.append(("warning", f"{len(left_out)} strain(s) of {WHAT[name]} are missing from another "
                                        f"table and are left out: {_names(left_out, 4)}. Integration needs "
                                        "every strain in all three tables."))
            raw[name] = df[df["strain_id"].isin(everywhere)].copy()

    # -- the trial results --------------------------------------------------------
    phe = raw["phenotype"]          # the index stays the file's row order, so messages name the right row
    kingdom = phe["kingdom"].astype("string").str.strip()
    mapped = kingdom.str.lower().map(KINGDOM_SPELLINGS)
    unknown = mapped.isna()
    if unknown.any():
        found = sorted(set(kingdom[unknown & ~_blank(kingdom)]))
        problems.append(("error", f"`kingdom` must be Bacteria, Fungi, Yeast or Oomycete "
                                  f"(found {_names(found) or 'empty cells'} on {_rows(phe.index[unknown])}). "
                                  "StrainScope compares each strain with others of its kingdom."))
    phe["kingdom"] = mapped
    score_text = phe["suppression_score"].astype("string").str.strip()
    score = pd.to_numeric(score_text, errors="coerce")
    unreadable = ~_blank(score_text) & score.isna()
    if unreadable.any():
        comma = any(re.fullmatch(r"-?\d+,\d+", str(v)) for v in score_text[unreadable])
        problems.append(("error", f"`suppression_score` must be a number (the % of disease suppressed); found "
                                  f"{_names(sorted(set(score_text[unreadable])), 4)} on {_rows(phe.index[unreadable])}."
                                  + (" Use a full stop as the decimal mark (52.5, not 52,5)." if comma else "")))
    no_score = _blank(score_text)
    if no_score.any() and not unreadable.any():
        problems.append(("warning", f"{int(no_score.sum())} strain(s) have no `suppression_score` and are left "
                                    f"out ({_rows(phe.index[no_score])}): a model can't learn from a strain "
                                    "without a result."))
    phe["suppression_score"] = score
    outside = (score < 0) | (score > 100)
    if outside.any():
        problems.append(("note", f"{int(outside.sum())} score(s) are below 0 or above 100 "
                                 f"({_rows(phe.index[outside])}). Cleaning clips them into 0 to 100 and "
                                 "counts them."))
    if "is_effective" in phe.columns:
        text = phe["is_effective"].astype("string").str.strip().str.lower()
        given = text.map(YES_NO)
        bad = ~_blank(text) & given.isna()
        if bad.any():
            problems.append(("error", f"`is_effective` must be 1 or 0 (or yes/no); found "
                                      f"{_names(sorted(set(phe.loc[bad, 'is_effective'])), 4)} on {_rows(phe.index[bad])}."))
        filled = int(_blank(text).sum())
        phe["is_effective"] = given.fillna((score >= effective_at).astype(float))
        if filled:
            problems.append(("note", f"`is_effective` was empty for {filled} strain(s); they count as effective "
                                     f"when their score is at least {effective_at:g} %."))
    else:
        phe["is_effective"] = (score >= effective_at).astype(float)
        problems.append(("note", f"There's no `is_effective` column, so a strain counts as effective when its "
                                 f"`suppression_score` is at least {effective_at:g} % (you can choose another line)."))
    if "growth_promotion" in phe.columns:                # a second outcome, kept but not modelled
        values = pd.to_numeric(phe["growth_promotion"], errors="coerce")
        bad = ~_blank(phe["growth_promotion"].astype("string").str.strip()) & values.isna()
        if bad.any():
            problems.append(("error", f"`growth_promotion` must be a number; found "
                                      f"{_names(sorted(set(phe.loc[bad, 'growth_promotion'])), 4)} on "
                                      f"{_rows(phe.index[bad])}."))
        phe["growth_promotion"] = values
    if "batch_id" not in phe.columns:
        problems.append(("note", "There's no `batch_id` column, so cleaning has no lab drift to correct "
                                 "(it says so in its ledger)."))
    if "genus" not in phe.columns:
        problems.append(("note", "There's no `genus` column, so the knowledge graph has no genus nodes for "
                                 "these strains; everything else works the same."))
    keep = ~no_score & ~unreadable
    phe = phe[keep]
    kept_ids = set(phe["strain_id"])

    # -- genes: 1, 0 or empty -------------------------------------------------------
    gen = raw["genomics"][raw["genomics"]["strain_id"].isin(kept_ids)].copy()
    for g in genes:
        text = gen[g].astype("string").str.strip().str.lower()
        values = text.map(YES_NO)
        bad = ~_blank(text) & values.isna()
        if bad.any():
            problems.append(("error", f"Gene column `{g}` must hold 1 or 0 (or yes/no); found "
                                      f"{_names(sorted(set(gen.loc[bad, g])), 4)} on {_rows(gen.index[bad])}."))
        gen[g] = values.astype(float)

    # -- compounds: numbers, 0 or more ---------------------------------------------
    met = raw["metabolomics"][raw["metabolomics"]["strain_id"].isin(kept_ids)].copy()
    for c in compounds:
        text = met[c].astype("string").str.strip()
        values = pd.to_numeric(text, errors="coerce")
        bad = ~_blank(text) & values.isna()
        if bad.any():
            found = sorted(set(text[bad]))
            comma = any(re.fullmatch(r"\d+,\d+", str(v)) for v in found)
            problems.append(("error", f"Compound column `{c}` must hold numbers; found {_names(found, 4)} on "
                                      f"{_rows(met.index[bad])}."
                                      + (" Use a full stop as the decimal mark (2.5, not 2,5)." if comma else "")))
        negative = values < 0
        if negative.any():
            problems.append(("error", f"Compound column `{c}` has negative levels on {_rows(met.index[negative])}; "
                                      "a level can be 0 but not below."))
        met[c] = values
    if any(level == "error" for level, _ in problems):
        return DatasetCheck(False, problems)

    # -- enough to learn from? -------------------------------------------------------
    first = phe.drop_duplicates("strain_id")
    n = len(first)
    effective = int(first["is_effective"].sum())
    if n > limits["strains"]:
        problems.append(("error", f"The tables hold {n:,} strains; {'this shared copy' if shared else 'StrainScope'} "
                                  f"takes up to {limits['strains']:,}."
                                  + (" On your own computer the limit is higher." if shared else "")))
    if n < MIN_STRAINS:
        problems.append(("error", f"Only {n} strain(s) are in all three tables with a result; StrainScope needs "
                                  f"at least {MIN_STRAINS} to learn from and to test fairly."))
    elif min(effective, n - effective) < MIN_PER_CLASS:
        problems.append(("error", f"{effective} of the {n} strains are effective and {n - effective} aren't. "
                                  f"Each group needs at least {MIN_PER_CLASS}: a model learns the difference "
                                  "from both sides. A different line for 'effective' may help."))
    for name, df, cols, word in (("genomics", gen, genes, "gene"), ("metabolomics", met, compounds, "compound")):
        varying = [c for c in cols if _top_share(df[c]) < NEAR_CONSTANT]
        if len(varying) < 2 and len(cols) >= 2:
            problems.append(("error", f"In {WHAT[name]}, fewer than two {word} columns tell strains apart (the "
                                      f"rest hold one value in 95 % of strains or more), so this layer has "
                                      "nothing to integrate."))
        sparse = [c for c in cols if df[c].isna().mean() > 0.5]
        if sparse:
            problems.append(("warning", f"More than half of the cells are empty in these {word} columns: "
                                        f"{_names(sparse)}. Gaps are filled from the strain's own kingdom "
                                        "(Phase 3), which says little when most are gaps."))
    counts = first["kingdom"].value_counts()
    small = [k for k, v in counts.items() if v < 5]
    if small:
        problems.append(("warning", f"Very few strains of {', '.join(small)} (fewer than 5): comparisons within "
                                    "those kingdoms rest on very little."))
    gaps = int(gen[genes].isna().sum().sum() + met[compounds].isna().sum().sum())
    if gaps:
        problems.append(("note", f"{gaps:,} empty cell(s) are read as 'not known' or 'not measured', never as 0."))
    if any(level == "error" for level, _ in problems):
        return DatasetCheck(False, problems)

    phe = phe[[c for c in PHENOTYPE_ORDER if c in phe.columns]].reset_index(drop=True)
    phe["is_effective"] = phe["is_effective"].astype(int)
    summary = {"strains": n, "effective": effective, "genes": len(genes), "compounds": len(compounds),
               "kingdoms": {k: int(counts.get(k, 0)) for k in KINGDOMS if counts.get(k, 0)},
               "known_genes": _known(genes, "genomics"), "known_compounds": _known(compounds, "metabolomics")}
    return DatasetCheck(True, problems, {"genomics": gen.reset_index(drop=True), "metabolomics": met.reset_index(drop=True),
                                         "phenotype": phe}, summary)


def _top_share(column: pd.Series) -> float:
    values = column.dropna()
    return float(values.value_counts(normalize=True).iloc[0]) if len(values) else 1.0


def _known(names: list[str], block: str) -> list[str]:
    """Which of these names the domain model knows (the mechanism comes with them)."""
    from strainscope.ontology import FEATURE_MODES
    return [n for n in names if n in FEATURE_MODES]


# =============================================================================
# 2. SAVING, LISTING, REMOVING
# =============================================================================

def _base(base: Path | None) -> Path:
    """The folder that holds the datasets (data/processed/datasets/ unless a test says otherwise)."""
    return Path(base) if base is not None else paths.DATASETS


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def check_name(name: str, base: Path | None = None) -> str | None:
    """A sentence saying what's wrong with a new dataset name, or None."""
    if not NAME_RULE.fullmatch(name or ""):
        return ("A dataset name starts with a letter and holds only letters, digits and _ "
                "(at most 40), for example trial_2026.")
    if name.lower() == "library":
        return "'library' is the built-in library's name. Choose another."
    if (_base(base) / name).exists():
        return f"There's already a dataset called {name}. Choose another name, or remove that one first."
    return None


def create(name: str, tables: dict[str, pd.DataFrame] | None = None, kind: str = "yours", source: str = "",
           effective_at: float = EFFECTIVE_AT, quick: bool = False, seed: int | None = None,
           strains: int | None = None, notes: list[str] | None = None, temporary: bool = False,
           owner: str | None = None, base: Path | None = None) -> Path:
    """Make a dataset's folder and its dataset.json. With `tables` (yours),
    they're saved as raw/genomics.csv, metabolomics.csv and phenotype.csv; a
    simulated dataset gets its tables from the first step of its plan."""
    problem = check_name(name, base)
    if problem:
        raise ValueError(problem)
    if kind not in ("yours", "simulated"):
        raise ValueError("kind is 'yours' or 'simulated'")
    home = _base(base) / name
    (home / "raw").mkdir(parents=True)
    info = {"name": name, "label": f"dataset {name}", "kind": kind, "answer_key": kind == "simulated",
            "created": _now(), "last_used": _now(), "source": source, "effective_at": float(effective_at),
            "repeats": QUICK_REPEATS if quick else 10, "quick": bool(quick), "temporary": bool(temporary),
            "notes": notes or [], "steps": {}}
    if owner:
        info["owner"] = owner             # a shared copy: only the browser tab with this token lists it
    if kind == "simulated":
        info.update(seed=int(seed if seed is not None else 42), strains=int(strains or 600))
        info["source"] = source or f"src/strainscope/generate_data.py, seed {info['seed']}, {info['strains']} strains"
    else:
        if tables is None:
            raise ValueError("a dataset of your own needs its three tables")
        for t in TABLES:
            tables[t].to_csv(home / "raw" / f"{t}.csv", index=False)
        first = tables["phenotype"].drop_duplicates("strain_id")
        info.update(strains=int(len(first)), effective=int(first["is_effective"].sum()),
                    genes=int(tables["genomics"].shape[1] - 1), compounds=int(tables["metabolomics"].shape[1] - 1))
    write_info(home, info)
    return home


def write_info(home: Path, info: dict) -> None:
    (Path(home) / paths.INFO_FILE).write_text(json.dumps(info, indent=2), encoding="utf-8")


def update_info(dataset: str | Path, **changes) -> dict:
    """Change some fields of a dataset's dataset.json and return it."""
    home = paths.locate(dataset)
    info = paths.info(home)
    info.update(changes)
    write_info(home, info)
    return info


def record_step(dataset: str | Path, script: str, seconds: float) -> None:
    """Remember when a step last finished and how long it took (the Workflow
    page and `datasets.py show` print it). Never fails a run."""
    try:
        home = paths.locate(dataset)
        if home is None or not (home / paths.INFO_FILE).exists():
            return
        info = paths.info(home)
        info.setdefault("steps", {})[script] = {"finished": _now(), "seconds": round(float(seconds), 1)}
        info["last_used"] = _now()
        write_info(home, info)
    except Exception:                                    # noqa: BLE001  (a record, not the result)
        pass


def list_datasets(base: Path | None = None, owner: str | None = None) -> list[dict]:
    """Every dataset (newest first), each as its dataset.json plus its folder.
    With `owner`, only the temporary datasets made by that visitor of a
    shared copy (each browser tab has its own token)."""
    out = []
    if not _base(base).exists():
        return out
    for home in _base(base).iterdir():
        if home.is_dir() and (home / paths.INFO_FILE).exists():
            info = paths.info(home)
            if owner is not None and info.get("owner") != owner:
                continue
            out.append({**info, "home": home})
    return sorted(out, key=lambda d: d.get("created", ""), reverse=True)


def remove(dataset: str | Path, base: Path | None = None) -> None:
    """Delete a dataset's folder, and only a dataset's folder: it must sit in
    data/processed/datasets/ and hold a dataset.json."""
    home = paths.locate(dataset) if not isinstance(dataset, Path) else dataset.resolve()
    if home is None or home.parent.resolve() != _base(base).resolve() or not (home / paths.INFO_FILE).exists():
        raise ValueError(f"{dataset} isn't a dataset folder in {paths.rel(_base(base))}/")
    shutil.rmtree(home)


def sweep(base: Path | None = None, max_age_hours: float = SHARED_MAX_AGE_HOURS,
          keep: int = SHARED_MAX_DATASETS, busy: str | None = None) -> list[str]:
    """A shared copy's tidy-up: delete temporary datasets not used for
    `max_age_hours`, and the oldest beyond `keep`. A dataset being worked on
    (`busy`) is never deleted. Returns the names removed."""
    gone = []
    temporary = [d for d in list_datasets(base) if d.get("temporary")]
    now = time.time()

    def age(d) -> float:
        try:
            return now - datetime.fromisoformat(d.get("last_used") or d["created"]).timestamp()
        except (KeyError, ValueError):
            return float("inf")
    temporary.sort(key=age)
    for i, d in enumerate(temporary):
        if d["name"] == busy:
            continue
        if age(d) > max_age_hours * 3600 or i >= keep:
            try:
                remove(d["home"], base)
                gone.append(d["name"])
            except (OSError, ValueError):
                pass
    return gone


def new_owner_token() -> str:
    """A random token for one browser tab of a shared copy: the datasets it
    makes carry it, and only that tab lists them."""
    return secrets.token_hex(8)


def temporary_name(base: Path | None = None) -> str:
    while True:
        name = f"visit_{secrets.token_hex(4)}"
        if not (_base(base) / name).exists():
            return name


# =============================================================================
# 3. TEMPLATES AND AN EXAMPLE
# =============================================================================

def templates() -> dict[str, pd.DataFrame]:
    """Three empty tables in the right layout, with a few of the library's
    gene and compound names as examples of where columns go."""
    return {"genomics": pd.DataFrame(columns=["strain_id", "ituA", "srfAA", "chiA", "my_gene_1"]),
            "metabolomics": pd.DataFrame(columns=["strain_id", "iturin", "surfactin", "my_compound_1"]),
            "phenotype": pd.DataFrame(columns=["strain_id", "kingdom", "suppression_score", "genus",
                                               "batch_id", "is_effective"])}


def example(strains: int = 120, seed: int = 7) -> dict[str, pd.DataFrame]:
    """A small simulated library (seed 7, 120 strains) in the layout of the
    three tables, messy on purpose like the real thing. Good for trying the
    upload; it's simulated, so say so if you show its results."""
    from strainscope.generate_data import generate
    return generate(seed, strains)


def write_tables(tables: dict[str, pd.DataFrame], folder: Path) -> list[Path]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for t in TABLES:
        path = folder / f"{t}.csv"
        tables[t].to_csv(path, index=False)
        out.append(path)
    return out


# =============================================================================
# 4. HOW FAR A DATASET GOT: the steps and what each one found
# =============================================================================

# For each step: a file it writes at the end of its work (its "receipt"). A
# step is done when its receipt exists and is newer than every receipt before
# it, and, for your own data, newer than the raw tables it starts from.
RECEIPTS = {
    "generate_data.py": ("raw", "phenotype.csv"),
    "harmonize.py": ("processed", "cleaning_ledger.csv"),
    "integrate.py": ("integration", "signature_report_card.csv"),
    "model.py": ("model", "model_card.json"),
    "graph.py": ("graph", "explanations.csv"),
}


def receipt(f: paths.Folders, script: str) -> Path:
    where, name = RECEIPTS[script]
    return getattr(f, where) / name


@dataclass
class StepState:
    number: int
    script: str
    name: str
    command: str
    state: str          # "done", "stale" (what it reads changed since it ran, or isn't done) or "to do"
    seconds: float | None = None
    facts: list[str] = field(default_factory=list)


def progress(dataset: str | Path) -> list[StepState]:
    """Every step of the dataset's plan with its state and what it found."""
    from strainscope import service as sv
    f = paths.folders(dataset)
    info = paths.info(dataset)
    plan = sv.PIPELINES[sv.plan_for(dataset)]["steps"]
    out, latest, behind = [], 0.0, False      # newest receipt so far; an earlier step isn't done
    if plan[0][0] != "generate_data.py":       # your own data: its raw tables are what cleaning reads
        latest = max((p.stat().st_mtime for p in f.raw.glob("*.csv")), default=0.0)
    for number, step in enumerate(plan, start=1):
        script = step[0]
        path = receipt(f, script)
        if not path.exists():
            state = "to do"
        elif behind or path.stat().st_mtime < latest:
            state = "stale"                   # something before it ran later, or hasn't run
        else:
            state = "done"
        if path.exists():
            latest = max(latest, path.stat().st_mtime)
        behind = behind or state != "done"
        seconds = info.get("steps", {}).get(script, {}).get("seconds")
        out.append(StepState(number, script, sv.STEP_NAMES[script], sv.step_label(step), state, seconds,
                             facts(f, script) if state != "to do" else []))
    return out


def facts(f: paths.Folders, script: str) -> list[str]:
    """A few lines on what one step found, read from its result files."""
    try:
        if script == "generate_data.py":
            phe = pd.read_csv(f.raw / "phenotype.csv")
            first = phe.drop_duplicates("strain_id")
            gen = pd.read_csv(f.raw / "genomics.csv", nrows=1)
            met = pd.read_csv(f.raw / "metabolomics.csv", nrows=1)
            return [f"{len(first):,} strains, {int(first['is_effective'].sum())} effective "
                    f"({first['is_effective'].mean():.0%})",
                    f"{gen.shape[1] - 1} genes and {met.shape[1] - 1} compounds per strain"]
        if script == "harmonize.py":
            led = pd.read_csv(f.processed / "cleaning_ledger.csv")
            dropped = int((led["rows_in"] - led["rows_out"]).max()) if len(led) else 0
            changed = int(led.loc[~led["step"].isin(["account_missing"]), "cells_changed"].sum())
            missing = int(led.loc[led["step"] == "account_missing", "cells_changed"].sum())
            lines = [f"{dropped} duplicate row(s) removed per table, {changed:,} cells cleaned",
                     f"{missing:,} empty cells kept as empty (filled later, by each method itself)"]
            skipped = led.loc[led["note"].astype(str).str.startswith("skipped"), "note"]
            return lines + [str(n) for n in skipped]
        if script == "integrate.py":
            board = pd.read_csv(f.integration / "python_scoreboard.csv")
            real = board[~board["approach"].str.startswith("Control")]
            best = real.sort_values("ber_mean").iloc[0]
            sel = pd.read_csv(f.integration / "python_selection.csv")
            picked = sel.loc[sel["selection_frequency"] >= 0.8, "feature"].tolist()
            lines = [f"best: {best['approach']}, balanced error {best['ber_mean']:.3f} (a coin: 0.50)",
                     f"{len(picked)} feature(s) picked in 80 % of folds or more: {_names(picked, 6) or 'none'}"]
            if (f.integration / "diablo_summary.csv").exists():
                s = pd.read_csv(f.integration / "diablo_summary.csv").set_index("key")["value"]
                lines.append(f"DIABLO (R): balanced error {float(s['cv_ber_final']):.3f}, "
                             f"{s['n_signature_features']} features in its signature")
            else:
                lines.append("DIABLO (R) didn't run here (R isn't installed); the Python methods cover it")
            return lines
        if script == "model.py":
            card = json.loads((f.model / "model_card.json").read_text(encoding="utf-8"))
            perf, top = card["cross_validated_performance"], card["top_n_check"]
            return [f"winner: {card['model']}, balanced error {perf['ber']:.3f}, AUC {perf['auc']:.3f}",
                    f"of the top {top['n']} strains, {top['truly_effective']} are effective "
                    f"(chance: about {top['expected_by_chance']:.0f})"]
        if script == "graph.py":
            summary = pd.read_csv(f.graph / "graph_summary.csv")
            nodes = int(summary.loc[summary["kind"] == "nodes", "count"].sum())
            edges = int(summary.loc[summary["kind"] == "edges", "count"].sum())
            expl = pd.read_csv(f.graph / "explanations.csv")
            with_path = expl.loc[expl["kind"] == "mechanism", "strain_id"].nunique()
            return [f"{nodes:,} nodes and {edges:,} edges, each edge with its source",
                    f"{with_path:,} strain(s) with at least one mechanism path to disease suppression"]
    except Exception as err:                                   # noqa: BLE001  (a summary, never a failure)
        return [f"(couldn't read the results: {err})"]
    return []


# =============================================================================
# 5. THE COMMAND LINE
# =============================================================================

def _print_check(check: DatasetCheck) -> None:
    mark = {"error": "✗", "warning": "!", "note": "·"}
    for level, message in check.problems:
        print(f"  {mark[level]} {message}")
    if check.ok:
        s = check.summary
        kingdoms = ", ".join(f"{k} {v}" for k, v in s["kingdoms"].items())
        print(f"  ✓ {s['strains']:,} strains ({s['effective']} effective) · {s['genes']} genes · "
              f"{s['compounds']} compounds · {kingdoms}")
        known = s["known_genes"] + s["known_compounds"]
        print(f"    StrainScope knows {len(known)} of these names (their mechanisms join the knowledge graph)"
              + (f": {_names(known, 8)}" if known else ""))
    else:
        print(f"  ✗ {len(check.errors)} problem(s) to fix before the tables can be used.")


def _read_folder(folder: Path) -> tuple[dict | None, list[str]]:
    tables, problems = {}, []
    for t in TABLES:
        path = Path(folder) / f"{t}.csv"
        if not path.exists():
            problems.append(f"{paths.rel(path)} is missing (the three files are genomics.csv, "
                            "metabolomics.csv and phenotype.csv)")
            continue
        table, problem = read_table(path, paths.rel(path))
        if problem:
            problems.append(problem)
        tables[t] = table
    return (tables if not problems else None), problems


def _print_progress(name: str) -> None:
    info = paths.info(name)
    print(f"  ── {name}: {info.get('source', '')} ──")
    mark = {"done": "✓", "stale": "!", "to do": "·"}
    word = {"done": "done", "stale": "run again", "to do": "to do"}
    for s in progress(name):
        took = f"  ({s.seconds:.0f} s)" if s.seconds else ""
        print(f"  {mark[s.state]} {s.number}. {s.name:<36} {word[s.state]}{took}")
        for line in s.facts:
            print(f"       {line}")
    print(f"  Run every step: python src/strainscope/pipeline.py --dataset {name}")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):          # ✓ and ✗ must print on Windows too
        if (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="StrainScope Phase 9: datasets of your own "
                                                 "(docs/10-workflow-and-your-data.md).")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("template", help="write three empty tables to fill in")
    p.add_argument("folder")
    p = sub.add_parser("example", help="write 120 simulated strains in the three-table layout")
    p.add_argument("folder")
    p = sub.add_parser("check", help="check genomics.csv, metabolomics.csv and phenotype.csv in a folder")
    p.add_argument("folder")
    p.add_argument("--effective-at", type=float, default=EFFECTIVE_AT,
                   help="a strain is effective from this score on, when there's no is_effective column (65)")
    p = sub.add_parser("new", help="save a dataset: three tables (--from) or a simulated library (--simulate)")
    p.add_argument("name")
    p.add_argument("--from", dest="folder", help="the folder with genomics.csv, metabolomics.csv, phenotype.csv")
    p.add_argument("--simulate", action="store_true", help="a fresh simulated library instead")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--strains", type=int, default=600)
    p.add_argument("--effective-at", type=float, default=EFFECTIVE_AT)
    p.add_argument("--quick", action="store_true",
                   help=f"quick settings: {QUICK_REPEATS} cross-validation repeats instead of 10")
    sub.add_parser("list", help="every dataset and how far it got")
    p = sub.add_parser("show", help="one dataset, step by step")
    p.add_argument("name")
    p = sub.add_parser("remove", help="delete a dataset's folder")
    p.add_argument("name")
    p.add_argument("--yes", action="store_true", help="don't ask first")
    args = parser.parse_args(argv)

    if args.command in ("template", "example"):
        tables = templates() if args.command == "template" else example()
        for path in write_tables(tables, Path(args.folder)):
            print(f"  wrote {paths.rel(path)}")
        if args.command == "example":
            print("  These 120 strains are simulated (seed 7), messy on purpose. Try: "
                  f"python src/strainscope/datasets.py check {args.folder}")
        return 0
    if args.command == "check" or (args.command == "new" and not args.simulate):
        folder = args.folder
        if not folder:
            parser.error("new needs --from FOLDER (three tables) or --simulate")
        tables, problems = _read_folder(Path(folder))
        if tables is None:
            for problem in problems:
                print(f"  ✗ {problem}")
            return 1
        check = check_tables(tables["genomics"], tables["metabolomics"], tables["phenotype"], args.effective_at)
        _print_check(check)
        if not check.ok:
            return 1
        if args.command == "check":
            print(f"  Save them as a dataset: python src/strainscope/datasets.py new <name> --from {folder}")
            return 0
        try:
            home = create(args.name, check.tables, "yours", f"three CSV files from {folder}",
                          args.effective_at, args.quick,
                          notes=[m for level, m in check.problems if level != "error"])
        except ValueError as err:
            print(f"  ✗ {err}")
            return 1
        print(f"  saved → {paths.rel(home)}/")
        print(f"  Next: python src/strainscope/pipeline.py --dataset {args.name}")
        return 0
    if args.command == "new":
        if not 40 <= args.strains <= LIMITS["local"]["strains"]:
            parser.error(f"--strains must be between 40 and {LIMITS['local']['strains']}")
        try:
            home = create(args.name, kind="simulated", seed=args.seed, strains=args.strains,
                          effective_at=EFFECTIVE_AT, quick=args.quick)
        except ValueError as err:
            print(f"  ✗ {err}")
            return 1
        print(f"  saved → {paths.rel(home)}/ (seed {args.seed}, {args.strains} strains"
              + (", quick settings" if args.quick else "") + ")")
        print(f"  Next: python src/strainscope/pipeline.py --dataset {args.name}")
        return 0
    if args.command == "list":
        found = list_datasets()
        if not found:
            print("  No datasets yet. Make one: python src/strainscope/datasets.py new demo --simulate --seed 7")
            return 0
        for d in found:
            steps = progress(d["home"])
            done = sum(s.state == "done" for s in steps)
            print(f"  {d['name']:<24} {d['kind']:<10} {d.get('strains', '?'):>6} strains   "
                  f"{done} of {len(steps)} steps done   {d.get('created', '')[:10]}")
        return 0
    if args.command == "show":
        if paths.locate(args.name) is None or not (paths.locate(args.name) / paths.INFO_FILE).exists():
            print(f"  ✗ no dataset called {args.name} (python src/strainscope/datasets.py list)")
            return 1
        _print_progress(args.name)
        return 0
    if args.command == "remove":
        home = paths.locate(args.name)
        if home is None or not (home / paths.INFO_FILE).exists():
            print(f"  ✗ no dataset called {args.name}")
            return 1
        if not args.yes:
            answer = input(f"  Delete {paths.rel(home)}/ and everything in it? Type yes: ")
            if answer.strip().lower() != "yes":
                print("  Nothing deleted.")
                return 0
        remove(home)
        print(f"  deleted {paths.rel(home)}/")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
