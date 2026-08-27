# Glossary — every term, in plain language

[← README](../README.md) · [All docs in order](../README.md#the-tutorial-in-order)

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
- **Provenance / provenance log** — the paper trail of where data came from. Our `fetch_log.csv` records when, which source, what was asked, which URL, and how much came back — the permanent answer to "where did this number come from?"
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
