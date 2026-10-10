# Glossary — every term, in plain language

[← README](../README.md) · [Handbook](HANDBOOK.md) · [All docs in order](../README.md#the-tutorial-in-order)

This is a living document. Every technical or biological term used anywhere in
StrainScope is defined here in everyday language, grouped by the phase where it
first appears. If a term is missing, that's a documentation bug worth fixing.

> The rule of the project: **no undefined jargon.** If you hit a word you don't
> know, it should be here — with an everyday analogy wherever one helps.

---

## Setup & architecture (docs 00–01)

- **Backend** — the "kitchen": code that does the real work behind the scenes (generating, cleaning, modelling). Users never see it, only its results.
- **Frontend** — the "dining room": the part a person sees and clicks (our Streamlit app).
- **Database** — the "pantry": organised storage you question precisely with SQL. Ours is DuckDB.
- **SQL** — the near-universal language for asking a database questions ("give me every strain scoring above 80").
- **DuckDB** — a free, single-file SQL database engine, tuned for analysis. "A spreadsheet you talk to in SQL."
- **Pipeline** — a fixed sequence of steps run in order, like an assembly line: raw material in, finished product out.
- **Artifact** — a saved output file (a prediction table, a trained model, a chart). Computed once, reused many times.
- **Deployment** — putting your app on a computer on the internet so others can use it, not just your laptop.
- **Git** — a "save-game system" for code: snapshots you can return to, and how your project reaches GitHub.
- **Repository (repo)** — the project as Git tracks it; lives both locally and on GitHub.
- **Branch** — a parallel copy of the project. We use `master` (stable), `beta` (preview), `develop` (working).
- **Commit** — one saved snapshot, with a short message describing it.
- **Push** — send your local snapshots up to GitHub.
- **Virtual environment (`.venv`)** — a sealed, per-project toolbox of Python packages, so projects don't clash.
- **`requirements.txt`** — the shopping list of Python packages that rebuilds `.venv`.
- **`renv`** — R's equivalent of a virtual environment: a sealed, per-project R toolbox.
- **`renv.lock`** — the receipt of exact R package versions; the R twin of `requirements.txt`.
- **`.Rprofile`** — a small file that auto-activates renv whenever R starts in the project. Committed (no secrets).
- **`.Rproj`** — an RStudio project file; opening it sets the working directory and activates renv. Optional.
- **CRAN vs Bioconductor** — two "app stores" for R packages. General packages live on CRAN; biology packages (like mixOmics) live on Bioconductor.
- **Package** — a reusable bundle of pre-written code you install and import.
- **`.gitignore`** — the list of files Git should never save (secrets, rebuildable toolboxes, regenerated data).
- **Pre-push safety gate (`check-public-safe.sh`)** — a script that scans what Git tracks and refuses the all-clear if a secret or local path would be published. "A guard checking your bag on the way out."
- **API key / secret** — a private credential (like a password) that must never be committed to a public repo.
- **Tracked / new (untracked) / ignored file** — the three kinds of file in a Git project. *Tracked*: already saved in Git. *New*: in the folder but not in Git yet, and not ignored — `git add -A` will add it. *Ignored*: listed in `.gitignore`, so Git never adds it. "Items in the parcel, items next to it about to go in, and items on the shelf marked never send." The safety gate reads the first two.
- **Staging (`git add`)** — choosing what goes into the next commit; the staging area is the parcel being packed before it is sealed (`git commit`).
- **Force-add (`git add -f`)** — adding a file even though `.gitignore` lists it. Once added it is tracked, and the safety gate checks it like any other.
- **Plain keyboard characters (ASCII)** — the letters, digits and punctuation on an ordinary keyboard. Commands and commit/tag messages in this project use only these; look-alikes such as a long dash `—` or curly quotes `“ ”` can be garbled when pasted into a terminal.
- **Regression test** — a test written to catch a bug that once happened, so it can never quietly come back. It should *fail* on the old, broken code — that proves it guards the fix.
- **Patch release** — a version that only fixes things (the third number goes up: v0.1.0 → v0.1.1).

## Phase 1 — the data (doc 02)

### Biology
- **Biologicals** — crop-protection products derived from nature (living microbes, extracts, or natural molecules) instead of synthetic chemicals.
- **Microbe** — a tiny living organism. Beneficial ones protect plants or help them grow.
- **Kingdom** — a top-level grouping of living things. We model four *cellular* microbial kingdoms: **Bacteria**, **Fungi**, **Yeasts** (single-celled fungi), and **Oomycetes** (fungus-like organisms). Each fights pests differently.
- **Fungi** — a kingdom of organisms (moulds, mushrooms, yeasts). Biocontrol fungi like *Trichoderma* attack plant pathogens directly.
- **Yeast** — a single-celled fungus; biocontrol yeasts mostly work by out-competing pests for space and nutrients.
- **Oomycete** — a fungus-like microbe (e.g. *Pythium oligandrum*); a few are helpful biocontrol agents even though many relatives are pathogens.
- **Viruses / protozoa** — also part of the biocontrol landscape, but they don't share the genome+metabolome "fingerprint" of the cellular kingdoms, so StrainScope names them as context and does *not* put them in the molecular dataset (an honest scoping choice).
- **Genus** — the next level of naming below kingdom (e.g. *Bacillus*, *Trichoderma*). Each strain has one.
- **Strain** — one specific isolate of a microbe. Our samples are strains; each gets a `strain_id`.
- **Mycoparasitism** — one fungus (or oomycete) literally attacking and feeding on another fungus; a key biocontrol mechanism of *Trichoderma* and *Pythium oligandrum*.
- **Entomopathogen** — an "insect-killing" microbe; entomopathogenic fungi like *Beauveria*/*Metarhizium* make insecticidal toxins (beauvericin, destruxin).
- **Biocontrol** — using a beneficial microbe to suppress a plant disease or pest.
- **Pathogen** — the disease-causing organism a biocontrol strain fights (often a fungus, here).
- **-omics** — "measuring a whole category at once." *Genomics* = all the genes; *metabolomics* = all the metabolites.
- **Multi-omics** — looking at several -omics layers together, and analysing them jointly.
- **Genome / gene** — the microbe's DNA blueprint; a gene is one instruction in it. Here: which helpful genes a strain carries.
- **Metabolite** — a small-molecule chemical a microbe produces. Some are natural antifungals/antibiotics/toxins.
- **Phenotype** — an observable outcome. Here: how well a strain suppresses disease (`suppression_score`).
- **Lipopeptide** — a class of soap-like antifungal molecules (surfactin, iturin, fengycin) made by some **bacteria**.
- **Siderophore** — a molecule (pyoverdine in bacteria; a yeast version too) that grabs iron, starving competing pathogens.
- **Chitinase / glucanase** — enzymes that digest fungal cell walls (dissolving their "armour"); used across kingdoms.
- **Killer toxin** — a protein some yeasts secrete to kill rival microbes.
- **Housekeeping gene** — a conserved gene present in almost every microbe of every kingdom (e.g. `ssu_rRNA`, `ef1a`, `rpb1`); carries no signal because it doesn't vary.
- **Plant-growth promotion (PGP)** — helping the plant grow directly (via nitrogen, phosphate, auxin, stress relief); a secondary outcome here.

### Data & method
- **Sample** — one thing you measured. Here, one strain.
- **Feature** — one measured column (one gene, one metabolite). One clue about a sample.
- **Signal vs noise (features)** — *signal* features genuinely drive the outcome; *noise* features vary but don't. Real data mixes both; finding the signal is the challenge.
- **Target / outcome / label** — the thing we want to predict. Here: `suppression_score` (a number) and `is_effective` (yes/no).
- **Synthetic (simulated) data** — data created by a program rather than measured in a lab. Honest and useful when real data is private, rare, or unavailable. "A flight simulator for the workflow."
- **Random seed** — the starting number that makes a computer's "random" choices repeatable. Same seed → same data, everywhere. "Shuffling the deck the same way every time."
- **Reproducibility** — the property that anyone can rerun your work and get the same result.
- **Class imbalance** — when one outcome is much rarer than the other (here ~24% "effective"). Naive models can cheat by always guessing the majority.
- **Missing value (`NaN`)** — a blank where a reading should be. Most models can't run with holes, so missingness must be handled.
- **Outlier** — an extreme value, often a measurement error; can distort analysis if not handled.
- **Batch effect** — systematic drift between groups of samples processed together, caused by *how* data was collected rather than real biology. Must be corrected or a model may "learn the batch."
- **Duplicate** — the same sample recorded more than once; must be de-duplicated.
- **Log-normal** — a right-skewed distribution (many small values, a few large) typical of chemical-abundance data.
- **Ledger** — an honest, printed summary of exactly what a step produced (counts in, counts out), so nothing changes silently.
- **`pathlib`** — Python's tool for building file paths that work the same on Windows, macOS, and Linux.
- **`__init__.py`** — an empty marker file that makes a folder an importable Python "package."

## Phase 1b — real-data ingestion (doc 02b)

- **API (Application Programming Interface)** — a website designed for programs instead of people: request a carefully-shaped URL, get raw data back. "A restaurant's service hatch — structured orders in, plates out."
- **JSON** — the labelled-boxes-inside-labelled-boxes format most APIs answer in: `{}` objects with named fields, `[]` lists.
- **Endpoint** — one specific "counter" of an API, reached by its URL path (e.g. PubChem's `/compound/name/...` counter).
- **REST** — the common style of web API where each URL names a thing and standard web requests (GET etc.) act on it. All three of our sources are REST-style.
- **Rate limit** — the maximum request speed a service allows (e.g. KEGG's 3/second). Exceed it and you're blocked. Our adapters pause between calls on purpose.
- **User-Agent** — the "who's calling" label sent with every request. Ours identifies the project politely.
- **HTTP status codes** — the numeric verdict on every web request: `200` OK, `404` not found (often an honest "no such entry", not an outage), `403` forbidden, `5xx` server trouble.
- **Provenance / provenance log** — the paper trail of where data came from. Our `data/raw/real/fetch_log.csv` records when, which source, what was asked, which URL, and how much came back — the permanent answer to "where did this number come from?"
- **Evidence locker** — `data/raw/real/<source>/`: every API response saved exactly as received, never edited. If parsing ever needs fixing, nothing was lost.
- **Adapter (the socket-and-plugs pattern)** — one shared contract (`probe → fetch → tidy`) that every data source implements. One socket, many plugs: adding a source is one new file.
- **Probe** — a cheap "what's out there?" call that counts what a fetch would bring back, before downloading anything. Measure twice, cut once.
- **Idempotent** — safe to run again: re-fetching rewrites the same files rather than piling up duplicates or breaking.
- **Canned response (offline testing)** — a tiny, hand-made copy of an API answer saved with the tests, so parsing logic can be verified in milliseconds, offline, without bothering a live server.
- **Attribution / licence note** — the usage terms that travel with data. KEGG's API is **academic-use only**; our tables carry an attribution column so the condition is never separated from the rows.
- **BacDive** — the DSMZ's Bacterial Diversity Metadatabase: ~82,000 real, curated bacterial strains, strain-level metadata, free API.
- **PubChem** — the NIH's open chemistry reference (100M+ compounds); our metabolites' real IDs, formulas, and weights come from here.
- **KEGG** — the Kyoto Encyclopedia of Genes and Genomes: the hand-curated map of how genes, enzymes, compounds, and pathways connect; the source of the knowledge graph's first real edges.
- **CID / KEGG ID** — a database's permanent number for a molecule (PubChem CID, KEGG `C…` code). IDs beat names: names are ambiguous, IDs aren't.
- **SMILES** — a text notation that encodes a molecule's structure in one line, so software can exchange chemical structures.

## Phase 2 — cleaning & the database (doc 03)

- **Raw vs processed data** — raw files are *evidence*, never edited; cleaning reads them and writes new files into `data/processed/`. "Annotate a copy; never draw on the original."
- **Cleaning ledger** — the accounting of cleaning: rows in, rows out, cells changed, per step. Reconciling it against what you *know* is how silent damage gets caught (it caught a real bug in this project).
- **Harmonisation (text)** — forcing one agreed spelling per real-world thing: strip spaces, unify case, fix typos from a written-down list — never by guessing.
- **Controlled vocabulary** — that written-down list of allowed values (e.g. the genus spellings). The antidote to `Soil`, `soil `, and `SOIL` being counted as three places.
- **Clipping** — pushing an impossible value to the nearest possible boundary (a 104 % suppression becomes 100 %). The strain stays; only the overshoot goes.
- **Winsorising / capping** — replacing extreme values with a ceiling instead of deleting the row. Keeps the sample, removes the distortion.
- **Percentile (p95)** — the value below which 95 % of the data sits. Our outlier ceiling is 3×p95: "three times the upper edge of plausible is an artifact."
- **Quartile / IQR** — Q1/Q3 are the 25 %/75 % marks; IQR is the spread between them. The textbook outlier fence (Q3 + k·IQR) assumes one-humped data — and fails on two-humped data like ours.
- **Bimodal** — a distribution with two humps. Ours: a *trace* hump (gene absent) and a *producer* hump (gene present). Many textbook rules silently assume one hump.
- **Batch-effect correction (median-scaling)** — per batch and metabolite, divide by (batch median ÷ overall median), cooling a hot batch by exactly its drift. Medians, so leftover extremes can't drag the factor.
- **Imputation** — filling missing values. Deliberately *not* done in cleaning: the right strategy depends on the downstream method, so it's a modelling decision made openly later — Phase 3 fills gaps *within each kingdom* without looking at the outcome (see *kingdom-wise imputation* below).
- **Idempotent (cleaning)** — run it twice, get the identical result. What makes re-running safe and casual.
- **Database** — the "filing cabinet": organised, permanent storage you question with SQL — versus the pandas "desk" (fast, in-memory, gone when you stand up).
- **DuckDB** — a full SQL analytics database living in one ordinary file (`strainscope.duckdb`). No server, no setup drama. "A filing cabinet you can zip up and email."
- **SQL** — the ~50-year-old language for questioning tables; still the most-demanded data skill. Reads almost like English.
- **`SELECT` / `WHERE` / `ORDER BY` / `LIMIT`** — choose columns / keep matching rows / sort / take the first N.
- **`GROUP BY`** — fold a table into one row per category ("per kingdom, count strains").
- **`JOIN`** — line tables up on a shared key (`strain_id`) so one question can span genomics, metabolomics, and phenotype at once.
- **`NULL`** — SQL's honest "no value here." Special grammar: `IS NULL`, never `= NULL` (which silently matches nothing).
- **Schema** — the shape of a database: which tables exist and what columns each holds.
- **Query cookbook** — this project's growing file of tested, explained SQL recipes ([`docs/QUERY_COOKBOOK.md`](QUERY_COOKBOOK.md)).

## Phase 1c — more real sources & secrets (doc 02c)

- **API key** — a personal access code for a service; a "membership card". NCBI's is free and optional (it doubles the rate limit) — the perfect low-stakes place to learn the handling discipline.
- **Secret** — any value that must never be public: keys, passwords, tokens. The iron rule: a secret never enters the repository — history, forks, and caches remember forever, and scrapers harvest leaked keys within minutes.
- **Environment (variables)** — the private named values a running program carries "in its pockets"; where secrets live. Set per session (`export KEY=...`) or per project (`.env`).
- **`.env` file** — one `KEY=VALUE` per line at the project root, read at startup by `load_env()`; git-ignored **and** watched by the safety gate. The shell wins if both define a key.
- **`.env.example`** — the committed *template*: variable names, empty values, instructions. Template public, values private — how projects document their secrets without leaking them.
- **Rate-limit tiers** — some services serve keyholders faster (NCBI: 5 req/s anonymous → 10 with a key). A key here is a courtesy upgrade, not a lock.
- **Genome assembly** — the reconstructed sequence of an organism's genome, with a quality level (contig → scaffold → chromosome → complete).
- **Accession** — a database's permanent ID for one assembly (e.g. `GCF_000009045.1`); IDs beat names, as ever.
- **GC content (GC %)** — the fraction of a genome's letters that are G or C; a stable fingerprint that differs between organisms.
- **Genome size (bp / Mb)** — length in base pairs; bacterial genomes run ~4–8 million letters, fungal ones ~10× that — visible in this project's own fetched data.
- **RefMet** — Metabolomics Workbench's curated "official names register" for metabolites, each entry carrying a classification ladder (super-class → main class → sub-class): chemistry's shelving system, and knowledge-graph fodder.
- **Metabolomics Workbench** — the NIH's open archive of real metabolomics studies + RefMet.
- **NCBI Datasets** — the NIH's API over the world's genome-assembly catalogue; source of our multi-kingdom `real_genomes` table.
- **`curl`** — the universal command-line tool that speaks raw HTTP; handy for poking any API from any terminal (with headers attached by hand).
- **Header (HTTP)** — a labelled note sent alongside a request (our `User-Agent`; NCBI's `api-key`). Data about the request, not part of the URL.

## Phase 3 — multi-omics integration (doc 04)

- **Block** — one kind of measurement for the same samples, kept as its own table: the *genomics block* (genes) and the *metabolomics block* (metabolites). "Two witnesses describing the same strains."
- **Integration** — analysing several blocks *together* so that what they agree on stands out. "Two witnesses whose stories match are more convincing than either alone."
- **Early / intermediate / late integration** — three ways to combine blocks. *Early*: glue the tables side by side and fit one model. *Intermediate*: give each block its own summary, but make the summaries agree (DIABLO). *Late*: fit one model per block and average their votes.
- **Block scaling** — before gluing blocks together (early integration), divide each block by the square root of its number of columns, so a block with many columns cannot drown out a smaller one just by being bigger.
- **Alignment** — putting every block in the same strain order, keeping only strains present in all of them; the shared key is `strain_id`.
- **Kingdom-wise imputation** — filling a gap with the typical value *of that strain's kingdom* (the most common call for a gene, the median for a metabolite), never using the outcome. A missing bacterial reading is filled with a bacterial value, not a fungal one.
- **Near-constant feature** — a column where almost every sample has the same value (here: ≥ 95 %), like the housekeeping genes. It carries no information and breaks some methods, so it is dropped — and the drop is written in the ledger.
- **Centring (within kingdom)** — subtracting each kingdom's own average from its strains, so every feature reads "more or less than is typical *for this kind of microbe*". The outcome is judged within kind too, so the yardsticks match — this cut DIABLO's error by about a third.
- **`log(1 + x)` transform** — squashes right-skewed chemical abundances so a few huge readings don't dominate; the `1 +` keeps zero at zero.
- **DIABLO** — *Data Integration Analysis for Biomarker discovery using Latent cOmponents*: the supervised integration method of the R package **mixOmics**. It builds a few summary scores per block that must agree with each other *and* separate the outcome groups, keeping only a short list of features.
- **mixOmics** — the free Bioconductor R package that provides DIABLO and its standard plots.
- **Component** — one summary score DIABLO builds per block: a weighted sum of features. Component 1 is the strongest shared story; component 2 the next one, independent of the first.
- **Loading** — the weight a feature gets in a component; its sign says in which direction it pushes and its size how much.
- **Sparse / sparsity** — keeping most weights at exactly zero so only a short, readable list of features remains.
- **`keepX`** — DIABLO's setting for how many features to keep per block and per component; *tuned* by cross-validation rather than guessed.
- **Design matrix** — DIABLO's setting for how strongly blocks must agree with each other (0 = not at all, 1 = as much as possible). We use 0.1: some agreement, prediction first.
- **Tuning** — trying several values of a setting and keeping the one that scores best under cross-validation.
- **PLS-DA** — *partial least squares discriminant analysis*: the single-table ancestor of DIABLO; builds components from all features at once to separate groups.
- **Lasso (L1) logistic regression** — a prediction model that pushes most feature weights to exactly zero, so it selects features as it learns.
- **Cross-validation** — honest scoring by rotation: split the strains into 5 parts, train on 4, test on the unseen 5th, rotate until every part has been the test once. "Never mark your own homework with the answer sheet open."
- **Repeated (stratified) cross-validation** — doing the 5-part rotation 10 times with different random splits, each keeping the effective/not-effective proportions; averages out the luck of one particular split and gives an uncertainty (±).
- **Balanced error rate (BER)** — the average of the error on each outcome group. Unlike plain accuracy it cannot be gamed by always guessing the common group: that lazy strategy scores 0.50, exactly like a coin.
- **AUC (area under the ROC curve)** — the chance that a randomly chosen effective strain gets a higher score than a randomly chosen non-effective one; 0.5 = coin, 1.0 = perfect ranking.
- **Negative control** — a deliberately useless input that *must* fail (score like a coin). If it does not, something is leaking. Ours: the kingdom label alone, and shuffled labels.
- **Y-scrambling (label shuffling)** — randomly re-dealing the outcome labels so any real link is destroyed, then re-running the whole procedure; the score must collapse to chance.
- **Leakage** — information from the test strains sneaking into training, making scores look better than they are. Phase 3 documents a small, label-free one (gap filling and centring use all strains); Phase 4 removes it by moving them inside the cross-validation loop.
- **One-standard-deviation rule** — among settings whose score is within one ± of the best, choose the simplest. Prefers fewer components when more do not clearly help.
- **Cost of sparsity** — how much error a short feature list costs compared with using every feature, expressed in standard deviations so "small" has a meaning.
- **Stability (selection)** — the share of cross-validation re-fits in which a feature is picked again. ≥ 80 % = *robust*; a feature picked only occasionally is quota-filling, not a finding.
- **Signature** — the short list of features a method selects as the explanation of the outcome.
- **Grading against planted truth** — because the data is simulated, we *know* which features truly drive the outcome, so every signature can be marked: how many picks are true drivers (precision) and how many true drivers were found (recall). One of synthetic data's quiet superpowers.
- **Decoy** — a feature planted to *look* plausible but carry no signal; a good signature avoids it.
- **Spearman correlation (rho)** — how consistently two columns rise and fall together, using ranks rather than raw values (robust to skew and outliers); −1 to +1.
- **Producer pair** — a gene and the compound it helps make (e.g. `ituA` → iturin); in real biology these should correlate, and in our data they do (median rho 0.72).
- **Contract (R ↔ Python)** — the agreed list of hand-off file names and columns two programs exchange; a test checks both sides use the same names, so one cannot silently drift.
- **Hand-off file** — a plain CSV one step writes and another reads; the only way R and Python talk in this project.
- **`Rscript`** — the command that runs an R script (or one line, with `-e`) and quits; works the same on every operating system.
- **Installed but invisible** — a package installed on your computer that R *inside this project* cannot see, because renv shows only the project's own library. The fix is to install it into the project (`renv::install`).
- **Plotly** — a charting library that makes interactive web charts (hover, zoom). Our interactive pages share one copy of its code, `docs/interactive/plotly.min.js`.

## The Handbook, releases and the planned phases (docs HANDBOOK, ROADMAP, PRODUCT_ROADMAP)

- **Handbook** — [`docs/HANDBOOK.md`](HANDBOOK.md): the one living document that walks the whole journey from a blank laptop to the finished product and links every specialised guide. Read first; updated in the same commit as every change.
- **Roadmap** — the ordered plan of what gets built next and why ([`docs/ROADMAP.md`](ROADMAP.md)); the **product roadmap** looks beyond this repository ([`docs/PRODUCT_ROADMAP.md`](PRODUCT_ROADMAP.md)).
- **Verdict / trigger** — in the product roadmap, every technology gets a verdict (*required now · recommended later · optional · not needed*) and a trigger: the observable event that would change it. "Justify, don't accumulate."
- **Tag (Git)** — a bookmark on one exact commit, named with a version number (`v0.1.0`), so anyone can return to that state. *Annotated* tags (`git tag -a`) also record who, when and why.
- **Semantic versioning** — version numbers as `MAJOR.MINOR.PATCH`: MINOR for a new usable level, PATCH for fixes, MAJOR 1 for the first complete release.
- **Changelog** — [`CHANGELOG.md`](../CHANGELOG.md): the human-readable list of what changed in each version.
- **Calibration** *(Phase 4)* — whether predicted probabilities mean what they say: of all strains given "80 %", about 80 % should really be effective.
- **Ontology** *(Phase 5)* — the agreed rules of what kinds of things exist in a domain and how they may connect (a strain *carries* a gene, a gene *helps make* a compound). "A family tree for concepts."
- **Knowledge graph** *(Phase 5)* — the filled-in family tree: actual strains, genes, compounds and pathways as dots (nodes) joined by labelled lines (edges) you can walk.
- **Hub** — a node with unusually many connections; often a key gene or compound.
- **RAG (retrieval-augmented generation)** *(Phase 6b–7)* — find the relevant passages first, then let a language model write an answer *only from them*, citing them. "An open-book exam, with the page numbers written down."
- **Ask StrainScope** *(Phase 6b)* — the project's documentation assistant: answers from the project's own documents with links, and refuses questions that are not about StrainScope.
- **Out-of-scope refusal** — the assistant's polite "that isn't about this project" when even the best-matching passage matches weakly; it happens *before* any language model is called, so nothing can be invented.
- **Golden question set** — a fixed list of questions with known right answers (and off-topic questions that must be refused), run with the tests on every change.
- **Language model (LLM)** — a program trained on large amounts of text that writes fluent text. Here it is optional and only ever rephrases supplied facts or passages.
- **Ollama** — free software that runs open language models on your own computer (Windows, macOS, Linux), so nothing leaves the laptop.
- **Text-to-SQL / data assistant** *(Phase 7)* — turning a question in plain words into a SQL query, run read-only, with the query shown so it can be checked.
- **GraphRAG** *(Phase 7)* — RAG where the "passages" are paths walked through the knowledge graph, cited as the route taken.
- **MCP (Model Context Protocol)** *(Phase 7b)* — an open standard that lets AI assistants call a program's tools in a uniform way. "A USB port for AI assistants."
- **Continuous integration (CI)** *(Phase 8)* — a service (here GitHub Actions) that runs the tests automatically on fresh Windows, macOS and Linux machines at every push.
- **Container** *(Phase 8, optional)* — a sealed, portable box holding a program plus everything it needs to run (Python, R, packages), so it runs the same anywhere.

