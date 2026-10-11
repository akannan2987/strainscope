# 03 · Phase 2: Cleaning the mess and building the database (DuckDB + SQL)

[← Phase 1b: real data](02b-real-data-ingestion.md) · [Handbook](HANDBOOK.md) · [All docs in order](../README.md#the-tutorial-in-order) · [Glossary](GLOSSARY.md) · [Query Cookbook](QUERY_COOKBOOK.md)

**Prerequisites:** Phase 1 complete (the raw synthetic tables exist; rerun `python src/strainscope/generate_data.py` if `data/raw/` is empty). Phase 1b is a bonus and isn't required. If you fetched real data, it joins the database automatically; if you didn't, everything here still works.
**Learning goal:** after this phase you will understand why raw data is *evidence* that must never be edited; how professionals clean data (rules written in English first, every change counted in a ledger, each decision justified); what a database is and why analysts keep one next to their dataframes; and enough SQL to question 600 strains in one line. You'll also watch a textbook cleaning rule *fail* on our data, and see what that failure has to teach.
**Why this phase exists in a real workflow:** models trained on dirty data learn the dirt. Duplicates inflate counts, batch drift masquerades as biology, one spiked reading drags averages, and two spellings of one genus split every statistic in half. Cleaning is the step that makes later results trustworthy, and the ledger is how you *prove* nothing was changed silently.

**Session plan:**
- **Session A (about 1 to 1.5 h):** concepts (§1-2), the cleaning rules in English (§3), reading the engine (§4), then running it and studying the ledger (§5).
- **Session B (about 1 to 1.5 h):** the figures (§6), meeting the database and running your first SQL (§7, with the [Query Cookbook](QUERY_COOKBOOK.md)), then tests, checkpoint and commit (§8 to 13).

> **How this guide works:** every action step tells you what **You should see** and **What it means**, plus **If instead** for the steps that can wobble. Nothing here should catch you off guard.

---

## 1. The ideas you need first

**Raw data is evidence; cleaning produces new files.** Think of a crime-scene photo: you can *annotate a copy*, but you never draw on the original. Our raw CSVs in `data/raw/` are never edited. Cleaning reads them and writes *new* files into `data/processed/`, which is why it can be re-run as often as you like (and why a mistake costs nothing).

**The desk and the filing cabinet.** When Python loads a table with pandas, the table sits in memory, like papers spread on your desk: fast to shuffle, gone when you stand up, and visible only to you. A **database** is the filing cabinet. It's organised, permanent and shared, and it comes with a precise language for asking questions (**SQL**). Analysts use both, the desk for wrangling and the cabinet for storing and querying. Our cabinet is **DuckDB**, a full SQL database that lives in *one ordinary file* (`strainscope.duckdb`), needs no server or fiddly installation, and is built for analysis. (You could zip the whole filing cabinet up and email it.)

**SQL, in one breath.** It's a ~50-year-old language for asking tables questions, and still the most widely used language in data work. It reads almost like English: `SELECT kingdom, COUNT(*) FROM phenotype GROUP BY kingdom` means *"for each kingdom, count the strains."* You'll run real queries in §7, and the [Query Cookbook](QUERY_COOKBOOK.md) collects them from now on.

**NULL, the marked gap.** A database gives a missing value its own marker, `NULL`: a first-class "no value here" that is different from zero and from an empty string. Keeping gaps as NULLs (instead of quietly filling them) means the database never pretends to know something that was never measured.

**The ledger.** Every cleaning step reports rows in, rows out and cells changed. You can treat it as the project's bookkeeping: if a number in a later chart looks odd, the ledger says exactly what cleaning did and didn't touch. You'll see it *catch a real bug* in §5's "notes from the build."

**Idempotent** (a word worth learning): run the cleaning twice and you get an identical result, with nothing piling up or drifting between runs. Everything in this phase is idempotent, so it's safe to re-run whenever you like.

## 2. The data round trip

```mermaid
flowchart TD
    RAW["Raw synthetic tables<br/>data/raw/*.csv<br/><i>evidence: read, never edited</i>"]
    REALT["Real tidy tables (Phase 1b)<br/>data/processed/real/*.csv<br/><i>auto-loaded if present</i>"]
    DESK["pandas: <b>the desk</b><br/>tables loaded into memory,<br/>fast to reshape, gone on exit"]
    CLEANF["Six cleaning functions, in order<br/>duplicates → text → clip impossible →<br/>cap outliers → batch correction → missingness"]
    LEDGER["The cleaning ledger<br/>rows in · rows out · cells changed<br/><i>printed every run, nothing silent</i>"]
    CLEAN["Clean tables<br/>data/processed/*_clean.csv"]
    DB[("strainscope.duckdb: <b>the filing cabinet</b><br/>synthetic + real tables in one file,<br/>permanent and queryable")]
    SQL["You, asking questions in SQL<br/>+ the Query Cookbook<br/>(and every later phase reads from here)"]

    RAW -->|"read only"| DESK
    DESK --> CLEANF
    CLEANF -->|"reports every change"| LEDGER
    CLEANF --> CLEAN
    CLEAN -->|"loaded as tables"| DB
    REALT -->|"loaded as real_* tables"| DB
    DB --> SQL

    classDef laptop fill:#E8F0FE,stroke:#5B8DEF,color:#0B2545;
    classDef store fill:#FFF3CD,stroke:#C9A227,color:#4A3B00;
    classDef artifact fill:#EAECEF,stroke:#8A94A6,color:#1F2933;
    classDef cloud fill:#E6F4EA,stroke:#4CAF7D,color:#0B3D2E;
    class DESK,CLEANF laptop
    class RAW,REALT,DB store
    class LEDGER,CLEAN artifact
    class SQL cloud
```

Read it top to bottom. Raw files are read and never modified (evidence stays evidence). The desk holds them while the six functions clean in order, reporting every change to the ledger. The clean tables, plus any real Phase 1b tables, land in the cabinet, and that one file is where you (and every later phase) ask questions.

## 3. The cleaning rules in English, before any code

There are six rules, and their order matters. Each one exists because Phase 1 planted a specific, known mess (a nice property of synthetic data: we *know* the dirt, so we can check that our cleaning catches it).

1. **Remove duplicate strains first** (8 strains recorded twice). Duplicates distort every count and statistic computed after them, so de-duplication always goes first. Keep the first occurrence (with exact duplicates the choice is cosmetic, but stating it makes the rule reproducible).
2. **Harmonise the text**: strip stray spaces, unify case (genera Title-case, sites lower-case), then fix known typos from a *written-down list* (`Psuedomonas → Pseudomonas`) rather than by guessing. The aim is one agreed spelling for each real-world thing.
3. **Clip impossible scores**: a suppression *percentage* can't be below 0 or above 100, so the 3 values outside that range get clipped to the boundary. We clip instead of deleting because the strain is real; only the reading overshot.
4. **Cap the outlier spikes.** This rule took the most thought (see the notes from the build, because the textbook rule fails here). The final version: per metabolite, cap anything above **3 × its 95th percentile**, on the reasoning that three times the upper edge of plausible production can only be an artifact.
5. **Correct the batch effect**: per batch and per metabolite, divide by (batch median ÷ overall median), so a batch running 15 % hot is cooled by exactly 15 %. Medians are used instead of means so that leftover extremes can't drag the correction. **Order matters:** this runs *after* outlier capping, or one spike could poison its whole batch's factor.
6. **Count the missing values, and leave them missing.** 338 gene cells + 714 metabolite cells become proper `NULL`s. Filling gaps (*imputation*) bakes in assumptions that depend on the downstream method, so it's a modelling decision, made openly later. Cleaning's job here is to make missingness *visible and counted*.

### What this phase leaves out on purpose

- **No imputation** (rule 6: it belongs to modelling).
- **No removal of the undetectable spikes.** A spike of a *trace* value lands inside the legitimate producer range, where it can't be told apart from real production without gene context. We cap what's provably absurd and *tell the modelling phases* that the rest exists.
- **No editing of raw files, ever.**
- **No "fixing" of the class imbalance.** 24 % effective is what the data really looks like, and handling imbalance is a modelling technique rather than a cleaning one.

## 4. Get the Phase 2 files into your repo

| Path (from the project folder) | Its job |
|---|---|
| `src/strainscope/harmonize.py` | the cleaning engine: six documented functions + the ledger + the DuckDB loader |
| `tests/test_harmonize.py` | seven offline tests, one per cleaning behaviour, ledger included |
| `figures/make_phase2_figures.py` | before/after evidence figures + the interactive comparison |
| `docs/QUERY_COOKBOOK.md` | tested, ready-to-run SQL recipes (grows every phase) |
| `src/strainscope/sql.py` | the project's SQL console: run any query, read-only, nothing to install |

**Files-landed check:**

```bash
ls src/strainscope/harmonize.py src/strainscope/sql.py tests/test_harmonize.py \
   figures/make_phase2_figures.py docs/QUERY_COOKBOOK.md
```

**Read the engine before running it.** Open `src/strainscope/harmonize.py` and go top to bottom. It's written to be read: the golden rules at the top, then one function per cleaning rule, with each docstring explaining *why* as well as *what*. Ten minutes here makes the rest of the phase much easier to follow.

## 5. Run the cleaning

```bash
python src/strainscope/harmonize.py
```

**You should see** (exact numbers, thanks to the fixed seed):

```
  wrote data/processed/genomics_clean.csv  (600 rows, 32 columns)
  wrote data/processed/metabolomics_clean.csv  (600 rows, 21 columns)
  wrote data/processed/phenotype_clean.csv  (600 rows, 9 columns)

  ── Cleaning ledger: every change, counted ──────────────────
  drop_duplicates        genomics      608→600 rows (−8)           0 cells   8 duplicate strain rows removed
  drop_duplicates        metabolomics  608→600 rows (−8)           0 cells   8 duplicate strain rows removed
  drop_duplicates        phenotype     608→600 rows (−8)           0 cells   8 duplicate strain rows removed
  harmonize_text         phenotype     600→600 rows              657 cells   stripped spaces, unified case, fixed known typos
  clip_impossible        phenotype     600→600 rows                3 cells   3 scores clipped into [0, 100]
  cap_outliers           metabolomics  600→600 rows               41 cells   values above 3.0×p95 capped (41 cells); moderate spikes are indistinguishable from real producers (documented)
  correct_batch          metabolomics  600→600 rows            12000 cells   per-batch median-scaling toward the overall median
  account_missing        genomics      600→600 rows              338 cells   338 missing cells kept as NULL …
  account_missing        metabolomics  600→600 rows              714 cells   714 missing cells kept as NULL …
  account_missing        phenotype     600→600 rows                0 cells   0 missing cells kept as NULL …
  ────────────────────────────────────────────────────────────

  Database: data/processed/strainscope.duckdb
  Tables loaded: genomics, metabolomics, phenotype, real_compound_pathways, real_compounds, real_kegg_compounds, real_strains
  (4 real table(s) auto-loaded from data/processed/real/; future sources join automatically)
```

**What it means, line by line:** the 8 duplicates Phase 1 planted are gone from every table (608→600, so the counts *reconcile with the known mess*, which is exactly what a ledger is for). 657 text cells were harmonised. The 3 impossible scores are clipped. Only 41 outlier cells were capped; the notes below explain why that small number is the *correct* one. The batch step touches all 12,000 metabolite cells (every value gets its batch's scaling). And 1,052 missing cells are counted, kept and explained.

**If instead** your `Tables loaded` line shows only the three synthetic tables and `0 real table(s)`: you haven't run Phase 1b's fetch (or its tables are elsewhere). That's fine. Everything in this phase works without them, and the real tables join whenever you do fetch.

### Notes from the build (kept on purpose): the ledger catches a bug

- **The textbook outlier rule would have flattened the biology, and the ledger caught it.** The first version used the classic fence (Q3 + 5×IQR, the rule most courses teach). The ledger reported 779 capped cells against a *known* injected mess of ~120 spikes. Those numbers didn't reconcile, and the mismatch was the alarm. Digging in showed why: our abundances are **bimodal** (a trace hump for strains without the producing gene, a producer hump for strains with it), and for weapons carried by only one kingdom the quartiles sit inside the trace hump. That puts the fence *below* the real producers and caps real biology wholesale. The fix judges extremes against the *upper edge* instead (3 × p95), which caps 41 provably absurd cells and spares both humps. The takeaways, most important first: (1) a ledger pays off when you reconcile its counts against what you *know*, because that's how silent damage gets caught; (2) textbook rules carry silent assumptions (one-humped data) that real data violates; (3) when you *know* the planted mess, you can grade your own cleaning, which is one of the quieter advantages of synthetic data.
- **Some corruption can't be detected at cleaning time.** The injected spikes multiplied *whatever value was there*, so a spiked trace value lands at ~16, squarely inside the legitimate producer range. No cleaning rule can catch those without using gene information (which would tangle cleaning up with modelling). So they stay, *documented*, and the modelling phases are told. Good cleaning comes down to knowing exactly what you can and cannot justify touching; removing everything that looks suspicious would go too far.
- **Integer columns bite.** A test table with whole numbers made the batch correction crash: scaling produces decimals, and modern pandas refuses to write decimals into an integer column. The function now coerces to float first, since a user-uploaded CSV of whole numbers would be read as integers too. It's a good example of why tiny hand-made test tables with *unrealistically simple* data are worth having: they turn up real bugs.

## 6. See the evidence (figures + interactive)

```bash
python figures/make_phase2_figures.py
```

### The ledger, drawn

![The cleaning ledger as a picture](../figures/cleaning_ledger.png)

Everything cleaning did, on one log-scale chart, from 3 clipped scores up to 1,052 documented NULLs. If anyone asks "what did cleaning change?", this chart answers it.

### The batch drift, removed

![Batch effect before and after](../figures/batch_before_after.png)

Left: the six batches disagree, and the red median line wanders (that's the lab drift Phase 1 injected). Right: after median-scaling the medians sit level, while the *spread within each batch* (the actual biology) survives untouched. There's an interactive version too, [`docs/interactive/batch_before_after.html`](interactive/batch_before_after.html): flip between BEFORE and AFTER with the buttons and watch the medians snap into line.

### Two humps are biology; the far tail is error

![Outliers capped](../figures/outliers_capped.png)

This is the picture behind the outlier story in the notes from the build: HCN's distribution on a log scale. The two blue humps are *real* (trace producers and gene-carrying producers). Only the far-right red tail, beyond 3×p95 (the dashed line), gets capped. A fence between the humps, which is where the textbook rule landed, would have wiped out a whole population of real producers.

### One voice per genus

![Text harmonization](../figures/text_harmonization.png)

Left: the raw genus column's many spellings (trailing spaces, case chaos, the typo). Right: the clean set of genera, one bar each. Every later group-by, count and chart depends on this step having happened.

### What the cabinet now holds

![Database schema](../figures/database_schema.png)

The whole database at a glance: three cleaned synthetic tables (blue) and the real tables from Phase 1b (green), side by side in one file. I kept them in a single file on purpose, so one SQL query can reach across both worlds.

## 7. Meet the database: your first SQL

The cabinet is built, so now you can ask it questions. The project ships its own
SQL console, and it's read-only, so nothing you type can break or lock anything:

```bash
python src/strainscope/sql.py
```

**You should see** a `sql>` prompt. Ask your first question:

```
sql> SELECT kingdom, COUNT(*) AS n FROM phenotype GROUP BY kingdom;
```

Helpers worth knowing: `.tables` lists every table, `.schema phenotype` lists a
table's columns, and `exit` leaves. Multi-line statements are welcome: paste a
whole cookbook recipe and it runs when a line ends with `;` (the `  ->`
continuation prompt shows the console is still listening, and an empty line also
runs whatever's buffered). A typo only prints the error and brings the prompt
back, so experiment freely. (One-shot mode works too:
`python src/strainscope/sql.py "SELECT ..."`.)

Under the hood, the console is ~40 lines wrapped around DuckDB's Python
interface. You can do the same by hand in any Python session, and that's how the
app will do it later:

```python
import duckdb
con = duckdb.connect("data/processed/strainscope.duckdb", read_only=True)
con.execute("SELECT kingdom, COUNT(*) AS n FROM phenotype GROUP BY kingdom").fetchdf()
# ... keep querying `con` as long as you like ...
```

> **The one rule of connections:** a connection is an open phone line, and
> `con.close()` hangs up. A closed connection **stays** closed. Trying to use
> it raises `Connection already closed!`, and the fix is to *dial again*
> (run the `duckdb.connect(...)` line to make a new one). Close it once you've
> finished exploring, rather than between queries. (The console handles all of
> this for you, which is one more reason to use it as your front door.)

**You should see** the four kingdoms with 267/183/95/55. That matches Phase 1's ledger exactly, which doubles as a check that *cleaning preserved the biology*.

Next, a query that shows why a database is worth having, with three tables answering one question:

```python
con.execute("""
    SELECT p.strain_id, p.kingdom, p.suppression_score, g.ituA, m.iturin
    FROM phenotype p
    JOIN genomics g USING (strain_id)
    JOIN metabolomics m USING (strain_id)
    WHERE p.is_effective = 1
    ORDER BY p.suppression_score DESC LIMIT 5
""").fetchdf()
```

**What it means:** the top strains all show `ituA = 1` and high iturin. That's the hidden signal Phase 1 planted, showing up through five lines of SQL before any model exists. When you're done, run `con.close()`.

From here, work through the [Query Cookbook](QUERY_COOKBOOK.md). Every recipe is tested and explained in English, and the cookbook also has the queries that reach into the *real* tables (your BacDive strains, the PubChem chemistry, the KEGG edges).

## 8. The tests

```bash
pytest -q
```

**You should see:** `14 passed`. That's Phase 1b's six ingestion tests plus seven new ones, one per cleaning behaviour: duplicates, text (space/case/typo), clipping, the bimodality-safe outlier cap, batch-median equalisation, the DuckDB loader's real-table auto-load, and idempotency (build the database twice and get an identical result). As always, they run offline in under a second, on tiny hand-made dirty tables.

## 9. Two ways to run everything (running tally)

| Capability | Manual path (now) | Automatic path (later) |
|---|---|---|
| Generate synthetic data | `python src/strainscope/generate_data.py` | the one-command pipeline (Phase 8) |
| Probe / fetch real data | `python src/strainscope/fetch_real.py [--probe]` | the app's **Upload · Synthetic · Fetch-real** picker |
| **Clean + build the database** | `python src/strainscope/harmonize.py` | runs automatically inside the pipeline |
| **Question the data** | the SQL console: `python src/strainscope/sql.py` + the [Cookbook](QUERY_COOKBOOK.md) | the app's SQL console (Phase 6), cookbook built in |
| Make the figures | `python figures/make_phase2_figures.py` (etc.) | regenerated on demand; interactive in the app |

## 10. Same task, different language (optional, 10 min)

*"Remove duplicate strains, then count per kingdom"*, written in the two tools this phase brought together:

**pandas (the desk):**
```python
import pandas as pd
(pd.read_csv("data/raw/phenotype.csv")
   .drop_duplicates("strain_id")
   .groupby("kingdom").size())
```

**SQL (the cabinet):**
```sql
SELECT kingdom, COUNT(*) AS n
FROM (SELECT DISTINCT ON (strain_id) * FROM 'data/raw/phenotype.csv')
GROUP BY kingdom;
```
*(DuckDB can query a CSV file directly, which is a handy trick to know. Paste it into the console from the project root; the `;` on the last line is what tells the console the statement is complete.)*

Both give the same answer. As for the trade-off, pandas is strongest at *transforming* (our cleaning functions are pandas), while SQL is strongest at *questioning* what's stored, and it's the language every data team, tool and warehouse already speaks. This project uses each one where it's strongest, which is the usual way to split the work in practice.

## 11. What could go wrong (mini-FAQ)

- **`FileNotFoundError: data/raw/genomics.csv`**: Phase 1's data isn't there (a fresh clone, or you cleaned up). Regenerate it with `python src/strainscope/generate_data.py`; the same seed gives identical data.
- **`ModuleNotFoundError: No module named 'duckdb'`** means the venv isn't active or the requirements aren't installed: `pip install -r requirements.txt`.
- **My ledger numbers differ from §5's.** Almost always the raw data was generated with a modified seed or an older generator. Regenerate with the committed `src/strainscope/generate_data.py` (SEED = 42) and re-run. Cleaning is idempotent, so this costs nothing.
- **`0 real table(s)` loaded**: Phase 1b hasn't been fetched on this machine. It's optional; run `python src/strainscope/fetch_real.py` whenever you like, then re-run `src/strainscope/harmonize.py` and the tables appear.
- **`database is locked` or similar when re-running `src/strainscope/harmonize.py`**: some session holds the file open for *writing*. (The SQL console can't be the culprit, because it opens read-only.) Close stray Python sessions and re-run.
- **I pasted a multi-line query and got several strange errors, one per line.** You're on an old copy of `src/strainscope/sql.py` (the first version executed line by line). Update to the current console, which buffers until a `;` or an empty line completes the statement.
- **`No files found that match the pattern "data/raw/…"`**: the query reads a CSV by *relative* path, so start the console from the project root (the folder with `docs/` in it).
- **`Connection Error: Connection already closed!`** You ran `con.close()` (perhaps as the last line of a pasted snippet) and then queried the same `con`. Closed connections can't be revived, so make a new one by re-running the `duckdb.connect(...)` line, then your query. The SQL console avoids this entirely.
- **The interactive HTML shows only one view.** You're looking at the static PNG; the buttons live in `docs/interactive/batch_before_after.html` (double-click to open it in a browser).

## 12. Save your work (commit ritual + safety gate)

```bash
pytest -q                     # 14 passed
./check-public-safe.sh        # SAFE TO PUSH  (the .duckdb file is gitignored - data is regenerated, never committed)
git switch develop
git add -A
git commit -m "feat: add cleaning pipeline with ledger and DuckDB database; seed the SQL cookbook"
git push origin develop develop:beta develop:master
git switch master && git pull --ff-only origin master && git switch develop
```

## 13. What you learned, and what's next

**You learned:** raw data is evidence, and cleaning writes new files; the six cleaning rules and *why their order matters*; the ledger habit (you watched it catch a real bug that a textbook rule caused); why bimodal data breaks one-humped rules; what *can't* be cleaned and how to document it; the desk-vs-cabinet mental model; and enough SQL to filter, group, join and respect `NULL`, with a tested cookbook to grow from.

**Try it yourself (extensions):**
- In §7's session, find the *worst* effective strain (`ORDER BY … ASC LIMIT 1`) and look at its genes. What is it winning with?
- Change the outlier `mult` from 3.0 to 1.5 in `src/strainscope/harmonize.py`, re-run, and watch the ledger count jump. Then look at `outliers_capped.png` to see *what* you'd be flattening. (Put it back afterwards.)
- Write one cookbook query of your own (for example, the effective rate per `collection_site`) and add it to `docs/QUERY_COOKBOOK.md`. It's your cookbook now.

**Next:** [`docs/04-integration.md`](04-integration.md), **Phase 3**, where the layers stop being separate tables. Multi-omics integration (DIABLO in R, with a Python companion) finds the cross-layer signatures that separate winners from the rest. It's the most specialised part of the project.
