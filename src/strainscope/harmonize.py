"""
harmonize.py — StrainScope Phase 2: cleaning, quality control, and the database.
================================================================================

WHAT THIS MODULE DOES (in one sentence)
---------------------------------------
It takes the three raw, deliberately-messy tables from Phase 1, cleans them
step by documented step, records every change in a "cleaning ledger", and loads
the clean result — plus any real tables from Phase 1b — into one DuckDB
database file that the rest of the project (and you, with SQL) can question.

THE GOLDEN RULES OF CLEANING (read before the code)
---------------------------------------------------
1. NEVER edit the raw files. Raw data is evidence; cleaning produces NEW files.
   (You can always re-run cleaning; you can never un-edit evidence.)
2. EVERY change is counted. The ledger records rows in, rows out, and cells
   changed for every step — nothing vanishes silently.
3. Decisions are WRITTEN DOWN, with reasons. "We capped outliers at 5×IQR
   because…" beats a mystery number every time.
4. Cleaning is IDEMPOTENT: run it twice, get the identical result. That's what
   makes it trustworthy and re-runnable.

ONE FILE, TWO ROLES (a Python idiom worth knowing)
--------------------------------------------------
This file is both a LIBRARY (other code — the app, the tests — imports its
functions) and a SCRIPT (you run it directly). The functions are the reusable
machinery; `main()` at the bottom is the narrative that drives them in order.

HOW TO RUN IT
-------------
    python src/strainscope/harmonize.py

Outputs:
  data/processed/genomics_clean.csv, metabolomics_clean.csv, phenotype_clean.csv
  data/processed/strainscope.duckdb      <- the database (synthetic + real tables)
  and a printed cleaning ledger.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REAL = PROCESSED / "real"
DB_PATH = PROCESSED / "strainscope.duckdb"

# --- The vocabulary the messy text must be harmonised INTO -------------------
# (One agreed spelling per real-world thing. This tiny "controlled vocabulary"
#  is the whole trick behind text harmonisation.)
GENUS_FIXES = {"Psuedomonas": "Pseudomonas"}     # the deliberate Phase-1 typo
METAB_COLS_HINT = None  # discovered from the data; kept for readability


# =============================================================================
# THE LEDGER — every step reports what it did, in numbers
# =============================================================================

class Ledger:
    """A running record of what cleaning changed. Printed at the end and
    returned to callers (the tests read it; a later phase can store it)."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def add(self, step: str, table: str, rows_in: int, rows_out: int,
            cells_changed: int, note: str) -> None:
        self.entries.append({"step": step, "table": table, "rows_in": rows_in,
                             "rows_out": rows_out, "cells_changed": cells_changed,
                             "note": note})

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.entries)

    def print(self) -> None:
        print("\n  ── Cleaning ledger — every change, counted ─────────────────")
        for e in self.entries:
            delta = e["rows_in"] - e["rows_out"]
            rows = (f"{e['rows_in']}→{e['rows_out']} rows"
                    + (f" (−{delta})" if delta else ""))
            print(f"  {e['step']:<22} {e['table']:<13} {rows:<22} "
                  f"{e['cells_changed']:>6} cells   {e['note']}")
        print("  ────────────────────────────────────────────────────────────")


# =============================================================================
# CLEANING FUNCTIONS — one job each, each honest about what it changed
# =============================================================================

def drop_duplicate_strains(df: pd.DataFrame, table: str, ledger: Ledger) -> pd.DataFrame:
    """Remove repeated strain rows (same strain_id recorded twice).

    WHY FIRST: duplicates distort every count and statistic computed after
    them, so de-duplication always leads. We keep the FIRST occurrence — with
    exact duplicates the choice is cosmetic, but stating it makes the rule
    reproducible."""
    rows_in = len(df)
    out = df.drop_duplicates(subset="strain_id", keep="first").reset_index(drop=True)
    ledger.add("drop_duplicates", table, rows_in, len(out), 0,
               f"{rows_in - len(out)} duplicate strain rows removed")
    return out


def harmonize_text(df: pd.DataFrame, ledger: Ledger) -> pd.DataFrame:
    """Make the messy text columns speak with one voice.

    Three moves, in order:
      1. strip stray spaces ("` rhizosphere`" -> "rhizosphere")
      2. unify case (genus Title-case: "trichoderma" -> "Trichoderma";
         sites lower-case: "Endosphere" -> "endosphere")
      3. fix known typos from a written-down mapping ("Psuedomonas" ->
         "Pseudomonas") — never by guessing, always from an explicit list."""
    out = df.copy()
    changed = 0
    for col, case in (("genus", "title"), ("collection_site", "lower")):
        before = out[col].copy()
        cleaned = out[col].astype(str).str.strip()
        cleaned = cleaned.str.title() if case == "title" else cleaned.str.lower()
        if col == "genus":
            cleaned = cleaned.replace(GENUS_FIXES)
        out[col] = cleaned
        changed += int((before != cleaned).sum())
    ledger.add("harmonize_text", "phenotype", len(out), len(out), changed,
               "stripped spaces, unified case, fixed known typos")
    return out


def clip_impossible_scores(df: pd.DataFrame, ledger: Ledger) -> pd.DataFrame:
    """A suppression percentage cannot be below 0 or above 100 — values outside
    that range are measurement noise, and we CLIP them to the boundary.

    Why clip rather than delete? The strain itself is fine; only the reading
    overshot. Deleting would throw away a real sample over a boundary wobble."""
    out = df.copy()
    mask = (out["suppression_score"] < 0) | (out["suppression_score"] > 100)
    out["suppression_score"] = out["suppression_score"].clip(0, 100)
    ledger.add("clip_impossible", "phenotype", len(out), len(out), int(mask.sum()),
               f"{int(mask.sum())} scores clipped into [0, 100]")
    return out


def cap_outliers(df: pd.DataFrame, metab_cols: list[str], ledger: Ledger,
                 mult: float = 3.0) -> pd.DataFrame:
    """Tame the wild measurement spikes in the metabolite readings.

    THE RULE (written down, so it's reproducible): for each metabolite, any
    value above  mult × its 95th percentile  (mult = 3) is CAPPED to that
    ceiling. Reading it plainly: the 95th percentile is "the upper edge of
    plausible production"; a value THREE TIMES beyond that edge is a
    measurement artifact, not biology.

    WHY NOT the textbook Q3 + k·IQR fence? Because our abundances are
    BIMODAL — strains without the producing gene sit in a low "trace" hump,
    strains with it in a high "producer" hump. For weapons carried by only one
    kingdom, the quartiles land inside the trace hump, the fence lands BELOW
    the real producers, and the rule flattens genuine biology (verified: it
    would have capped 779 cells here — six times the known injected spikes).
    Textbook rules assume one-humped data; presence/absence chemistry has two.

    HONEST LIMITATION (kept, not hidden): a spike of a *trace* value lands
    inside the legitimate producer range and is indistinguishable from real
    production without gene context. Cleaning caps what is provably absurd and
    documents that some corruption survives — the modelling phases are told.

    Why CAP (winsorise) rather than delete? The strain is real; only one
    reading spiked. Capping keeps the sample, removes the distortion, and the
    ledger records exactly how many cells were touched."""
    out = df.copy()
    capped = 0
    for col in metab_cols:
        ceiling = mult * out[col].quantile(0.95)
        mask = out[col] > ceiling
        out.loc[mask, col] = ceiling
        capped += int(mask.sum())
    ledger.add("cap_outliers", "metabolomics", len(out), len(out), capped,
               f"values above {mult}×p95 capped ({capped} cells); moderate "
               f"spikes are indistinguishable from real producers — documented")
    return out


def correct_batch_effect(df: pd.DataFrame, batch: pd.Series,
                         metab_cols: list[str], ledger: Ledger) -> pd.DataFrame:
    """Remove the systematic drift between lab batches (median-scaling).

    THE IDEA, plainly: if batch 3's readings run ~15% hot for a metabolite
    (its batch median is 1.15× the overall median), divide batch 3's values for
    that metabolite by 1.15. Do that per metabolite, per batch. Medians (not
    means) so the correction can't be dragged by leftover extremes.

    ORDER MATTERS: this runs AFTER outlier capping — otherwise one spike could
    poison its whole batch's scaling factor."""
    out = df.copy()
    # Whole-number CSVs parse as integers; scaling produces decimals, and
    # writing decimals into an integer column is an error in modern pandas.
    # Coerce to float first so the function is safe for ANY input table.
    out[metab_cols] = out[metab_cols].astype(float)
    adjusted = 0
    for col in metab_cols:
        overall = out[col].median()
        for b in sorted(batch.dropna().unique()):
            sel = (batch == b)
            b_median = out.loc[sel, col].median()
            if pd.notna(b_median) and b_median > 0 and pd.notna(overall):
                factor = b_median / overall
                out.loc[sel, col] = out.loc[sel, col] / factor
                adjusted += int(sel.sum())
    out[metab_cols] = out[metab_cols].round(3)
    ledger.add("correct_batch", "metabolomics", len(out), len(out), adjusted,
               "per-batch median-scaling toward the overall median")
    return out


def account_missing(dfs: dict[str, pd.DataFrame], ledger: Ledger) -> None:
    """COUNT the missing values — and deliberately leave them missing.

    This is a decision, not an omission. Filling gaps ("imputation") bakes in
    assumptions that depend on what you'll do downstream — the integration and
    modelling phases will choose their own strategies, openly. Cleaning's job
    is to make missingness VISIBLE and COUNTED, not to hide it. In the
    database, these gaps become proper SQL NULLs."""
    for name, df in dfs.items():
        n = int(df.isna().sum().sum())
        ledger.add("account_missing", name, len(df), len(df), n,
                   f"{n} missing cells kept as NULL (imputation is a modelling "
                   f"choice, made later)")


# =============================================================================
# THE DATABASE — load clean synthetic + any real tables into DuckDB
# =============================================================================

def load_to_duckdb(clean: dict[str, pd.DataFrame], db_path: Path = DB_PATH) -> list[str]:
    """Write every clean table into one DuckDB database file.

    Also loads EVERY CSV found in data/processed/real/ as a table named after
    the file (real_strains.csv -> table real_strains). That "load whatever is
    there" design means future real sources (Tier 2's NCBI and Metabolomics
    Workbench tables) join the database automatically, with no changes here.

    Returns the list of table names created (the tests check it)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()          # rebuild from scratch => idempotent
    con = duckdb.connect(str(db_path))
    created: list[str] = []
    for name, df in clean.items():
        con.register("df_tmp", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df_tmp")
        con.unregister("df_tmp")
        created.append(name)
    if REAL.exists():
        for csv in sorted(REAL.glob("*.csv")):
            if csv.stat().st_size == 0:
                continue
            table = csv.stem                      # real_strains.csv -> real_strains
            con.execute(
                f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto('{csv.as_posix()}')")
            created.append(table)
    con.close()
    return created


# =============================================================================
# MAIN — the narrative: raw -> cleaned -> counted -> stored
# =============================================================================

def run(verbose: bool = True) -> tuple[dict[str, pd.DataFrame], Ledger, list[str]]:
    """Run the whole cleaning pipeline; returns (clean tables, ledger, db tables)."""
    ledger = Ledger()

    genomics = pd.read_csv(RAW / "genomics.csv")
    metabolomics = pd.read_csv(RAW / "metabolomics.csv")
    phenotype = pd.read_csv(RAW / "phenotype.csv")
    metab_cols = [c for c in metabolomics.columns if c != "strain_id"]

    # 1. Duplicates first — everything after depends on honest row counts.
    genomics = drop_duplicate_strains(genomics, "genomics", ledger)
    metabolomics = drop_duplicate_strains(metabolomics, "metabolomics", ledger)
    phenotype = drop_duplicate_strains(phenotype, "phenotype", ledger)

    # 2. Text: one agreed spelling per real-world thing.
    phenotype = harmonize_text(phenotype, ledger)

    # 3. Impossible values: clip to the physically possible range.
    phenotype = clip_impossible_scores(phenotype, ledger)

    # 4. Outliers BEFORE batch correction (a spike must not poison a batch factor).
    metabolomics = cap_outliers(metabolomics, metab_cols, ledger)

    # 5. Batch effect: remove the lab drift, keep the biology.
    batch = phenotype.set_index("strain_id")["batch_id"]
    batch_aligned = metabolomics["strain_id"].map(batch)
    metabolomics = correct_batch_effect(metabolomics, batch_aligned, metab_cols, ledger)

    # 6. Missingness: counted, kept, explained.
    clean = {"genomics": genomics, "metabolomics": metabolomics,
             "phenotype": phenotype}
    account_missing(clean, ledger)

    # Write the clean CSVs (never overwriting raw).
    PROCESSED.mkdir(parents=True, exist_ok=True)
    for name, df in clean.items():
        df.to_csv(PROCESSED / f"{name}_clean.csv", index=False)

    tables = load_to_duckdb(clean)

    if verbose:
        for name, df in clean.items():
            print(f"  wrote data/processed/{name}_clean.csv  "
                  f"({len(df):,} rows, {df.shape[1]} columns)")
        ledger.print()
        print(f"\n  Database: data/processed/{DB_PATH.name}")
        print(f"  Tables loaded: {', '.join(tables)}")
        real_n = sum(t.startswith('real_') for t in tables)
        print(f"  ({real_n} real table(s) auto-loaded from data/processed/real/ — "
              "future sources join automatically)")
        print("\n  Raw files remain untouched — cleaning is re-runnable, evidence is safe.")
    return clean, ledger, tables


if __name__ == "__main__":
    run()
