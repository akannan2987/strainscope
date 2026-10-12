"""
src/strainscope/service.py (StrainScope Phases 6 and 7): the service layer behind the app.
=========================================================================================

WHAT THIS MODULE IS
-------------------
One set of plain Python functions that every way into StrainScope uses: the
Streamlit app (app/streamlit_app.py), the assistants (Phases 6b and 7), and
the MCP server (src/strainscope/mcp_server.py, Phase 7b). In the restaurant
picture of docs/00-architecture.md, the scripts of
Phases 1 to 5 are the kitchen and the app is the dining room. This module is
the pass, the counter where finished plates are checked before a waiter takes
them out. Nothing here draws anything on a screen, so every function can be
tested without a browser (tests/test_service.py).

WHAT IT OFFERS
--------------
  status()                 what exists: the database, each phase's results, the model
  read_artifact()          one of the committed result tables of Phases 3, 4 and 5
  database_tables()        every table in the database, with its row count
  query_database()         read-only SQL with four guards (see SQL SAFETY below)
  cookbook_recipes()       the tested recipes of docs/QUERY_COOKBOOK.md, ready to run
  upload_template(), example_upload(), validate_upload(), score_upload()
                           your own strains: checked, scored by the saved model of
                           Phase 4 and explained by the knowledge graph of Phase 5
  neighbourhood()          one strain's corner of the graph, laid out for drawing
  ask_docs()               Ask StrainScope: a question about the project, answered from
                           its own documents (src/strainscope/ask.py), as plain data
  ask_data(), ask_graph(), explain_in_words()
                           Phase 7: a question about the data (src/strainscope/ask_data.py),
                           a question about how things connect (src/strainscope/ask_graph.py)
                           and a strain's rank in plain words (src/strainscope/narrate.py)
  check_model()            does the switched-on language model cite its sources? Four
                           questions through the real assistants, each answer shown or not
  release_info()           which version this copy is (from CHANGELOG.md)
  PIPELINES, pipeline_events(), run_pipeline()
                           the scripts of Phases 1 to 5, run in order, with live output
                           (the app's build buttons, and src/strainscope/pipeline.py, the
                           one-command pipeline of Phase 8)

THE COMMAND LINE (the manual path; the app is the automatic one)
-----------------------------------------------------------------
    python src/strainscope/service.py status
    python src/strainscope/service.py template my_strains.csv
    python src/strainscope/service.py score my_strains.csv
    python src/strainscope/service.py check-model      (only with a language model switched on)

SQL SAFETY (the SQL console in the app runs through query_database)
-------------------------------------------------------------------
1. The database is opened READ-ONLY, so CREATE, INSERT, UPDATE and DELETE fail.
2. File access is switched off, so a query can't read or write files on the
   computer (no read_csv('...'), no COPY ... TO '...'), and that setting is
   locked for the rest of the connection.
3. A timer interrupts any query still running after SQL_TIMEOUT_S seconds.
4. At most SQL_MAX_ROWS rows come back; the result says when it was cut.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import threading
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# Make `strainscope` importable no matter where the script is run from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "processed" / "strainscope.duckdb"
ARTIFACTS = ROOT / "artifacts"
COOKBOOK = ROOT / "docs" / "QUERY_COOKBOOK.md"

SQL_TIMEOUT_S = 10          # a query still running after this is stopped
SQL_MAX_ROWS = 10_000       # rows returned at most (the result says when it was cut)
SQL_MEMORY = "1GB"          # DuckDB's memory ceiling for console queries
MAX_UPLOAD_ROWS = 5_000     # strains per uploaded file
KINGDOMS = ("Bacteria", "Fungi", "Yeast", "Oomycete")
BORDERLINE = (0.30, 0.70)   # a chance in this range is "borderline" (Phase 4 section 11; Query Cookbook section 9)
P_UPLOAD = "your upload"    # the source recorded on edges built from an uploaded file

# Spellings people use for the four kingdoms, mapped to the library's names.
KINGDOM_SPELLINGS = {
    "bacteria": "Bacteria", "bacterium": "Bacteria", "bacterial": "Bacteria",
    "fungi": "Fungi", "fungus": "Fungi", "fungal": "Fungi",
    "yeast": "Yeast", "yeasts": "Yeast",
    "oomycete": "Oomycete", "oomycetes": "Oomycete",
}
GENE_WORDS = {"1": 1.0, "1.0": 1.0, "true": 1.0, "yes": 1.0, "y": 1.0,
              "0": 0.0, "0.0": 0.0, "false": 0.0, "no": 0.0, "n": 0.0}


# =============================================================================
# 1. WHAT EXISTS: the database, each phase's results, the model
# =============================================================================

def read_artifact(name: str, artifacts_dir: Path = ARTIFACTS) -> pd.DataFrame | None:
    """One committed result table, e.g. read_artifact('model/predictions.csv').
    Returns None (instead of failing) when the file isn't there yet."""
    path = Path(artifacts_dir) / name
    return pd.read_csv(path) if path.exists() else None


def model_card(artifacts_dir: Path = ARTIFACTS) -> dict | None:
    import json
    path = Path(artifacts_dir) / "model" / "model_card.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def database_tables(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Every table in the database with its row count, grouped by where it
    comes from. An empty table (no rows, the right columns) if there is no
    database yet."""
    columns = ["table", "rows", "group"]
    if not Path(db_path).exists():
        return pd.DataFrame(columns=columns)
    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        names = [r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables ORDER BY table_name").fetchall()]
        rows = [(n, con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]) for n in names]
    finally:
        con.close()
    out = pd.DataFrame(rows, columns=["table", "rows"])
    out["group"] = out["table"].map(table_group)
    return out[columns]


def table_group(name: str) -> str:
    """Which phase a table belongs to, from its name."""
    for prefix, group in (("int_", "Phase 3: integration"), ("ml_", "Phase 4: machine learning"),
                          ("kg_", "Phase 5: knowledge graph"), ("real_", "Real data (Phases 1b and 1c)")):
        if name.startswith(prefix):
            return group
    return "Clean library (Phase 2)"


@dataclass
class Check:
    """One line of the health check: what, whether it's fine, and the fix."""
    name: str
    ok: bool | None          # True = fine, False = needed and missing, None = optional and missing
    detail: str
    fix: str = ""


def status(db_path: Path = DB_PATH, artifacts_dir: Path = ARTIFACTS) -> list[Check]:
    """A health check of everything the app reads. Cheap: it opens the
    database read-only for a moment and looks at file names."""
    tables = database_tables(db_path)
    names = set(tables["table"])
    checks = []
    core = {"genomics", "metabolomics", "phenotype"}
    if not Path(db_path).exists():
        checks.append(Check("Database", False, "no database file yet",
                            "build it on the app's Home or Data page, or run the five commands in docs/07-app.md section 5"))
    elif not core <= names:
        checks.append(Check("Database", False, f"the clean tables are missing ({', '.join(sorted(core - names))})",
                            "python src/strainscope/harmonize.py"))
    else:
        n = int(tables.loc[tables["table"] == "phenotype", "rows"].iloc[0])
        checks.append(Check("Database", True, f"{len(names)} tables, {n} strains"))

    for prefix, phase, folder, script in (("int_", "Phase 3 results", "integration", "integrate.py"),
                                          ("ml_", "Phase 4 results", "model", "model.py"),
                                          ("kg_", "Phase 5 results", "graph", "graph.py")):
        files = sorted((Path(artifacts_dir) / folder).glob("*.csv"))
        in_db = sum(t.startswith(prefix) for t in names)
        if not files:
            checks.append(Check(phase, False, f"nothing in artifacts/{folder}/",
                                f"python src/strainscope/{script} all"))
        elif in_db == 0 and Path(db_path).exists():
            checks.append(Check(phase, False, f"{len(files)} files in artifacts/{folder}/, none in the database",
                                f"python src/strainscope/{script} publish"))
        else:
            checks.append(Check(phase, True, f"{len(files)} files in artifacts/{folder}/, {in_db} {prefix}* tables"))

    card = model_card(artifacts_dir)
    model_file = Path(artifacts_dir) / "model" / "strainscope_model.joblib"
    if card is None or not model_file.exists():
        checks.append(Check("Saved model", False, "no saved model", "python src/strainscope/model.py final"))
    else:
        import sklearn
        built = card.get("versions", {}).get("scikit-learn")
        same = built == sklearn.__version__
        detail = f"{card['model']}, built with scikit-learn {built}"
        if not same:
            detail += f" (you have {sklearn.__version__}; scores still work, rebuild to silence the warning)"
        checks.append(Check("Saved model", True, detail,
                            "" if same else "python src/strainscope/model.py final"))

    real = sorted(t for t in names if t.startswith("real_"))
    if real:
        checks.append(Check("Real tables (optional)", True, f"{len(real)} tables: {', '.join(real)}"))
    else:
        checks.append(Check("Real tables (optional)", None, "none fetched (the app works without them)",
                            "Data page, Real data tab, or python src/strainscope/fetch_real.py"))

    from strainscope import llm
    cfg = llm.settings()
    if cfg.on:
        checks.append(Check("AI features (optional)", True, f"on, {cfg.describe()}; {llm.daily_cap().describe()}"))
    else:
        checks.append(Check("AI features (optional)", None, "off: the assistants answer by search and rules "
                                                            "alone, and nothing is sent anywhere",
                            "STRAINSCOPE_ASK_BACKEND in .env (docs/LANGUAGE_MODEL.md)"))
    return checks


def release_info(changelog: Path = ROOT / "CHANGELOG.md") -> dict:
    """The newest released version and its date, read from CHANGELOG.md,
    and whether changes have been added since ([Unreleased] has entries).
    Reading it from the changelog means there's no second place to update."""
    out = {"version": "unknown", "date": "", "title": "", "unreleased": False}
    if not Path(changelog).exists():
        return out
    text = Path(changelog).read_text(encoding="utf-8")
    m = re.search(r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2}):?\s*(.*)$", text, flags=re.M)
    if m:
        out.update(version=m.group(1), date=m.group(2), title=m.group(3).strip())
    pending = re.search(r"^## \[Unreleased\]\s*(.*?)^## \[", text, flags=re.M | re.S)
    out["unreleased"] = bool(pending and re.search(r"^### ", pending.group(1), flags=re.M))
    return out


# =============================================================================
# 2. SQL: read-only questions with four guards
# =============================================================================

@dataclass
class QueryResult:
    table: pd.DataFrame | None
    error: str | None = None
    truncated: bool = False
    seconds: float = 0.0


def safe_connect(db_path: Path = DB_PATH):
    """A connection that can look but not touch: read-only, no file access,
    a memory ceiling, and settings locked so a query can't undo any of it."""
    import duckdb
    return duckdb.connect(str(db_path), read_only=True,
                          config={"enable_external_access": False,
                                  "memory_limit": SQL_MEMORY,
                                  "lock_configuration": True})


def query_database(sql: str, db_path: Path = DB_PATH, max_rows: int = SQL_MAX_ROWS,
                   timeout_s: float = SQL_TIMEOUT_S) -> QueryResult:
    """Run one query (or several, separated by ';': the last one's result is
    returned) and come back with a table or a readable error. Never raises
    for a bad query: a typo should cost a message, not the app."""
    import duckdb
    if not sql or not sql.strip():
        return QueryResult(None, "Type a query first, or pick a recipe.")
    if not Path(db_path).exists():
        return QueryResult(None, "There's no database yet. Build it on the Data page "
                                 "(or run: python src/strainscope/harmonize.py).")
    started = time.perf_counter()
    con = safe_connect(db_path)
    timer = threading.Timer(timeout_s, con.interrupt)
    try:
        timer.start()
        con.execute(sql)
        if con.description is None:                    # e.g. a SET: nothing to show
            return QueryResult(pd.DataFrame(), None, False, time.perf_counter() - started)
        columns = _unique([d[0] for d in con.description])
        rows = con.fetchmany(max_rows + 1)
        truncated = len(rows) > max_rows
        table = pd.DataFrame.from_records(rows[:max_rows], columns=columns)
        return QueryResult(table, None, truncated, time.perf_counter() - started)
    except duckdb.InterruptException:
        return QueryResult(None, f"Stopped after {timeout_s:g} seconds. Add a WHERE or a LIMIT, "
                                 "or check for a join without an ON condition.",
                           seconds=time.perf_counter() - started)
    except duckdb.Error as err:
        return QueryResult(None, explain_sql_error(str(err)), seconds=time.perf_counter() - started)
    finally:
        timer.cancel()
        con.close()


def _unique(names: list[str]) -> list[str]:
    """Column names made unique (a join can return two columns called strain_id)."""
    seen: dict[str, int] = {}
    out = []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}_{seen[n]}")
    return out


def explain_sql_error(message: str) -> str:
    """DuckDB's error, with one plain sentence in front for the usual cases."""
    low = message.lower()
    hint = ""
    if "read-only" in low:
        hint = ("The console is read-only: it can look at the data but never change it, "
                "so CREATE, INSERT, UPDATE and DELETE are refused.")
    elif "file system operations are disabled" in low or "external" in low and "disabled" in low:
        hint = "The console can't read or write files on the computer. It only sees the tables in the database."
    elif "does not exist" in low:
        missing = re.search(r"with name (\w+)", message)
        name = missing.group(1) if missing else ""
        if name.startswith("real_"):
            hint = "Real tables appear after fetching real data (Data page, Real data tab)."
        elif name[:3] in ("int", "ml_", "kg_"):
            hint = "Phase results reach the database through the publish steps (Data page, Build the database)."
        else:
            hint = "Check the spelling; the list of tables is under the editor."
    elif "parser error" in low or "syntax error" in low:
        hint = "The SQL couldn't be read. Look near the word DuckDB points at."
    elif "lock_configuration" in low or "configuration has been locked" in low:
        hint = "Settings are locked in the console, so the safety guards stay on."
    first = message.strip().splitlines()[0]
    return f"{hint}\n\nDuckDB says: {first}" if hint else f"DuckDB says: {first}"


# =============================================================================
# 3. THE QUERY COOKBOOK, as recipes the app can run
# =============================================================================

@dataclass
class Recipe:
    section: str
    question: str
    sql: str
    note: str = ""
    tables: list[str] = field(default_factory=list)


_TABLE_WORD = re.compile(r"\b(genomics|metabolomics|phenotype|(?:real|int|ml|kg)_[a-z0-9_]+)\b")


def cookbook_recipes(path: Path = COOKBOOK) -> list[Recipe]:
    """Every ```sql block of docs/QUERY_COOKBOOK.md with its section, the
    plain-English question above it (**"..."**) and the note below it. The
    cookbook stays the single source: edit a recipe there and the app's menu
    follows."""
    if not Path(path).exists():
        return []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    recipes, section, question, i = [], "", "", 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            section, question = line[3:].strip(), ""
        elif line.startswith("**"):
            para, j = [line], i + 1                     # the whole paragraph, which may wrap
            while j < len(lines) and lines[j].strip() and not lines[j].startswith("```"):
                para.append(lines[j].strip())
                j += 1
            text = " ".join(para)
            quoted = re.match(r'\*\*"([^"]+)"', text)                  # **"Which ...?"**
            labelled = re.match(r"\*\*([^*]+)\*\*\s*(.*?[.?:])(?:\s|$)", text)  # **Try it yourself:** list ...
            if quoted:
                question = quoted.group(1)
            elif labelled:
                question = f"{labelled.group(1).strip()} {labelled.group(2).strip()}".strip()
            question = question.replace("*", "").replace("`", "")
        elif line.strip() == "```sql":
            block = []
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                block.append(lines[i])
                i += 1
            note = []
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].startswith(("**", "```", "#", ">", "<")):
                note.append(lines[j].strip())
                j += 1
            sql = "\n".join(block).strip()
            text = " ".join(note)
            text = text[1:].strip() if text.startswith("→") else text
            recipes.append(Recipe(section, question or f"Recipe {len(recipes) + 1}", sql, text,
                                  sorted(set(_TABLE_WORD.findall(sql)))))
            question = ""
        i += 1
    return recipes


# =============================================================================
# 4. YOUR OWN STRAINS: template, checks, scores, explanations
# =============================================================================

def feature_columns(artifacts_dir: Path = ARTIFACTS) -> tuple[list[str], list[str]]:
    """The gene and metabolite columns, in the library's order (from the
    committed feature list of Phase 3, so no database is needed)."""
    ann = read_artifact("integration/feature_annotations.csv", artifacts_dir)
    if ann is None:
        raise FileNotFoundError("artifacts/integration/feature_annotations.csv is missing. "
                                "Run: python src/strainscope/integrate.py all")
    genes = ann.loc[ann["block"] == "genomics", "feature"].tolist()
    metabs = ann.loc[ann["block"] == "metabolomics", "feature"].tolist()
    return genes, metabs


def upload_template(artifacts_dir: Path = ARTIFACTS) -> pd.DataFrame:
    """An empty table with every column an upload can have."""
    genes, metabs = feature_columns(artifacts_dir)
    return pd.DataFrame(columns=["strain_id", "kingdom", "genus", *genes, *metabs])


def example_upload(db_path: Path = DB_PATH, artifacts_dir: Path = ARTIFACTS) -> pd.DataFrame:
    """Twelve strains copied from the library (three per kingdom: the best,
    a middling and the lowest ranked), renamed EXAMPLE_01 to EXAMPLE_12. The
    column `copied_from` says which library strain each one is, so you can
    open the original's page and compare."""
    import duckdb
    if not Path(db_path).exists():
        raise FileNotFoundError("There's no database yet, so there's nothing to copy from. Build it first.")
    pred = read_artifact("model/predictions.csv", artifacts_dir)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        phe = con.execute("SELECT strain_id, kingdom, genus FROM phenotype").fetchdf()
        gen = con.execute("SELECT * FROM genomics").fetchdf()
        met = con.execute("SELECT * FROM metabolomics").fetchdf()
    finally:
        con.close()
    lib = phe.merge(gen, on="strain_id").merge(met, on="strain_id")
    if pred is not None:
        lib = lib.merge(pred[["strain_id", "rank"]], on="strain_id").sort_values("rank")
    picks = []
    for k in KINGDOMS:
        ids = lib.loc[lib["kingdom"] == k, "strain_id"].tolist()
        if ids:
            picks += [ids[0], ids[len(ids) // 2], ids[-1]]
    out = lib.set_index("strain_id").loc[picks].reset_index()
    out.insert(0, "copied_from", out.pop("strain_id"))
    out.insert(0, "strain_id", [f"EXAMPLE_{i:02d}" for i in range(1, len(out) + 1)])
    genes, metabs = feature_columns(artifacts_dir)
    return out[["strain_id", "kingdom", "genus", *genes, *metabs, "copied_from"]]


@dataclass
class UploadCheck:
    table: pd.DataFrame | None         # the cleaned table (None when there are errors)
    problems: list[tuple[str, str]]    # (level, message); level: error, warning or note
    ok: bool


def _rows(index, limit: int = 5) -> str:
    """'rows 3, 7 and 9' (spreadsheet row numbers: the header is row 1)."""
    nums = [str(int(i) + 2) for i in list(index)[:limit]]
    extra = len(index) - len(nums)
    if extra:
        return f"rows {', '.join(nums)} and {extra} more"
    if len(nums) == 1:
        return f"row {nums[0]}"
    return f"rows {', '.join(nums[:-1])} and {nums[-1]}"


def validate_upload(raw: pd.DataFrame, artifacts_dir: Path = ARTIFACTS) -> UploadCheck:
    """Check an uploaded table and return a clean copy ready for scoring.
    Errors stop the scoring; warnings and notes explain what was assumed."""
    genes, metabs = feature_columns(artifacts_dir)
    known = {c.lower(): c for c in ["strain_id", "kingdom", "genus", *genes, *metabs]}
    problems: list[tuple[str, str]] = []
    df = raw.copy()
    # column names: forgive spaces and upper/lower case ("ITUA ", "Strain_ID")
    df.columns = [known.get(str(c).strip().lower(), str(c).strip()) for c in df.columns]
    if df.columns.duplicated().any():
        dup = sorted(set(df.columns[df.columns.duplicated()]))
        return UploadCheck(None, [("error", f"These columns appear twice: {', '.join(dup)}.")], False)
    if len(df) == 0:
        return UploadCheck(None, [("error", "The file has a header but no strains.")], False)
    if len(df) > MAX_UPLOAD_ROWS:
        return UploadCheck(None, [("error", f"The file has {len(df):,} strains; the app takes up to "
                                            f"{MAX_UPLOAD_ROWS:,} at a time. Split it into smaller files.")], False)
    for col in ("strain_id", "kingdom"):
        if col not in df.columns:
            problems.append(("error", f"The file needs a `{col}` column. Download the template to see the layout."))
    present_genes = [g for g in genes if g in df.columns]
    present_metabs = [m for m in metabs if m in df.columns]
    if not present_genes and not present_metabs:
        problems.append(("error", "None of the gene or metabolite columns were found. "
                                  "The column names must match the template (for example ituA, iturin)."))
    if any(level == "error" for level, _ in problems):
        return UploadCheck(None, problems, False)

    # strain ids: present and unique
    ids = df["strain_id"].astype("string").str.strip()
    blank = ids.isna() | (ids == "")
    if blank.any():
        problems.append(("error", f"`strain_id` is empty on {_rows(df.index[blank])}."))
    dup = ids[~blank & ids.duplicated(keep=False)]
    if len(dup):
        problems.append(("error", f"Each strain needs its own `strain_id`; these appear more than once: "
                                  f"{', '.join(sorted(set(dup))[:8])}."))
    df["strain_id"] = ids

    # kingdoms: harmonise spellings; an unknown one is allowed but flagged
    kingdom = df["kingdom"].astype("string").str.strip()
    mapped = kingdom.str.lower().map(KINGDOM_SPELLINGS)
    unknown = kingdom.notna() & (kingdom != "") & mapped.isna()
    if unknown.any():
        names = ", ".join(sorted(set(kingdom[unknown]))[:5])
        problems.append(("warning", f"{int(unknown.sum())} strain(s) have a kingdom the model has never seen "
                                    f"({names}). They're scored against all strains instead of their own "
                                    "kingdom, and their 'missing weapon' notes are skipped."))
    empty_k = kingdom.isna() | (kingdom == "")
    if empty_k.any():
        problems.append(("warning", f"`kingdom` is empty on {_rows(df.index[empty_k])}; "
                                    "those strains are scored against all strains."))
    df["kingdom"] = mapped.fillna(kingdom).fillna("unknown").replace("", "unknown")

    # gene calls: 0 or 1 (yes/no and true/false are accepted), blank = not known
    gaps = 0
    for g in present_genes:
        text = df[g].astype("string").str.strip().str.lower()
        gaps += int((text.isna() | (text == "")).sum())
        values = text.map(GENE_WORDS)
        bad = text.notna() & (text != "") & values.isna()
        if bad.any():
            problems.append(("error", f"Gene column `{g}` must hold 0 or 1 (or yes/no); found "
                                      f"{', '.join(sorted(set(df.loc[bad, g].astype(str)))[:4])} on {_rows(df.index[bad])}."))
        df[g] = values.astype(float)

    # metabolite levels: numbers, not negative, blank = not measured
    for m in present_metabs:
        values = pd.to_numeric(df[m], errors="coerce")
        text = df[m].astype("string").str.strip()
        gaps += int((text.isna() | (text == "")).sum())
        bad = text.notna() & (text != "") & values.isna()
        if bad.any():
            found = sorted(set(df.loc[bad, m].astype(str)))[:4]
            comma = any(re.fullmatch(r"\d+,\d+", v) for v in found)
            problems.append(("error", f"Metabolite column `{m}` must hold numbers; found "
                                      f"{', '.join(found)} on {_rows(df.index[bad])}."
                                      + (" Use a full stop as the decimal mark (2.5, not 2,5)." if comma else "")))
        negative = values < 0
        if negative.any():
            problems.append(("error", f"Metabolite column `{m}` has negative levels on {_rows(df.index[negative])}; "
                                      "a level can be 0 but not below."))
        df[m] = values

    missing_cols = [c for c in genes + metabs if c not in df.columns]
    if missing_cols:
        shown = ", ".join(missing_cols[:6]) + (" ..." if len(missing_cols) > 6 else "")
        problems.append(("warning", f"{len(missing_cols)} column(s) are missing and are treated as not measured: "
                                    f"{shown}. The model fills gaps the way it learned to (Phase 4)."))
        for c in missing_cols:
            df[c] = np.nan
    extra = [c for c in df.columns if c not in ["strain_id", "kingdom", "genus", *genes, *metabs]]
    if extra:
        problems.append(("note", f"Ignored column(s): {', '.join(map(str, extra[:6]))}"
                                 f"{' ...' if len(extra) > 6 else ''}. They're kept in your download."))
    if "genus" not in df.columns:
        df["genus"] = "unknown"
    df["genus"] = df["genus"].astype("string").fillna("unknown")
    if gaps > 0:
        problems.append(("note", f"{gaps:,} empty cell(s) are read as 'not measured', never as zero."))
    if any(level == "error" for level, _ in problems):
        return UploadCheck(None, problems, False)
    return UploadCheck(df[["strain_id", "kingdom", "genus", *genes, *metabs, *extra]].reset_index(drop=True),
                       problems, True)


def library_medians(db_path: Path = DB_PATH, artifacts_dir: Path = ARTIFACTS) -> dict[str, float]:
    """Each compound's median level across the library: the yardstick for
    'produces' (at least 4 times the median, the rule of Phase 5). Read from
    the database when it exists (exact), else from the committed graph."""
    if Path(db_path).exists():
        import duckdb
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            met = con.execute("SELECT * FROM metabolomics").fetchdf().set_index("strain_id")
        finally:
            con.close()
        return {c: float(met[c].median()) for c in met.columns}
    nodes = read_artifact("graph/nodes.csv", artifacts_dir)
    comp = nodes[nodes["node_type"] == "Compound"]
    return dict(zip(comp["label"], comp["median_level"].astype(float)))


def load_full_graph(artifacts_dir: Path = ARTIFACTS, db_path: Path = DB_PATH):
    """The Phase 5 graph with the facts its explanations need (which weapons
    are common in each kingdom, which gene calls were missing). None when
    the graph hasn't been built."""
    from strainscope import graph as kg
    if not (Path(artifacts_dir) / "graph" / "nodes.csv").exists():
        return None
    G = kg.load_graph(Path(artifacts_dir) / "graph")
    kg.attach_expectations(G, db_path)
    return G


def graph_with_upload(G, table: pd.DataFrame, medians: dict[str, float],
                      scores: pd.DataFrame | None = None, artifacts_dir: Path = ARTIFACTS):
    """A copy of the knowledge layer (every node except the library's
    strains) with the uploaded strains added, using the same rules as
    Phase 5: a gene call of 1 is 'carries', a level at least 4 times the
    library median is 'produces', and an empty gene call is 'not known'
    (never 'lacks'). The library graph itself is never changed."""
    from strainscope import graph as kg
    keep = [n for n, d in G.nodes(data=True) if d["node_type"] != "Strain"]
    U = G.subgraph(keep).copy()
    U.graph.update({k: v for k, v in G.graph.items() if k != "unknown_calls"})
    unknown = set()
    genes, metabs = feature_columns(artifacts_dir)
    scored = scores.set_index("strain_id") if scores is not None else None
    for row in table.to_dict("records"):
        sid = kg.node_id("Strain", row["strain_id"])
        attrs = {"node_type": "Strain", "label": row["strain_id"], "kingdom": row["kingdom"],
                 "genus": row.get("genus", "unknown"), "source": P_UPLOAD}
        if scored is not None and row["strain_id"] in scored.index:
            attrs.update(probability=float(scored.loc[row["strain_id"], "probability"]),
                         rank=int(scored.loc[row["strain_id"], "rank"]))
        U.add_node(sid, **attrs)
        for g in genes:
            gid = kg.node_id("Gene", g)
            if gid not in U:
                continue
            value = row.get(g)
            if value is None or (isinstance(value, float) and np.isnan(value)):
                unknown.add((sid, gid))
            elif value == 1:
                U.add_edge(sid, gid, key=f"carries|{P_UPLOAD}", relation="carries", provenance=P_UPLOAD)
        for c in metabs:
            cid, med, value = kg.node_id("Compound", c), medians.get(c), row.get(c)
            if cid not in U or med is None or not med > 0 or value is None or np.isnan(value):
                continue
            if value >= kg.DETECTION_FOLD * med:
                U.add_edge(sid, cid, key=f"produces|{P_UPLOAD}", relation="produces",
                           provenance=P_UPLOAD, weight=round(float(value / med), 4),
                           evidence=f"{value:.1f} = {value / med:.1f}x the library median ({med:.2f})")
    U.graph["unknown_calls"] = unknown
    return U


def explain_strains(G, strain_ids, source: str | None = None) -> pd.DataFrame:
    """The Phase 5 explanation of each strain, as rows like
    artifacts/graph/explanations.csv. For uploaded strains, the facts come
    from your file, and the source column says so."""
    from strainscope import graph as kg
    rows = []
    for s in strain_ids:
        rows += kg.explain_strain(G, s)
    table = pd.DataFrame(rows)
    if source and len(table):
        table["provenance"] = table["provenance"].str.replace(kg.P_SYNTH, source, regex=False)
    return table


def confidence_band(probability: float) -> str:
    """'likely', 'borderline' or 'unlikely'. "Effective" means suppressing
    disease by at least 65 % in the trial, and a strain that suppresses 64 %
    is, biologically, much like one at 66 %. The model's mistakes crowd near
    that line (Phase 4), so a predicted chance between 30 % and 70 % is shown
    as borderline instead of as a confident yes or no."""
    low, high = BORDERLINE
    if probability > high:
        return "likely"
    return "borderline" if probability >= low else "unlikely"


def score_upload(table: pd.DataFrame, artifacts_dir: Path = ARTIFACTS) -> tuple[pd.DataFrame, list[str]]:
    """Score checked strains with the saved Phase 4 model. Returns the
    scores (best first) and any notes, for example a scikit-learn version
    difference. Each strain also gets the rank it would have among the
    library's 600 (from their out-of-fold probabilities)."""
    from strainscope.model import load_model, score_strains
    notes = []
    model_dir = Path(artifacts_dir) / "model"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model, card = load_model(model_dir / "strainscope_model.joblib", model_dir / "model_card.json")
        scores = score_strains(table, model, card)
    for w in caught:                      # keep our one-line version note, not scikit-learn's own copies
        if str(w.message).startswith("model built with"):
            notes.append(str(w.message))
    out = table[["strain_id", "kingdom", "genus"]].copy()
    out["probability"] = scores["probability"].to_numpy()
    out["predicted_effective"] = scores["predicted_effective"].to_numpy()
    out["band"] = out["probability"].map(confidence_band)
    out = out.sort_values(["probability", "strain_id"], ascending=[False, True]).reset_index(drop=True)
    out.insert(0, "rank", np.arange(1, len(out) + 1))
    lib = read_artifact("model/predictions.csv", artifacts_dir)
    if lib is not None:
        library = np.sort(lib["probability"].to_numpy())[::-1]
        out["library_rank"] = [int((library > p).sum()) + 1 for p in out["probability"]]
    return out, notes


def score_and_explain(raw: pd.DataFrame, G=None, db_path: Path = DB_PATH,
                      artifacts_dir: Path = ARTIFACTS) -> dict:
    """The whole upload journey in one call: check, score, explain.
    Returns a dict with the check, the scores, the explanations, the graph
    holding the uploaded strains and any notes."""
    check = validate_upload(raw, artifacts_dir)
    if not check.ok:
        return {"check": check}
    scores, notes = score_upload(check.table, artifacts_dir)
    G = G if G is not None else load_full_graph(artifacts_dir, db_path)
    result = {"check": check, "scores": scores, "notes": notes, "graph": None, "explanations": None}
    if G is not None:
        from strainscope import graph as kg
        U = graph_with_upload(G, check.table, library_medians(db_path, artifacts_dir), scores, artifacts_dir)
        expl = explain_strains(U, [kg.node_id("Strain", s) for s in scores["strain_id"]], source=P_UPLOAD)
        paths = expl.groupby("strain_id")["mechanism_paths"].first() if len(expl) else pd.Series(dtype=int)
        scores["mechanism_paths"] = scores["strain_id"].map(paths).fillna(0).astype(int)
        first = (expl[expl["kind"] == "mechanism"].groupby("strain_id")["text"].first()
                 if len(expl) else pd.Series(dtype=str))
        scores["strongest_reason"] = scores["strain_id"].map(first).fillna("no mechanism path")
        result.update(graph=U, explanations=expl)
    return result


# =============================================================================
# 5. ONE STRAIN'S CORNER OF THE GRAPH, laid out for drawing
# =============================================================================

LAYERS = {"Strain": 0, "Gene": 1, "Compound": 2, "ModeOfAction": 3, "Outcome": 4}


def neighbourhood(G, strain: str, explanation: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The strain, the weapons it carries or makes that lead somewhere, how
    each one works and what that leads to, plus the weapons its kingdom
    usually has and it lacks. Returns (nodes, edges) with x/y positions in
    five columns: strain, genes, compounds, modes of action, outcomes.

    Three choices keep the picture readable (the graph itself is unchanged):
      * housekeeping and accessory genes that lead nowhere are left out,
        because every strain has them;
      * a compound hangs off the gene that makes it when the strain carries
        that gene, so a line straight from the strain to a compound means
        "makes it without carrying the gene" (a spike, or background noise
        just over the line), which is worth noticing;
      * a gene's own line to a mode of action is skipped when the compound it
        makes is shown and works the same way (the route through the
        compound already says it)."""
    from strainscope import graph as kg
    sid = strain if strain.startswith("strain:") else kg.node_id("Strain", strain)
    if sid not in G:
        raise KeyError(f"no strain called {strain!r}")
    target = kg.node_id("Outcome", kg.TARGET)
    node_rows: dict[str, dict] = {}
    edge_rows: list[dict] = []
    edge_keys: set = set()

    def add_node(n, status="has", detail=""):
        if n not in node_rows:
            d = G.nodes[n]
            node_rows[n] = {"node_id": n, "label": d["label"], "node_type": d["node_type"], "status": status,
                            "description": d.get("description", ""), "detail": detail}

    def add_edge(a, b, relation, provenance, style):
        if (a, b, relation) not in edge_keys:            # one line per pair, even if several weapons share it
            edge_keys.add((a, b, relation))
            edge_rows.append({"from_id": a, "to_id": b, "relation": relation,
                              "provenance": provenance, "style": style})

    def leads_somewhere(f):
        return bool(kg._out(G, f, "acts_by")) or any(o == target for o, _ in kg._out(G, f, "associated_with"))

    carried = {g: e for g, e in kg._out(G, sid, "carries") if leads_somewhere(g)}
    produced = {c: e for c, e in kg._out(G, sid, "produces") if leads_somewhere(c)}
    add_node(sid)
    for g in carried:
        add_node(g)
    for c, e in produced.items():
        add_node(c, detail=f"made at {e.get('weight', 0):.1f}x the usual level")

    makers = {c: [g for g, _, r in G.in_edges(c, data="relation") if r == "makes" and g in carried]
              for c in produced}
    for g, e in carried.items():
        add_edge(sid, g, "carries", e["provenance"], "fact")
    for c, e in produced.items():
        for g in makers[c]:
            me = next(x for y, x in kg._out(G, g, "makes") if y == c)
            add_edge(g, c, "makes", me["provenance"], "mechanism")
        if not makers[c]:
            add_edge(sid, c, "produces", e["provenance"], "without gene")

    for f in list(carried) + list(produced):
        modes = kg._out(G, f, "acts_by")
        shown_products = [c for c, _ in kg._out(G, f, "makes") if c in produced]
        for m, me in modes:
            add_node(m)
            via_product = any(m in {x for x, _ in kg._out(G, c, "acts_by")} for c in shown_products)
            if not via_product:
                add_edge(f, m, "acts_by", me["provenance"], "mechanism")
            for o, oe in kg._out(G, m, "contributes_to"):
                add_node(o)
                add_edge(m, o, "contributes_to", oe["provenance"], "mechanism")
        if not modes:                                    # statistics only: no known mechanism
            stats = [x for x in kg._out(G, f, "associated_with") if x[0] == target]
            add_node(target)
            add_edge(f, target, "associated_with", "; ".join(sorted({x[1]["provenance"] for x in stats})),
                     "statistics")
    if explanation is not None and len(explanation):     # weapons its kingdom usually has and it lacks
        for r in explanation[explanation["kind"] == "missing"].itertuples(index=False):
            gid = kg.node_id("Gene", r.feature)
            if gid in G:
                add_node(gid, status="lacks")
                add_edge(sid, gid, "lacks", r.provenance, "lacks")

    nodes = pd.DataFrame(list(node_rows.values()))
    edges = pd.DataFrame(edge_rows, columns=["from_id", "to_id", "relation", "provenance", "style"])
    nodes["x"] = nodes["node_type"].map(LAYERS).astype(float)

    # y: keep each weapon level with the way it works, so lines run across
    # instead of criss-crossing. Modes are ordered by outcome, then name;
    # genes follow their mode; a compound sits level with the gene that makes
    # it; statistics-only features and missing weapons go to the bottom.
    # Every column is spread over the same height.
    modes = [n for n in node_rows if node_rows[n]["node_type"] == "ModeOfAction"]
    leads = {m: [o for o, _ in kg._out(G, m, "contributes_to")] for m in modes}
    mode_pos = {m: i for i, m in enumerate(sorted(modes, key=lambda m: (target not in leads[m],
                                                                        node_rows[m]["label"])))}

    def mode_key(n):
        mine = [mode_pos[m] for m, _ in kg._out(G, n, "acts_by") if m in mode_pos]
        return (0, min(mine)) if mine else (1, 0)

    gene_order = sorted((n for n in node_rows if node_rows[n]["node_type"] == "Gene"),
                        key=lambda n: (node_rows[n]["status"] == "lacks", *mode_key(n), node_rows[n]["label"]))
    gene_rank = {g: i for i, g in enumerate(gene_order)}

    def place(n):
        row = node_rows[n]
        if row["node_type"] == "Gene":
            return (gene_rank[n],)
        if row["node_type"] == "ModeOfAction":
            return (mode_pos[n],)
        if row["node_type"] == "Outcome":
            return (0 if n == target else 1, row["label"])
        if row["node_type"] == "Compound":
            made_by = [gene_rank[g] for g in makers.get(n, []) if g in gene_rank]
            # made without its gene: to the bottom, so its line doesn't run through a gene
            return (not made_by, *mode_key(n), min(made_by) if made_by else 0, row["label"])
        return (0,)

    height = max(nodes["x"].value_counts())
    position = {}
    for layer in range(len(LAYERS)):
        ranked = sorted(nodes.loc[nodes["x"] == layer, "node_id"], key=place)
        k = len(ranked)
        for i, n in enumerate(ranked):                   # first item at the top
            position[n] = 0.0 if k == 1 else (height - 1) / 2 * (1 - 2 * i / (k - 1))
    nodes["y"] = nodes["node_id"].map(position).astype(float)
    return nodes, edges


# =============================================================================
# 6. THE ASSISTANTS: questions about the project (Phase 6b), the data and
#    the graph (Phase 7), and a strain's rank in plain words (Phase 7)
# =============================================================================

def ask_docs(question: str, write: bool | None = False) -> dict:
    """A question about StrainScope, answered from its own documents, as plain
    data: the verdict, a one-line message, and the matching passages with
    their links. The engine is src/strainscope/ask.py (the app's Ask StrainScope
    page and the terminal use it directly); this is the door the MCP server
    of Phase 7b uses (src/strainscope/mcp_server.py). `write=None` adds a written answer when one is set
    up (STRAINSCOPE_ASK_BACKEND); the default, False, never contacts a model."""
    from strainscope import ask as docs
    a = docs.ask(question, write=write)
    return {
        "question": a.question, "verdict": a.verdict, "message": a.message,
        "sections": [{"heading": h.section.heading, "file": h.section.file, "link": h.section.link,
                      "url": h.section.url, "match": round(h.score, 3), "passage": h.passage} for h in a.hits],
        "related": [{"heading": s.heading, "file": s.file, "link": s.link} for s in a.related],
        "written": a.written, "written_by": a.written_by, "note": a.note,
    }


def ask_data(question: str, write: bool | None = False, db_path: Path = DB_PATH, max_rows: int = 200) -> dict:
    """A question about the data, answered with a query (a tested recipe, or
    one a model wrote when that's switched on) run through the four guards,
    as plain data: the verdict, the message, the SQL, where it came from and
    up to `max_rows` rows. `write=None` lets a model write a query when no
    recipe fits and one is set up; the default, False, never contacts a model."""
    from strainscope import ask_data as data
    a = data.ask(question, db_path, write=write)
    table = a.table
    return {
        "question": a.question, "verdict": a.verdict, "message": a.message, "sql": a.sql,
        "source": ("recipe" if a.recipe else a.written_by),
        "recipe": a.recipe.recipe.question if a.recipe else None,
        "error": a.result.error if a.result is not None else None,
        "columns": list(table.columns) if table is not None else [],
        "rows": table.head(max_rows).to_dict("records") if table is not None else [],
        "row_count": int(len(table)) if table is not None else 0,
        "options": [h.recipe.question for h in a.options], "note": a.note,
    }


def ask_graph(question: str, write: bool | None = False, G=None) -> dict:
    """A question about how things connect, answered by walking the knowledge
    graph (GraphRAG), as plain data: the verdict, the message, the numbered
    facts with their sources and the route. `write=None` adds a written
    answer when a model is set up; the default, False, never contacts one."""
    from strainscope import ask_graph as graph_qa
    a = graph_qa.ask(question, G, write=write)
    return {
        "question": a.question, "verdict": a.verdict, "message": a.message,
        "facts": [{"number": n, "text": f.text, "source": f.source} for n, f in enumerate(a.facts, start=1)],
        "route": [{k: h.get(k) for k in ("from", "relation", "to", "provenance")} for h in a.hops],
        "strain": a.strain, "story": a.story, "written": a.written, "written_by": a.written_by, "note": a.note,
    }


# The questions check_model() asks: two for each assistant that writes an
# answer from what it found. They are starter questions, so the search always
# answers them and the model is always asked.
MODEL_CHECK = (("Ask the graph", "How does iturin suppress disease?"),
               ("Ask the graph", "What does pyrrolnitrin do?"),
               ("Ask StrainScope", "What is a balanced error rate?"),
               ("Ask StrainScope", "Why is the data simulated?"))


def check_model(cfg=None, G=None, report=None) -> list[dict]:
    """Does the switched-on language model follow the rules? Asks the four
    questions of MODEL_CHECK through Ask the graph and Ask StrainScope, with
    exactly the requests the app sends, and says for each whether the model
    answered ("answered") and whether that answer would be shown ("shown": it
    cites only what it was given and, for Ask the graph, adds no number), or
    why not ("note"). That's four requests, which count towards a hosted
    provider's limits. STRAINSCOPE_AI_DAILY_LIMIT counts from 0 in every
    program that starts, so this check never uses up the app's allowance,
    but a limit below 4 stops it partway. No model switched on: nothing is
    sent and the result is []. `report`, if given, is called with each
    result as soon as it's ready."""
    from strainscope import ask as docs, ask_graph as graph_qa, llm
    cfg = cfg or llm.settings()
    if not cfg.on:
        return []
    G = G if G is not None else load_full_graph()
    rows = []
    for assistant, question in MODEL_CHECK:
        start = time.time()
        if assistant == "Ask the graph":
            a = graph_qa.ask(question, G, write=True, cfg=cfg)
        else:
            a = docs.ask(question, write=True, settings=cfg)
        row = {"assistant": assistant, "question": question,
               "answered": a.written_by is not None,      # the model replied (shown or not)
               "shown": a.written is not None, "written": a.written,
               "note": a.note or a.message, "seconds": time.time() - start}
        rows.append(row)
        if report:
            report(row)
    return rows


def explain_in_words(strain_id: str, artifacts_dir: Path = ARTIFACTS) -> dict:
    """One library strain's rank and reasons in plain words
    (src/strainscope/narrate.py), from the committed results only."""
    from strainscope import narrate
    pred = read_artifact("model/predictions.csv", artifacts_dir)
    reasons = read_artifact("graph/explanations.csv", artifacts_dir)
    if pred is None or reasons is None:
        raise FileNotFoundError("The ranking or the explanations are missing (Phases 4 and 5).")
    match = pred[pred["strain_id"] == strain_id]
    if match.empty:
        raise KeyError(f"no strain called {strain_id!r}")
    nodes = read_artifact("graph/nodes.csv", artifacts_dir)
    row = match.iloc[0].to_dict()
    if nodes is not None:
        genus = nodes.loc[nodes["label"] == strain_id, "genus"]
        row["genus"] = genus.iloc[0] if len(genus) else None
    story = narrate.strain(row, reasons[reasons["strain_id"] == strain_id], len(pred), model_card(artifacts_dir))
    return {"strain_id": strain_id, "text": story.text, "paragraphs": story.paragraphs}


# =============================================================================
# 7. THE PIPELINE: the scripts of Phases 1 to 5, run in order
# =============================================================================

# Each pipeline is a list of (script, arguments). They run with the same
# Python that runs the app, one after another; a step that fails stops the rest.
# The app's buttons run them, and so does the one-command pipeline of Phase 8
# (python src/strainscope/pipeline.py), so both always run the same steps.
PIPELINES = {
    "everything": {
        "title": "Rebuild everything from scratch",
        "takes": "5 to 10 minutes; about 4 without R",
        "what": ("regenerates the synthetic library, cleans it into a fresh database, and recomputes every "
                 "result: the integration (DIABLO too, when R is installed), the models and the knowledge graph"),
        "steps": [("generate_data.py",), ("harmonize.py",), ("integrate.py", "all"),
                  ("model.py", "all"), ("graph.py", "all")],
    },
    "database": {
        "title": "Build the database from the scripts",
        "takes": "about 15 seconds",
        "what": ("regenerates the synthetic library (same seed, same strains), cleans it into a fresh "
                 "database, then loads the committed results of Phases 3, 4 and 5 into it"),
        "steps": [("generate_data.py",), ("harmonize.py",), ("integrate.py", "publish"),
                  ("model.py", "publish"), ("graph.py", "publish")],
    },
    "probe": {
        "title": "Ask the public databases what a fetch would bring",
        "takes": "under a minute, needs the internet",
        "what": "asks each of the five sources how much it holds, without downloading anything",
        "steps": [("fetch_real.py", "--probe")],
    },
    "real": {
        "title": "Fetch real data and rebuild",
        "takes": "a few minutes, needs the internet",
        "what": ("downloads from BacDive, PubChem, KEGG, NCBI Datasets and Metabolomics Workbench, rebuilds "
                 "the database with the real tables, and rebuilds the knowledge graph so it uses them"),
        "steps": [("fetch_real.py",), ("harmonize.py",), ("integrate.py", "publish"),
                  ("model.py", "publish"), ("graph.py", "all")],
    },
}
_PIPELINE_LOCK = threading.Lock()


def step_command(step: tuple[str, ...]) -> list[str]:
    """The exact command for one step, with the Python running this code."""
    return [sys.executable, "-u", str(ROOT / "src" / "strainscope" / step[0]), *step[1:]]


def step_label(step: tuple[str, ...]) -> str:
    """A step as you'd type it: python src/strainscope/model.py all."""
    return "python src/strainscope/" + " ".join(step)


def pipeline_events(name: str, root: Path = ROOT, start: int = 1):
    """Run one of PIPELINES from step `start` on, and yield what happens, as
    dictionaries with an "event" key:

      start   a step begins          (step, label)
      line    a line it printed      (step, label, text)
      end     it finished well       (step, label, seconds)
      done / failed                  the last event, with a sentence (text)
                                     and, for failed, the step that stopped

    Each step runs in its own Python process, with the Python running this
    code. A step that fails stops the rest. Only one pipeline runs at a time,
    in this program, so two buttons can't write the database together."""
    steps = PIPELINES[name]["steps"]
    if not 1 <= start <= len(steps):
        raise ValueError(f"The '{name}' pipeline has steps 1 to {len(steps)}; there's no step {start}.")
    if not _PIPELINE_LOCK.acquire(blocking=False):
        yield {"event": "failed", "step": None,
               "text": "Another build is running. Wait for it to finish, then try again."}
        return
    proc = None
    try:
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}  # Windows prints UTF-8 too
        for number, step in enumerate(steps, start=1):
            if number < start:
                continue
            label = step_label(step)
            yield {"event": "start", "step": number, "label": label}
            started = time.time()
            proc = subprocess.Popen(step_command(step), cwd=root, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            for line in proc.stdout:
                yield {"event": "line", "step": number, "label": label, "text": line.rstrip("\n")}
            code = proc.wait()
            proc = None
            if code != 0:
                yield {"event": "failed", "step": number,
                       "text": f"Step {number} ({label}) stopped with exit code {code}. Its output is above."}
                return
            yield {"event": "end", "step": number, "label": label, "seconds": time.time() - started}
        what = f"All {len(steps)} steps" if start == 1 else f"Steps {start} to {len(steps)}"
        yield {"event": "done", "step": None, "text": f"{what} finished."}
    finally:
        if proc is not None and proc.poll() is None:     # stopped halfway (Ctrl+C): stop the step too
            proc.terminate()
            proc.wait()
        _PIPELINE_LOCK.release()


def run_pipeline(name: str, root: Path = ROOT, start: int = 1):
    """The same run, as the app shows it: (step_number, step_label,
    output_line) as the scripts print. The last item yielded is
    (None, 'done' or 'failed', summary)."""
    total = len(PIPELINES[name]["steps"])
    for e in pipeline_events(name, root, start):
        if e["event"] == "start":
            yield e["step"], e["label"], f"$ {e['label']}"
        elif e["event"] == "line":
            yield e["step"], e["label"], e["text"]
        elif e["event"] == "end":
            yield e["step"], e["label"], f"  (step {e['step']} of {total} done in {e['seconds']:.0f} s)"
        else:
            yield None, e["event"], e["text"]


# =============================================================================
# 8. THE COMMAND LINE
# =============================================================================

def _print_status() -> None:
    mark = {True: "✓", False: "✗", None: "·"}
    print("  ── StrainScope: what the app can read ──────────────────────────")
    for c in status():
        print(f"  {mark[c.ok]} {c.name:<24} {c.detail}")
        if c.fix:
            word = {False: "fix", None: "to add", True: "tip"}[c.ok]
            print(f"      {word}: {c.fix}")


def _score_file(path: Path, out: Path | None) -> None:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    result = score_and_explain(raw)
    check = result["check"]
    for level, message in check.problems:
        print(f"  {'!' if level == 'error' else '-'} {level}: {message}")
    if not check.ok:
        sys.exit("  Nothing was scored. Fix the errors above and try again.")
    for note in result.get("notes", []):
        print(f"  - note: {note}")
    scores = result["scores"]
    print(f"  ── {len(scores)} strain(s), best first ──────────────────────────────")
    for r in scores.head(20).itertuples(index=False):
        flag = "flag" if r.predicted_effective else "    "
        reason = getattr(r, "strongest_reason", "")
        print(f"  {r.rank:>3}. {r.strain_id:<12} {r.kingdom:<9} {r.probability:>6.1%}  {r.band:<10} {flag}  {reason}")
    if len(scores) > 20:
        print(f"  ... and {len(scores) - 20} more in the file")
    out = out or path.with_name(f"{path.stem}_scored.csv")
    extra = [c for c in check.table.columns if c not in scores.columns]
    scores.merge(check.table[["strain_id", *extra]], on="strain_id").to_csv(out, index=False)
    if result.get("explanations") is not None:
        expl_path = out.with_name(f"{out.stem}_reasons.csv")
        result["explanations"].to_csv(expl_path, index=False)
        print(f"  scores → {out}\n  reasons → {expl_path}")
    else:
        print(f"  scores → {out}")
    print("  Reminder: the model was trained on SIMULATED data. Treat these scores as a demonstration.")


def _print_model_check() -> None:
    import textwrap
    from strainscope import llm
    cfg = llm.settings()
    print("  ── StrainScope: does the language model cite its sources? ──────")
    if not cfg.on:
        print("  No language model is switched on (STRAINSCOPE_ASK_BACKEND is none or not set),")
        print("  so there's nothing to check. docs/LANGUAGE_MODEL.md shows how to switch one on.")
        return

    def show(r: dict) -> None:
        mark = "✓" if r["shown"] else ("✗" if r["answered"] else "·")
        print(f"\n  {mark} {r['assistant']}: {r['question']}   ({r['seconds']:.0f} s)")
        # a note's last sentence points at the passages or facts "below", which this list doesn't show
        text = r["written"] if r["shown"] else " ".join(t for t in re.split(r"(?<=[.?)])\s+", r["note"] or "")
                                                         if " below " not in t)
        print(textwrap.fill(text, width=96, initial_indent="      ", subsequent_indent="      "))

    print(f"  Model: {cfg.describe()}")
    print("  Four questions, asked the way the app asks them. This can take a minute or two.")
    rows = check_model(cfg, report=show)
    shown, answered = sum(r["shown"] for r in rows), sum(r["answered"] for r in rows)
    print(f"\n  {shown} of {len(rows)} written answers would be shown.")
    if answered < len(rows):
        print(f"  {len(rows) - answered} question(s) never reached the model; the line under each one says why.")
    if answered > shown:
        print("  A hidden answer does no harm: in the app, the passages or facts still answer the question.")
        if (answered - shown) * 2 > answered:
            print("  Most answers broke a rule. A larger model usually follows the rules better")
            print("  (docs/LANGUAGE_MODEL.md, section 8).")


def main() -> None:
    parser = argparse.ArgumentParser(description="StrainScope Phase 6: the service layer behind the app.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="what the app can read, and how to fix what's missing")
    t = sub.add_parser("template", help="write an empty upload template (CSV)")
    t.add_argument("path", type=Path)
    t.add_argument("--example", action="store_true", help="fill it with twelve example strains")
    s = sub.add_parser("score", help="check, score and explain your own strains (CSV)")
    s.add_argument("path", type=Path)
    s.add_argument("--out", type=Path, default=None, help="where to write the scores (default: NAME_scored.csv)")
    sub.add_parser("check-model", help="ask the switched-on language model four questions: does it cite its sources?")
    args = parser.parse_args()
    if args.command == "status":
        _print_status()
    elif args.command == "check-model":
        _print_model_check()
    elif args.command == "template":
        table = example_upload() if args.example else upload_template()
        table.to_csv(args.path, index=False)
        what = f"{len(table)} example strains" if args.example else "the header row only"
        print(f"  template → {args.path}   ({len(table.columns)} columns, {what})")
    else:
        _score_file(args.path, args.out)


if __name__ == "__main__":
    main()
