# Glossary: every term, in plain language

[← README](../README.md) · [Handbook](HANDBOOK.md) · [All docs in order](../README.md#the-tutorial-in-order)

This is a living document. Every technical or biological term used anywhere in
StrainScope is defined here in everyday language, grouped by the phase where it
first appears. If a term is missing, that's a documentation bug worth fixing.

> The rule of the project: **no undefined jargon.** If you hit a word you don't
> know, it should be here, with a familiar comparison wherever one helps.

---

## Setup & architecture (docs 00 and 01)

- **Backend**: the "kitchen", meaning the code that does the real work behind the scenes (generating, cleaning, modelling). Users never see it, only its results.
- **Frontend**: the "dining room", the part a person sees and clicks (our Streamlit app).
- **Database**: the "pantry", organised storage you question precisely with SQL. Ours is DuckDB.
- **SQL**: the near-universal language for asking a database questions ("give me every strain scoring above 80").
- **DuckDB**: a free, single-file SQL database engine, tuned for analysis. Think of it as a spreadsheet you talk to in SQL.
- **Pipeline**: a fixed sequence of steps run in order, like an assembly line where raw material goes in at one end and the finished product comes out at the other.
- **Artifact**: a saved output file (a prediction table, a trained model, a chart). It's computed once and reused many times.
- **Deployment**: putting your app on a computer on the internet so other people can use it too, instead of it living only on your laptop.
- **Git**: a "save-game system" for code. It keeps snapshots you can return to, and it's how your project reaches GitHub.
- **Repository (repo)**: the project as Git tracks it; it lives both locally and on GitHub.
- **Branch**: a parallel copy of the project. We use `master` (stable), `beta` (preview) and `develop` (working).
- **Commit**: one saved snapshot, with a short message describing it.
- **Push**: send your local snapshots up to GitHub.
- **Virtual environment (`.venv`)**: a sealed, per-project toolbox of Python packages, so projects don't clash.
- **`requirements.txt`**: the shopping list of Python packages that rebuilds `.venv`.
- **`renv`**: R's equivalent of a virtual environment, i.e. a sealed, per-project R toolbox.
- **`renv.lock`**: the receipt of exact R package versions; the R twin of `requirements.txt`.
- **`.Rprofile`**: a small file that auto-activates renv whenever R starts in the project. It's committed (there are no secrets in it).
- **`.Rproj`**: an RStudio project file; opening it sets the working directory and activates renv. Optional.
- **CRAN vs Bioconductor**: two "app stores" for R packages. General packages live on CRAN; biology packages (like mixOmics) live on Bioconductor.
- **Package**: a reusable bundle of pre-written code you install and import.
- **`.gitignore`**: the list of files Git should never save (secrets, rebuildable toolboxes, regenerated data).
- **Pre-push safety gate (`check-public-safe.sh`)**: a script that scans what Git tracks and refuses the all-clear if a secret or local path would be published. Picture a guard checking your bag on the way out.
- **API key / secret**: a private credential (like a password) that must never be committed to a public repo.
- **Tracked / new (untracked) / ignored file**: the three kinds of file in a Git project. *Tracked*: already saved in Git. *New*: in the folder but not in Git yet, and not ignored, so `git add -A` will add it. *Ignored*: listed in `.gitignore`, so Git never adds it. In parcel terms, these are the items in the parcel, the items next to it about to go in, and the items on the shelf marked "never send". The safety gate reads the first two.
- **Staging (`git add`)**: choosing what goes into the next commit; the staging area is the parcel being packed before it's sealed (`git commit`).
- **Force-add (`git add -f`)**: adding a file even though `.gitignore` lists it. Once added it's tracked, and the safety gate checks it like any other.
- **Plain keyboard characters (ASCII)**: the letters, digits and punctuation on an ordinary keyboard. Commands and commit/tag messages in this project use only these; look-alikes such as a long dash (&mdash;) or curly quotes (&ldquo; &rdquo;) can be garbled when pasted into a terminal.
- **Regression test**: a test written to catch a bug that once happened, so it can never quietly come back. It should *fail* on the old, broken code, because that's what proves it guards the fix.
- **Patch release**: a version that only fixes things (the third number goes up: v0.1.0 → v0.1.1).

## Phase 1: the data (doc 02)

### Biology
- **Biologicals**: crop-protection products derived from nature (living microbes, extracts, or natural molecules) instead of synthetic chemicals.
- **Microbe**: a tiny living organism. Beneficial ones protect plants or help them grow.
- **Kingdom**: a top-level grouping of living things. We model four *cellular* microbial kingdoms: Bacteria, Fungi, Yeasts (single-celled fungi), and Oomycetes (fungus-like organisms). Each fights pests differently.
- **Fungi**: a kingdom of organisms (moulds, mushrooms, yeasts). Biocontrol fungi like *Trichoderma* attack plant pathogens directly.
- **Yeast**: a single-celled fungus; biocontrol yeasts mostly work by out-competing pests for space and nutrients.
- **Oomycete**: a fungus-like microbe (e.g. *Pythium oligandrum*); a few are helpful biocontrol agents even though many relatives are pathogens.
- **Viruses / protozoa**: also used in biocontrol, but they don't share the genome+metabolome "fingerprint" of the cellular kingdoms, so StrainScope names them as context and does *not* put them in the molecular dataset (a scoping choice, stated up front).
- **Genus**: the next level of naming below kingdom (e.g. *Bacillus*, *Trichoderma*). Each strain has one.
- **Strain**: one specific isolate of a microbe. Our samples are strains; each gets a `strain_id`.
- **Mycoparasitism**: one fungus (or oomycete) literally attacking and feeding on another fungus; it's a major biocontrol mechanism of *Trichoderma* and *Pythium oligandrum*.
- **Entomopathogen**: an "insect-killing" microbe; entomopathogenic fungi like *Beauveria*/*Metarhizium* make insecticidal toxins (beauvericin, destruxin).
- **Biocontrol**: using a beneficial microbe to suppress a plant disease or pest.
- **Pathogen**: the disease-causing organism a biocontrol strain fights (here, often a fungus).
- **-omics**: "measuring a whole category at once." *Genomics* = all the genes; *metabolomics* = all the metabolites.
- **Multi-omics**: looking at several -omics layers together, and analysing them jointly.
- **Genome / gene**: the microbe's DNA blueprint; a gene is one instruction in it. Here we care about which helpful genes a strain carries.
- **Metabolite**: a small-molecule chemical a microbe produces. Some are natural antifungals/antibiotics/toxins.
- **Phenotype**: an observable outcome. In this project it's how well a strain suppresses disease (`suppression_score`).
- **Lipopeptide**: a class of soap-like antifungal molecules (surfactin, iturin, fengycin) made by some *bacteria*.
- **Siderophore**: a molecule (pyoverdine in bacteria; a yeast version too) that grabs iron, starving competing pathogens.
- **Chitinase / glucanase**: enzymes that digest fungal cell walls (dissolving their "armour"); used across kingdoms.
- **Killer toxin**: a protein some yeasts secrete to kill rival microbes.
- **Housekeeping gene**: a conserved gene present in almost every microbe of every kingdom (e.g. `ssu_rRNA`, `ef1a`, `rpb1`). Because it doesn't vary, it carries no signal.
- **Plant-growth promotion (PGP)**: helping the plant grow directly (via nitrogen, phosphate, auxin, stress relief); a secondary outcome here.

### Data & method
- **Sample**: one thing you measured. Here, one strain.
- **Feature**: one measured column (one gene, one metabolite), which gives you one clue about a sample.
- **Signal vs noise (features)**: *signal* features actually drive the outcome; *noise* features vary but don't. Real data mixes both, and finding the signal is the hard part.
- **Target / outcome / label**: the thing we want to predict. Here: `suppression_score` (a number) and `is_effective` (yes/no).
- **Synthetic (simulated) data**: data created by a program rather than measured in a lab. It's a useful option when real data is private, rare, or unavailable; you could call it a flight simulator for the workflow.
- **Random seed**: the starting number that makes a computer's "random" choices repeatable. Same seed → same data, everywhere, much like shuffling a deck of cards the same way every time.
- **Reproducibility**: the property that anyone can rerun your work and get the same result.
- **Class imbalance**: when one outcome is much rarer than the other (here ~24% "effective"). Naive models can cheat by always guessing the majority.
- **Missing value (`NaN`)**: a blank where a reading should be. Most models can't run with holes, so missingness must be handled.
- **Outlier**: an extreme value, often a measurement error; it can distort an analysis if it isn't handled.
- **Batch effect**: systematic drift between groups of samples processed together, caused by *how* data was collected rather than by real biology. It must be corrected, or a model may "learn the batch."
- **Duplicate**: the same sample recorded more than once; must be de-duplicated.
- **Log-normal**: a right-skewed distribution (many small values, a few large) typical of chemical-abundance data.
- **Ledger**: a printed summary of exactly what a step produced (counts in, counts out), so nothing changes silently.
- **`pathlib`**: Python's tool for building file paths that work the same on Windows, macOS, and Linux.
- **`__init__.py`**: an empty marker file that makes a folder an importable Python "package."

## Phase 1b: real-data ingestion (doc 02b)

- **API (Application Programming Interface)**: a website designed for programs instead of people. You request a carefully shaped URL and get raw data back. It works like a restaurant's service hatch, with structured orders going in and plates coming out.
- **JSON**: the labelled-boxes-inside-labelled-boxes format most APIs answer in: `{}` objects with named fields, `[]` lists.
- **Endpoint**: one specific "counter" of an API, reached by its URL path (e.g. PubChem's `/compound/name/...` counter).
- **REST**: the common style of web API where each URL names a thing and standard web requests (GET etc.) act on it. All three of our sources are REST-style.
- **Rate limit**: the maximum request speed a service allows (e.g. KEGG's 3/second). Exceed it and you're blocked, which is why our adapters pause between calls on purpose.
- **User-Agent**: the "who's calling" label sent with every request. Ours identifies the project politely.
- **HTTP status codes**: the numeric verdict on every web request: `200` OK, `404` not found (often a correct "no such entry" answer rather than an outage), `403` forbidden, `5xx` server trouble.
- **Provenance / provenance log**: the paper trail of where data came from. Our `data/raw/real/fetch_log.csv` records when, which source, what was asked, which URL, and how much came back, so "where did this number come from?" always has an answer.
- **Evidence locker**: `data/raw/real/<source>/`, where every API response is saved exactly as received and never edited. If parsing ever needs fixing, nothing was lost.
- **Adapter (the socket-and-plugs pattern)**: one shared contract (`probe → fetch → tidy`) that every data source implements. One socket, many plugs: adding a source is one new file.
- **Probe**: a cheap "what's out there?" call that counts what a fetch would bring back, before downloading anything (measure twice, cut once).
- **Idempotent**: safe to run again. Re-fetching rewrites the same files instead of piling up duplicates or breaking.
- **Canned response (offline testing)**: a tiny, hand-made copy of an API answer saved with the tests, so parsing logic can be verified in milliseconds, offline, without bothering a live server.
- **Attribution / licence note**: the usage terms that travel with data. KEGG's API is **academic-use only**; our tables carry an attribution column so the condition is never separated from the rows.
- **BacDive**: the DSMZ's Bacterial Diversity Metadatabase, with ~82,000 real, curated bacterial strains, strain-level metadata and a free API.
- **PubChem**: the NIH's open chemistry reference (100M+ compounds); our metabolites' real IDs, formulas, and weights come from here.
- **KEGG**: the Kyoto Encyclopedia of Genes and Genomes, a hand-curated map of how genes, enzymes, compounds, and pathways connect. It's the source of the knowledge graph's first real edges.
- **CID / KEGG ID**: a database's permanent number for a molecule (PubChem CID, KEGG `C…` code). IDs are safer than names, because a name can be ambiguous and an ID can't.
- **SMILES**: a text notation that encodes a molecule's structure in one line, so software can exchange chemical structures.

## Phase 2: cleaning & the database (doc 03)

- **Raw vs processed data**: raw files are *evidence* and are never edited; cleaning reads them and writes new files into `data/processed/`. The habit to keep: annotate a copy, and never draw on the original.
- **Cleaning ledger**: the accounting of cleaning (rows in, rows out, cells changed, per step). Reconciling it against what you *know* is how silent damage gets caught (it caught a real bug in this project).
- **Harmonisation (text)**: forcing one agreed spelling per real-world thing. You strip spaces, unify case and fix typos from a written-down list, never by guessing.
- **Controlled vocabulary**: that written-down list of allowed values (e.g. the genus spellings). It's what stops `Soil`, `soil `, and `SOIL` from being counted as three places.
- **Clipping**: pushing an impossible value to the nearest possible boundary (a 104 % suppression becomes 100 %). The strain stays; only the overshoot goes.
- **Winsorising / capping**: replacing extreme values with a ceiling instead of deleting the row. You keep the sample and lose the distortion.
- **Percentile (p95)**: the value below which 95 % of the data sits. Our outlier ceiling is 3×p95, on the reasoning that anything above three times the upper edge of plausible is an artifact.
- **Quartile / IQR**: Q1/Q3 are the 25 %/75 % marks; IQR is the spread between them. The textbook outlier fence (Q3 + k·IQR) assumes one-humped data, and it fails on two-humped data like ours.
- **Bimodal**: a distribution with two humps. Ours has a *trace* hump (gene absent) and a *producer* hump (gene present). Many textbook rules quietly assume there's only one.
- **Batch-effect correction (median-scaling)**: per batch and metabolite, divide by (batch median ÷ overall median), cooling a hot batch by exactly its drift. It uses medians so that leftover extremes can't drag the factor.
- **Imputation**: filling missing values. Cleaning leaves this out on purpose: the right strategy depends on the downstream method, so it's a modelling decision made openly later. Phase 3 fills gaps *within each kingdom* without looking at the outcome (see *kingdom-wise imputation* below).
- **Idempotent (cleaning)**: run it twice, get the identical result. That's what makes re-running safe and casual.
- **Database**: the "filing cabinet", organised and permanent storage you question with SQL. Compare the pandas "desk", which is fast and in-memory but gone when you stand up.
- **DuckDB**: a full SQL analytics database living in one ordinary file (`strainscope.duckdb`). There's no server and no setup drama (imagine a filing cabinet you can zip up and email).
- **SQL**: the ~50-year-old language for questioning tables, and still the most-demanded data skill. It reads almost like English.
- **`SELECT` / `WHERE` / `ORDER BY` / `LIMIT`**: choose columns / keep matching rows / sort / take the first N.
- **`GROUP BY`**: fold a table into one row per category ("per kingdom, count strains").
- **`JOIN`**: line tables up on a shared key (`strain_id`) so one question can span genomics, metabolomics, and phenotype at once.
- **`NULL`**: SQL's way of saying "no value here." It has its own grammar: `IS NULL`, never `= NULL` (which silently matches nothing).
- **Schema**: the shape of a database, meaning which tables exist and what columns each holds.
- **Query cookbook**: this project's growing file of tested, explained SQL recipes ([`docs/QUERY_COOKBOOK.md`](QUERY_COOKBOOK.md)).

## Phase 1c: more real sources & secrets (doc 02c)

- **API key**: a personal access code for a service, rather like a membership card. NCBI's is free and optional (it doubles the rate limit), which makes it a low-stakes place to learn how keys should be handled.
- **Secret**: any value that must never be public: keys, passwords, tokens. The iron rule is that a secret never enters the repository, because history, forks, and caches remember forever, and scrapers harvest leaked keys within minutes.
- **Environment (variables)**: the private named values a running program carries "in its pockets"; this is where secrets live. You set them per session (`export KEY=...`) or per project (`.env`).
- **`.env` file**: one `KEY=VALUE` per line at the project root, read at startup by `load_env()`; git-ignored **and** watched by the safety gate. The shell wins if both define a key.
- **`.env.example`**: the committed *template*, holding variable names, empty values and instructions. The template is public and the values stay private, which is how projects document their secrets without leaking them.
- **Rate-limit tiers**: some services serve keyholders faster (NCBI: 5 req/s anonymous → 10 with a key). Here the key only buys speed; nothing is locked without it.
- **Genome assembly**: the reconstructed sequence of an organism's genome, with a quality level (contig → scaffold → chromosome → complete).
- **Accession**: a database's permanent ID for one assembly (e.g. `GCF_000009045.1`). As ever, IDs beat names.
- **GC content (GC %)**: the fraction of a genome's letters that are G or C; a stable fingerprint that differs between organisms.
- **Genome size (bp / Mb)**: length in base pairs. Bacterial genomes run ~4 to 8 million letters and fungal ones ~10× that, which you can see in this project's own fetched data.
- **RefMet**: Metabolomics Workbench's curated "official names register" for metabolites. Each entry carries a classification ladder (super-class → main class → sub-class), so it works as chemistry's shelving system and gives the knowledge graph plenty to build on.
- **Metabolomics Workbench**: the NIH's open archive of real metabolomics studies + RefMet.
- **NCBI Datasets**: the NIH's API over the world's genome-assembly catalogue; source of our multi-kingdom `real_genomes` table.
- **`curl`**: the universal command-line tool that speaks raw HTTP; handy for poking any API from any terminal (with headers attached by hand).
- **Header (HTTP)**: a labelled note sent alongside a request (our `User-Agent`; NCBI's `api-key`). It carries data about the request and sits outside the URL itself.

## Phase 3: multi-omics integration (doc 04)

- **Block**: one kind of measurement for the same samples, kept as its own table: the *genomics block* (genes) and the *metabolomics block* (metabolites). Picture two witnesses describing the same strains.
- **Integration**: analysing several blocks *together* so that what they agree on stands out. Two witnesses whose stories match are more convincing than either one alone.
- **Early / intermediate / late integration**: three ways to combine blocks. *Early*: glue the tables side by side and fit one model. *Intermediate*: give each block its own summary, but make the summaries agree (DIABLO). *Late*: fit one model per block and average their votes.
- **Block scaling**: before gluing blocks together (early integration), divide each block by the square root of its number of columns, so a block with many columns can't drown out a smaller one just by being bigger.
- **Alignment**: putting every block in the same strain order, keeping only strains present in all of them; the shared key is `strain_id`.
- **Kingdom-wise imputation**: filling a gap with the typical value *of that strain's kingdom* (the most common call for a gene, the median for a metabolite), never using the outcome. So a missing bacterial reading gets a bacterial value and never a fungal one.
- **Near-constant feature**: a column where almost every sample has the same value (here: ≥ 95 %), like the housekeeping genes. It carries no information and breaks some methods, so it's dropped, and the drop is written in the ledger.
- **Centring (within kingdom)**: subtracting each kingdom's own average from its strains, so every feature reads "more or less than is typical *for this kind of microbe*". The outcome is judged within kind too, so the yardsticks match; this cut DIABLO's error by about a third.
- **`log(1 + x)` transform**: squashes right-skewed chemical abundances so a few huge readings don't dominate; the `1 +` keeps zero at zero.
- **DIABLO**: *Data Integration Analysis for Biomarker discovery using Latent cOmponents*, the supervised integration method of the R package mixOmics. It builds a few summary scores per block that must agree with each other *and* separate the outcome groups, keeping only a short list of features.
- **mixOmics**: the free Bioconductor R package that provides DIABLO and its standard plots.
- **Component**: one summary score DIABLO builds per block, made as a weighted sum of features. Component 1 is the strongest shared story; component 2 the next one, independent of the first.
- **Loading**: the weight a feature gets in a component; its sign says in which direction it pushes and its size how much.
- **Sparse / sparsity**: keeping most weights at exactly zero so only a short, readable list of features remains.
- **`keepX`**: DIABLO's setting for how many features to keep per block and per component. It's *tuned* by cross-validation rather than guessed.
- **Design matrix**: DIABLO's setting for how strongly blocks must agree with each other (0 = not at all, 1 = as much as possible). We use 0.1, which asks for some agreement but puts prediction first.
- **Tuning**: trying several values of a setting and keeping the one that scores best under cross-validation.
- **PLS-DA**: *partial least squares discriminant analysis*, the single-table ancestor of DIABLO; it builds components from all features at once to separate groups.
- **Lasso (L1) logistic regression**: a prediction model that pushes most feature weights to exactly zero, so it selects features as it learns.
- **Cross-validation**: fair scoring by rotation. Split the strains into 5 parts, train on 4, test on the unseen 5th, and rotate until every part has been the test once. It's the old rule of never marking your own homework with the answer sheet open.
- **Repeated (stratified) cross-validation**: doing the 5-part rotation 10 times with different random splits, each keeping the effective/not-effective proportions. This averages out the luck of one particular split and gives an uncertainty (±).
- **Balanced error rate (BER)**: the average of the error on each outcome group. Unlike plain accuracy it can't be gamed by always guessing the common group: that lazy strategy scores 0.50, exactly like a coin.
- **AUC (area under the ROC curve)**: the chance that a randomly chosen effective strain gets a higher score than a randomly chosen non-effective one; 0.5 = coin, 1.0 = perfect ranking.
- **Negative control**: an input that is useless by design and *must* fail (score like a coin). If it doesn't, something is leaking. Ours are the kingdom label alone, and shuffled labels.
- **Y-scrambling (label shuffling)**: randomly re-dealing the outcome labels so any real link is destroyed, then re-running the whole procedure; the score must collapse to chance.
- **Leakage**: information from the test strains sneaking into training, making scores look better than they are. Phase 3 documents a small, label-free one (gap filling and centring use all strains). Phase 4 removed it by moving them inside the cross-validation loop, and measured it as harmless (AUC 0.948 with it, 0.947 without).
- **One-standard-deviation rule**: among settings whose score is within one ± of the best, choose the simplest. In practice it prefers fewer components when more don't clearly help.
- **Cost of sparsity**: how much error a short feature list costs compared with using every feature, expressed in standard deviations so "small" has a meaning.
- **Stability (selection)**: the share of cross-validation re-fits in which a feature is picked again. ≥ 80 % counts as *robust*; a feature that turns up only occasionally is just filling a quota and shouldn't be read as a finding.
- **Signature**: the short list of features a method selects as the explanation of the outcome.
- **Grading against planted truth**: because the data is simulated, we *know* which features truly drive the outcome, so every signature can be marked: how many picks are true drivers (precision) and how many true drivers were found (recall). It's one of the quieter advantages of synthetic data.
- **Decoy**: a feature planted to *look* plausible but carry no signal; a good signature avoids it.
- **Spearman correlation (rho)**: how consistently two columns rise and fall together, using ranks rather than raw values (so skew and outliers throw it less); −1 to +1.
- **Producer pair**: a gene and the compound it helps make (e.g. `ituA` → iturin); in real biology these should correlate, and in our data they do (median rho 0.72).
- **Contract (R ↔ Python)**: the agreed list of hand-off file names and columns two programs exchange; a test checks both sides use the same names, so one can't silently drift.
- **Hand-off file**: a plain CSV one step writes and another reads; the only way R and Python talk in this project.
- **`Rscript`**: the command that runs an R script (or one line, with `-e`) and quits; works the same on every operating system.
- **Installed but invisible**: a package installed on your computer that R *inside this project* can't see, because renv shows only the project's own library. The fix is to install it into the project (`renv::install`).
- **Plotly**: a charting library that makes interactive web charts (hover, zoom). Our interactive pages share one copy of its code, `docs/interactive/plotly.min.js`.

## Phase 4: machine learning (doc 05)

- **Prediction model**: a recipe learned from examples. Shown strains whose outcome is known, it works out a rule that turns measurements into a guess, and it's then judged on strains it has never seen. Compare an estate agent who learned prices from hundreds of sales.
- **Training strains / test strains**: the strains a model learns from, and the sealed ones it's judged on. Cross-validation rotates which is which.
- **Pipeline** *(scikit-learn)*: the chain of steps a model is made of (here: preparation, scaling, learner). Fitting the pipeline fits every step on the training strains only, which is what makes it leak-proof.
- **Out-of-fold prediction**: a strain's prediction from the cross-validation round in which it was a test strain, so it was made by a model that never saw it. For strains we already have, this is the fair number to report.
- **Baseline**: the simplest possible "model" (always say the base rate). Every real model must beat it; one that doesn't has learned nothing.
- **Base rate**: the share of strains that are effective in the data (24 %).
- **Logistic regression**: gives each feature a weight, adds them up, and squeezes the total into a probability with an S-shaped curve, a bit like a judge's scoring sheet.
- **Regularisation**: holding a model back so it can't lean too hard on any single feature or memorise noise. *Lasso* pushes weak weights to exactly zero (it picks features); *ridge* shrinks all of them a little; the *elastic net* mixes both.
- **C**: the elastic net's leash. Small C = held back hard, large C = free to fit closely.
- **Decision tree**: a flow-chart of yes/no questions ("carries fenA?") learned from data, much like the game of twenty questions.
- **Random forest**: many decision trees, each grown on a random sample of strains and features, voting together. Think of the average opinion of 200 people who each saw part of the evidence.
- **Gradient boosting**: small trees built one after another, each concentrating on the mistakes of the ones before (proof-readers in a chain).
- **Class weights**: making each rare-class example count more during training (`class_weight="balanced"`), so the model can't ignore the winners.
- **Threshold**: the probability above which a strain is flagged "effective": 0.5 for the class-weighted models, the base rate for the calibrated one.
- **Nested cross-validation**: tuning a setting (like C) with a small *inner* cross-validation inside each outer training fold, so the test strains never influence the choice. In school terms, you practise on past papers and never on the exam.
- **Accuracy**: the share of predictions that are right. It misleads when one class is rare: "always no" scores 76 % here.
- **Average precision (AP)**: how pure the top of a ranking is, averaged down the list; random ordering scores the base rate (0.24).
- **Brier score**: the average squared distance between the predicted probability and what happened (0 or 1); lower is better.
- **Calibration**: whether probabilities mean what they say. Of the strains called "30 %", about 30 % should be effective, like a weather forecast you can plan by.
- **Reliability diagram**: the picture of calibration, with predicted probability across and the observed share going up; perfect = the diagonal.
- **Calibration error (ECE)**: the average gap between predicted and observed rates over ten probability bins, weighted by how many predictions fall in each; 0 = perfect. It's measured on all out-of-fold predictions pooled, because small groups make it look worse than it is.
- **Platt scaling**: a calibration method that learns a smooth S-shaped correction from the model's raw scores to trustworthy probabilities, on strains the model didn't train on (`CalibratedClassifierCV(method="sigmoid")`).
- **Permutation importance**: shuffle one feature in the test strains and see how much the score drops; a big drop = the model relies on it. Here a feature counts as "reliably important" when the drop is at least 0.002 in AUC and clearly above zero across the five folds.
- **Label-using leak (selection bias)**: choosing features, settings or anything else by looking at the outcome of *all* strains before cross-validating. It manufactures signal even from pure noise (AUC 0.594 on shuffled labels in this project), which makes it the dangerous kind of leak.
- **Error analysis**: studying the strains a model gets wrong, one group and one strain at a time, to learn whether the fault is the model's, the data's or the question's.
- **Top-N hit rate**: of the N best-ranked strains, how many are truly effective (47 of 50 here; 12 expected by chance). It's the number a screening team plans with.
- **Model card**: a short document that travels with a saved model: what it is, its data, its scores and how they were measured, what it's for and not for, and the software versions (`artifacts/model/model_card.json`). It plays the role of the label on a medicine bottle.
- **Pickle / joblib file**: Python's way of saving an object such as a trained model to disk (`.joblib`). Loading one runs code stored inside it, so load only files you built yourself.

## Phase 5: the knowledge graph (doc 06)

- **Graph / network**: things (nodes) and the connections between them (edges). A family tree, a railway map and a social network are all graphs.
- **Node**: one thing in a graph; here a strain, a gene, a compound, a mode of action, an outcome, a kingdom, a genus, or (with the real tables) a KEGG pathway, a RefMet chemical class or a BacDive strain record.
- **Edge**: one connection between two nodes. Ours point one way (STRAIN_0485 *carries* fenA, never the reverse), which makes them *directed* edges, and each has a **relation** name.
- **Relation**: the kind of connection an edge stands for: `belongs_to`, `in_kingdom`, `carries`, `produces`, `makes`, `acts_by`, `contributes_to`, `associated_with`, `in_pathway`, `classified_as`, `subclass_of`. The full list, with what each may connect, is in `src/strainscope/ontology.py`.
- **Ontology**: the agreed list of the kinds of things in a domain and the ways they may connect, written down before any data is loaded (a strain *carries* a gene; a gene *makes* a compound; a pathway can't carry anything). You can think of it as a family tree for concepts. Ours has ten node types and eleven relations.
- **Domain model**: the project's own written-down knowledge of the biology: which gene makes which compound and which mode of action each weapon uses. Here it comes from the descriptions that define the simulated library; on real strains it would come from the literature.
- **Knowledge graph**: the ontology filled in with facts, every edge carrying its source. If the ontology is the family tree's blank template, the knowledge graph is the tree with every name written in.
- **Provenance (on an edge)**: where a connection came from, stored on the edge itself: the synthetic library, the domain model, KEGG, RefMet, BacDive, or Phases 3 and 4. It's what lets anyone trace a claim back to its origin.
- **Mode of action**: *how* a weapon works against a disease: antibiosis, lipopeptide membrane attack, iron competition, cell-wall degradation, mycoparasitism, toxin production, induced plant resistance, killer-toxin antagonism (and, for the plant-growth genes, plant growth promotion).
- **Mechanism vs statistical association**: a mechanism says *how* something works (`acts_by` → `contributes_to`); an association says two things *go together* in the data (`associated_with`, from Phases 3 and 4), with no claim about why. "Smokers get more lung cancer" is an association; "tar damages lung cells" is the mechanism behind it.
- **Knowledge vs data**: the table (`artifacts/graph/knowledge_vs_data.csv`) that sorts every feature by what supports it: both a mechanism and the data, a mechanism only, the data only ("treat with care"), or neither.
- **Degree**: how many edges touch a node.
- **Hub**: a node with unusually many connections. A hub isn't automatically important: here the biggest hubs are housekeeping genes that every strain carries.
- **Path / shortest path**: a walk from one node to another along edges; the shortest path takes the fewest steps. Our path search counts a statistics-only edge as 2.5 steps, so it prefers a route that says *how*.
- **Betweenness**: the share of shortest paths between other nodes that pass through a node, like a railway junction that many journeys go through.
- **Knowledge layer**: every node type except individual strains. Concept analyses run on it so 600 strain nodes don't drown out a few dozen concepts.
- **Co-occurrence**: two features turning up in the same strains.
- **Phi correlation**: an ordinary correlation for yes/no data; 0 means no pattern, 1 means always together. Features are linked for the community search when phi is at least 0.15.
- **Jaccard index**: the share of strains having either feature that have both. Simple, but it favours common features, which is why the community search uses phi instead.
- **Community**: a group of nodes more tightly linked to each other than to the rest of the graph.
- **Louvain method**: a community-finding method that keeps moving nodes between groups as long as that makes the groups more tightly knit inside than between, a bit like rearranging wedding guests so each table is full of people who know each other. It's randomised, so it's run with a fixed seed (42).
- **Purity**: of the members of each community, the share that belong to that community's most common planted group; 1 = every community is "pure".
- **Adjusted Rand index (ARI)**: a score for how closely two groupings of the same items agree: 1 = identical, 0 = no better than chance.
- **Detection threshold ("produces")**: a strain counts as producing a compound when its cleaned level is at least 4 times that compound's median across all strains, so background readings don't count.
- **Measurement spike**: a wildly high reading that doesn't reflect the biology (Phase 1 planted about 1 %). When a compound appears without the gene that makes it, the explanations say it may be a spike or ordinary background noise just over the detection line; in this library both happen.
- **Explanation (of a ranking)**: the walks through the graph behind one strain's rank: up to three mechanism paths (`+`), any data-only flags (`?`) and up to two missing weapons (`-`), each with its sources (`artifacts/graph/explanations.csv`, and `python src/strainscope/graph.py why STRAIN_ID`).
- **NetworkX**: the free Python library the graph is built with; it needs no database and has ready-made functions for paths, centrality and communities.
- **MultiDiGraph**: NetworkX's name for a graph whose edges have a direction and where two nodes may be joined by several edges (one per source, for example).
- **GraphML**: a standard text format for graphs that Gephi and Cytoscape open directly and Neo4j can import with its APOC plugin (`artifacts/graph/knowledge_layer.graphml`).
- **Recursive query (SQL)**: a query that keeps joining a table to its own results, which is how a database walks a graph (`WITH RECURSIVE`, Cookbook §10).
- **Graph database (Neo4j)**: a database built to store and query graphs for many users at once. Deferred until the graph outgrows memory ([roadmap](ROADMAP.md#deferred-items-and-their-triggers)).

## Phase 6: the app (doc 07)

- **Web app**: a program you use through a browser. Ours runs on your own computer: Streamlit starts a small web server, and your browser talks to it.
- **Streamlit**: the Python library that turns a script into a web page. `st.slider(...)` draws a slider, `st.dataframe(...)` a table; there's no HTML or JavaScript to write.
- **Widget**: anything on the page you can click or type into: a slider, a dropdown (Streamlit says *selectbox*), a button, a text box, a file uploader.
- **Rerun**: what Streamlit does on every click: it runs the page's script again from the top with the new values, then redraws the page. It's why the code needs no "when this changes, update that" wiring.
- **Cache** (`st.cache_data`, `st.cache_resource`): a shelf of ready-made results, so slow things (reading a file, loading the graph) happen once instead of on every rerun. Ours are labelled with the file's last-changed time, so a rebuilt file is read again by itself.
- **Session state** (`st.session_state`): a small notebook Streamlit keeps for each browser tab; your upload and the strain you picked survive reruns there, and disappear when the tab closes.
- **Callback**: a small function a button or widget runs *before* the page reruns. It's the one moment Streamlit allows changing another widget's value.
- **Multipage app / navigation**: an app split into pages (ours has eight, in `app/views/`), listed in the sidebar by `st.navigation`.
- **Query parameter**: the part of a web address after `?`, like `?strain=STRAIN_0485`. The Strain page reads and writes it, so a link opens on a chosen strain.
- **Service layer**: a thin set of functions between the screens and the real work (`src/strainscope/service.py`), so the terminal, the app and later tools ask the same questions in the same way. In a restaurant it's the *pass*, the counter between kitchen and dining room.
- **localhost** and **port**: *localhost* means "this computer"; a *port* is a numbered door on it. The app listens at `http://localhost:8501`.
- **Headless**: running a program without opening a window or a browser, as on a server or a VM with no screen (`--server.headless true`).
- **Virtual machine (VM)**: a computer simulated by software on a bigger computer. It behaves like a separate machine with its own address and is often used without a screen.
- **SSH (secure shell)**: a program that opens an encrypted terminal on another computer (`ssh your-user@your-vm`); the commands you type then run there.
- **Docstring**: the block of plain text in triple quotes at the top of a Python file or function, written for the person reading the code.
- **SSH tunnel**: a private corridor through an SSH connection: `ssh -L 8501:localhost:8501 user@vm` makes the VM's port 8501 appear on your laptop's port 8501, without opening anything on the VM.
- **Firewall / opening a port**: the firewall decides which doors of a computer the network may knock on; `sudo firewall-cmd --add-port=8501/tcp` opens one on RHEL 8.
- **Read-only guard**: the database is opened so it can be read but never changed (CREATE, INSERT, UPDATE, DELETE are refused).
- **External access (switched off)**: DuckDB's setting that lets a query read or write files and the internet; the console turns it off and locks the setting.
- **Timeout**: a time limit after which a running query is stopped (10 seconds in the console).
- **Upload validation**: checking somebody else's file before using it, and saying in plain words which column and which row are wrong. *Errors* stop the scoring, *warnings* say what was assumed, *notes* are for information.
- **Template**: an empty file with the right column names, to fill in (`python src/strainscope/service.py template FILE.csv`).
- **Out-of-fold vs final model**: the library's ranking comes from models that never saw each strain (out-of-fold, a fair test). A new strain is scored by the final model, which learned from all 600. A copy of a library strain therefore gets a slightly different number as an upload.
- **Borderline (likely / borderline / unlikely)**: the bands next to every predicted chance: above 70 % likely, 30 % to 70 % borderline, below 30 % unlikely. "Effective" means suppressing disease by at least 65 % in the trial, and strains just either side of that line are much alike, so for a middling chance the app says *borderline* instead of a confident yes or no.
- **Health check**: a list of what the app needs and whether it's there, with the fix for anything missing (`python src/strainscope/service.py status`, the app's Home page, and since Phase 7 its *About this copy* page).
- **Shared mode** (`STRAINSCOPE_MODE=public`): an environment variable for an app other people can reach. It hides the real-data buttons and allows the database build only while there's no database yet (a first start). Since Phase 7 it also builds the database by itself on that first start, gives visitors messages they can act on, and caps the AI features' requests to a language model per day.
- **AppTest**: Streamlit's test runner; it plays the app the way a browser would, in memory, so the tests can open pages, press buttons and read what was drawn (`tests/test_app.py`).
- **Playwright**: a library that drives a real browser from Python; only the optional screenshot script uses it (`figures/take_app_screenshots.py`).
- **`tmux`**: a terminal program that keeps a command running after you log out of a remote machine.

## Phase 6b: Ask StrainScope (doc 07b)

- **Ask StrainScope**: the project's documentation assistant (`python src/strainscope/ask.py "..."`, and a page in the app). It answers from the project's own documents with the matching passage, word for word, and a link to it, and refuses questions the documents don't cover.
- **Search index**: what a search engine builds before anyone asks anything, like the index at the back of a book: for every passage, which words it contains and how much each one counts. Ours is built in memory in a second or two and rebuilt when a document changes.
- **Section** and **passage**: a section is a document's text under one heading (or one glossary entry, or one docstring), which is what a link points at; a passage is about 120 words of it, which is what the search compares. A long section is found by its best passage.
- **TF-IDF (term frequency, inverse document frequency)**: a way of weighing words. A word counts more the more often it appears in a passage, and less the more passages it appears in. If every recipe mentions salt, "salt" won't find you the risotto; "saffron" will.
- **Stop words**: little words that appear everywhere ("the", "is", "how") and are dropped before searching. Ask StrainScope also drops *filler* words that say what kind of question it is rather than what it's about ("explain", "does", "StrainScope").
- **Word forms**: "strains", "scoring" and "ranked" are matched as "strain", "score" and "rank", but only when the shorter form really appears in the documents.
- **Cosine similarity (match)**: a score from 0 (no words in common) to 1 (the same words in the same proportions) between a question and a passage. It compares what two texts are mostly about, whatever their length, the way two shopping lists can match well even if one is much longer.
- **The gate**: the four checks every question to Ask StrainScope passes before anything is shown (an instruction? words no document uses? a weak match? a good match with most of the words found?). They decide whether a question is answered, shown as *closest* or refused. Ask the data and Ask the graph (Phase 7) have gates of the same kind.
- **Out-of-scope refusal**: Ask StrainScope's polite "the documents don't cover this", given instead of a guess. It happens before any language model could be involved, so nothing can be invented.
- **Closest**: the verdict for a question the documents touch on but don't answer directly: the nearest sections are shown, marked as such, with the question's words that none of them use.
- **Golden question set**: a fixed list of questions with known right answers, off-topic questions that must be refused and undocumented ones that must not get a confident answer (`tests/golden_questions.csv`), run with the tests on every change. A driving test route for the assistant.
- **Known limitation** (in the golden set): a question the search is known to get wrong, kept in the set and reported on every run instead of being dropped, so it's visible and so an improvement shows up at once.
- **Language model (LLM)**: a program trained on large amounts of text to write fluent text. In StrainScope it's optional and only ever writes from passages it's given.
- **Hallucination**: a fluent, confident answer that isn't true, given by a language model that doesn't know but answers anyway. Searching first, sending only the passages found and requiring citations reduces the risk; keeping the passages on screen lets you check.
- **RAG (retrieval-augmented generation)**: find the relevant passages first, then let a language model answer *only from them*, citing them. It's an open-book exam with the page numbers written down.
- **Strong match** (for written answers): a passage whose match is at least three quarters of the best passage's. Since Handbook Stage 12.1 only strong matches go to a language model, so a passage that shares just a word or two with the question can't steer the written answer.
- **Grounded answer / citation**: an answer built only from the passages supplied, which names the passage behind each statement ([1], [2]). An answer that cites nothing is not shown.
- **Prompt** and **system prompt**: the text sent to a language model; the system prompt is the fixed part that sets the rules ("answer only from these sections, cite them").
- **Prompt injection**: text that tries to give a language model new orders ("ignore your instructions and..."), like a note slipped into a pile of forms telling the clerk to skip the checks. Ask StrainScope refuses questions that look like one.
- **Ollama**: free software that runs open language models on your own computer (Windows, macOS, Linux), so nothing leaves it. `ollama pull llama3.2:3b` downloads a small model.
- **OpenAI-compatible interface**: a common way of asking a language model for an answer over the web (send the messages to an address ending in `/chat/completions`, get the answer back). Ollama and many hosted providers offer it, so one piece of code reaches all of them.
- **Backend (for written answers)**: where a written answer comes from, set with `STRAINSCOPE_ASK_BACKEND`: `none` (the default: search only), `local` (Ollama on this computer) or `hosted` (a provider, with the key in `.env`). Since Phase 7 the same setting serves all three assistants.
- **Temperature**: a language model setting for how adventurous its wording is; 0 asks for its most likely wording every time. Ask StrainScope uses 0.
- **Stand-in server**: a tiny web server that a test starts on your own computer to play the part of the real service (an understudy), so the written answers can be tested without a model, a key or the internet.
- **grep**: the classic command that prints every line containing some text (`git grep -n "text"` is Git's version, the same on every system). Exact and complete, but not ranked.

## Phase 7: deployment and the AI layer (doc 08)

### Putting the app online

- **Deploying (deployment)**: running the app on a computer that is on all day and reachable from the internet, so anyone with the link can use it.
- **Hosting / host**: the service that provides that computer and runs your app on it, rather like a landlord who provides the shop, the power and the opening hours while you run the business.
- **Streamlit Community Cloud**: a free host for Streamlit apps. It builds the app from a GitHub repository, gives it an address on `streamlit.app` and updates it on every push.
- **App address (subdomain)**: the first part of the online copy's address (`<a-name>.streamlit.app`), chosen when the app is created. StrainScope's is `strainscope.streamlit.app`.
- **Entry point (main file path)**: the file a host runs to start the app: `app/streamlit_app.py`.
- **Redeploy**: the host installing and starting the app again, which Community Cloud does by itself after every push to the branch it watches.
- **Sleeping app**: an online app with no visitors for 12 hours is paused; the next visitor wakes it with a button, and it may start again from a fresh copy of the repository.
- **First start**: the first time a shared copy runs without a database. It builds one from the committed results (about 15 seconds), once per running copy.
- **Shared copy / local copy**: a copy of the app other people use (shared mode on, as online) or one on your own computer (every button available). *About this copy* says which one you're looking at.
- **About this copy**: the app's health page: the version, the mode, what each page can read, whether the AI features use a model, what may leave the copy, and the package versions.
- **Pinning (an exact version)**: writing `scikit-learn==1.9.0` instead of `scikit-learn`, so an install gives the same version every time (ordering a part by its catalogue number instead of asking for "a bolt that fits").
- **Dependency file (packing list)**: the file a host installs packages from. StrainScope has two: `requirements.txt` (your computer, current versions) and `app/requirements.txt` (the online copy, exact versions; Community Cloud reads the one next to the entry point first).
- **Secrets box (a host's secret store)**: where a host keeps settings and keys that must not be in Git. Community Cloud's is in the app's *Settings*; Streamlit puts its top-level lines into the app's environment.
- **TOML**: a plain settings format, one `NAME = "value"` per line (and `[section]` headings, which StrainScope doesn't use). The Secrets box is written in it; the template is `.streamlit/secrets.toml.example`.
- **Reboot (an app)**: stopping and starting the online copy from its *Manage app* menu, for example after changing its secrets.
- **Daily cap**: the most requests a running copy may send to a language model in one day (200 in shared mode unless `STRAINSCOPE_AI_DAILY_LIMIT` says otherwise). Once it's used up, the assistants still answer with what they found, without a written version, until the count starts again the next day (UTC).
- **Free tier**: a provider's free allowance, with its own limits. A free tier may use what you send to improve the provider's products, which is one reason StrainScope never sends a row of data or anything about a strain.
- **GitHub Pages**: GitHub's free hosting for a folder of plain web pages; StrainScope can publish `docs/` with it, so the interactive figures open with one click.
- **Static site** and **`.nojekyll`**: a static site is a set of files served as they are, with no program running behind them. GitHub Pages normally passes them through a page builder called Jekyll; an empty `docs/.nojekyll` file switches it off.

### The AI layer

- **Ask the data (data assistant)**: the app page and command (`python src/strainscope/ask_data.py "..."`) that answer a question about the data with a SQL query you can see and the table it returns.
- **Text-to-SQL**: turning a question in words into a SQL query. In StrainScope a tested recipe comes first, and a language model writes a new query only when no recipe fits.
- **Recipe (Query Cookbook)**: a tested SQL query in [`docs/QUERY_COOKBOOK.md`](QUERY_COOKBOOK.md), under the plain-English question it answers. Ask the data finds the recipe whose question matches yours.
- **Schema**: the names of a database's tables and columns (not what's in them). It's all a model is shown of the database.
- **The fifth guard**: the check a model's query passes before the SQL console's four guards: one statement, starting with `SELECT` or `WITH`, with no command that changes anything and no function that reads files.
- **Ask the graph**: the app page and command (`python src/strainscope/ask_graph.py "..."`) that answer how things connect by walking the knowledge graph.
- **GraphRAG**: retrieval-augmented generation where the retrieved material is facts read off a graph (each one an edge, with its source) rather than passages of text. The answer carries its own route.
- **Entity linking (finding names)**: spotting which things in the graph a question mentions ("iturin", "iron competition", "STRAIN_0485"), so the right walks can be taken.
- **Alias**: an everyday name the graph doesn't use itself ("hydrogen cyanide" for HCN); Ask the graph knows a few.
- **Fact (numbered)**: one step of a walk read aloud ("iturin works by lipopeptide membrane attack") with the source the edge records. A written answer must cite the facts by number.
- **Walking order**: the order a route visits its steps. A walk can cross an edge against its direction (ituA and fenA both work by the same mode of action), and a drawing of the route shows that step with an arrow pointing back.
- **Coverage**: the share of a question's words that the material found also uses; too little, and the answer is shown as *closest* instead.
- **Number check**: Ask the graph drops a written answer that contains a number none of its facts holds; a model rephrasing facts has no reason to add one.
- **Few-shot prompting (worked example)**: putting one or more finished examples of the task into the request, before the real question, so the model copies the form of the answer (a recipe with a photo of the finished dish is easier to follow than one without). StrainScope's request for a written answer has one: a question about a made-up pump and an answer that cites it with [2] and [1]. In the test of [`docs/LANGUAGE_MODEL.md` §9](LANGUAGE_MODEL.md#9-how-a-written-answer-is-asked-for-and-checked) it wasn't what made a small model (llama3.2:3b) cite, since an example sentence in the rule did that, but it gave the shortest answers.
- **Model check**: `python src/strainscope/service.py check-model`, which asks the switched-on language model four questions through Ask the graph and Ask StrainScope and says how many of its written answers would be shown. Worth running after switching to another model or provider.
- **Plain words (template text)**: a short paragraph written by rules from computed results, with no language model, so every number in it can be traced to a file (`src/strainscope/narrate.py`).
- **Suggest a fix**: the link under every answer in the app that opens a new GitHub issue with the question filled in. Nothing is sent unless you press Submit on GitHub, and issues there are public.

## Phase 7b: the MCP server (doc 08b)

- **MCP (Model Context Protocol)**: an open standard through which AI assistant apps use other programs' tools in one agreed way, so a program written once works with every app that speaks it (one plug standard, many appliances).
- **MCP server**: a program that offers tools through MCP. StrainScope's is `src/strainscope/mcp_server.py`, with nine read-only tools.
- **Assistant app (host)** and **MCP client**: the app you chat with (Claude Desktop, Claude Code and many others) is the host; the part of it that starts servers and talks to them is the client.
- **Claude Desktop** / **Claude Code**: two assistant apps that speak MCP: a desktop chat app for macOS and Windows, and an assistant that works in a terminal on macOS, Windows and Linux. Claude Desktop reads its servers from a settings file, `claude_desktop_config.json`; Claude Code adds them with `claude mcp add`.
- **Tool (MCP)**: one function a server offers, with a name, a description in words and an input schema. The app's model reads the descriptions to decide which tool to call, with which inputs. `rank_strain(strain_id)` is one.
- **Input schema**: the machine-readable list of a tool's inputs: their names, their kinds (text, whole number) and which ones may be left out. The MCP package builds it from the Python function's inputs (`n: int = 50` becomes "a whole number, 50 if not given").
- **Tool annotations**: labels a server puts on each tool, such as *read-only* or *destructive*. Apps can use them to decide whether to ask you before a call. StrainScope marks all nine tools read-only and not destructive.
- **Refusal (tool error)**: what a tool sends back instead of a result when an input isn't acceptable: one sentence saying why ("There's no STRAIN_0601 in the library ..."), marked as an error, so the app's model can correct itself.
- **stdio (standard input, standard output, standard error)**: the three channels every terminal program has: one it reads from, one for its results and one for notes and errors (stdin, stdout, stderr). An app talks to a local MCP server through the first two, which is why a server must never `print` to stdout; StrainScope's notes go to stderr.
- **Transport**: how MCP messages travel. **stdio** is for a server on the same computer, started by the app; **streamable HTTP** is for a server other people reach over the internet (a deferred item in the roadmap).
- **JSON-RPC**: the small message format MCP uses: a JSON object that names a function and its inputs ("call `rank_strain` with `strain_id` STRAIN_0485"), and a JSON object that carries the result back.
- **Handshake (protocol version)**: the first exchange between client and server, in which they agree which version of the protocol to speak (dated versions, such as `2025-11-25`) and the server introduces itself and its tools.
- **Call log**: `data/processed/mcp_calls.log`, one JSON line per tool call (the time, the tool, its inputs, the outcome and how long it took), never the result. Git never commits it.
- **UTC (`+00:00`)**: Coordinated Universal Time, the world's reference clock, which ignores time zones and summer time. The call log writes times in UTC, because an app starts the server without your time zone setting.
- **MCP Inspector**: the MCP project's own web page for trying a server by hand: list its tools, fill in inputs, see the raw results. Optional; it runs with Node.js.
- **Node.js** and **npx**: a program that runs JavaScript outside a browser, and its command for running a published tool without installing it first (`npx @modelcontextprotocol/inspector ...`). StrainScope needs neither, except for the optional Inspector.
- **Absolute path**: a file's full address from the top of the computer (`/Users/<you>/projects/strainscope/.venv/bin/python`, or `C:\Users\<you>\...` on Windows), as opposed to a path relative to the folder you're in. Assistant apps need absolute paths, because they start the server from their own folder.

## Phase 8: packaging and release 1.0 (doc 09)

### Rebuilding and checking
- **Pipeline**: steps that always run in the same order, each one reading what the one before it wrote. `python src/strainscope/pipeline.py` runs the scripts of Phases 1 to 5 that way, in one command.
- **Plan (of the pipeline)**: one named list of steps: `everything` (recompute every result), `database` (load the committed results, about 15 seconds), `real` (fetch real data, then rebuild) and `probe`. The app's buttons run the same lists.
- **Reproducible**: the same inputs and the same code give the same results on any computer. A stranger following the recipe in another kitchen gets the same cake.
- **`compare`**: `python src/strainscope/pipeline.py compare`, which checks every number in the result files (`artifacts/`) against the version in Git's last commit, and lists what it leaves out and why.
- **Tolerance**: how far apart two numbers may be and still count as the same. `compare` uses 0.001, because a different processor or package version can move the fourth decimal.
- **Tie (in a ranking)**: two strains with the same chance. Since Phase 8 they're ordered by strain id, so the ranking is the same on every computer.
- **Exit code**: the number a program hands back when it ends; 0 means it went well. The pipeline returns 0, 1 (a step failed, or a result differs) or 130 (stopped with Ctrl+C), so other programs, such as CI, can tell what happened.

### Tests on every push
- **Continuous integration (CI)**: a service (here GitHub Actions) that runs the tests on fresh machines every time a change reaches GitHub, so a problem that only shows up on one system is found the day it appears.
- **GitHub Actions** and the **Actions tab**: GitHub's CI service, and the page of the repository that shows every run, its jobs and their logs.
- **Workflow**: a file in `.github/workflows/` that lists the jobs to run and when. StrainScope's is `.github/workflows/ci.yml`, named *tests*.
- **Job**: one machine doing one list of steps in a workflow; jobs run side by side.
- **Runner**: the machine GitHub lends for a job (Linux, Windows or macOS), wiped afterwards.
- **Matrix**: one job run several times with different settings, here every combination of three systems and two Python versions.
- **Green tick / red cross**: GitHub's marks next to a commit: every job passed, or at least one failed (its log says where).
- **UBI (Universal Base Image)**: Red Hat's free container images of its own system. The *rhel8* job runs inside `ubi8/python-312`, which is RHEL 8 with Python 3.12, because GitHub has no RHEL machines.
- **pyflakes**: a small checker that reads Python files and reports mistakes such as unused imports or misspelt names, without running them.

### Containers
- **Container**: a sealed box holding a program and everything it needs (a small Linux system, Python, the packages), which runs the same on Windows, macOS and Linux; the shipping container did the same for cargo.
- **Image**: the sealed box itself, built once from the recipe and then started as often as you like.
- **Dockerfile**: the recipe for an image: start from this, install that, copy these files, run this command. StrainScope's is `Dockerfile` in the project folder; `.dockerignore` lists what stays out.
- **Docker** and **Podman**: two programs that build and run containers from the same Dockerfile. Docker Desktop runs on Windows and macOS; RHEL 8 comes with Podman.
- **Port mapping** (`-p 8501:8501`): connecting a port inside the box to a port on your computer, so `localhost:8501` reaches the app inside.
- **Registry**: an online store of images (Docker Hub, Red Hat's registry) from which `docker build` downloads its starting image.

### Reuse and contributions
- **Licence**: the text that says what others may do with a work. StrainScope's is the **MIT licence** (`LICENSE`): anyone may use, copy, change and share it, also commercially, if the licence text travels with it; there's no warranty.
- **Citation File Format** (`CITATION.cff`): a small file saying how to cite a project; GitHub turns it into a **Cite this repository** button.
- **Contribution guide** (`CONTRIBUTING.md`): how a change travels from an idea to a release, and what it must pass.
- **Security policy** (`SECURITY.md`): how to report a security problem privately, before it becomes public.
- **Private vulnerability reporting**: GitHub's way for someone to report a security problem that only the maintainer sees (*Security*, *Advisories*, *Report a vulnerability*).
- **Issue form**: a short form GitHub shows when someone opens a new issue, from a file in `.github/ISSUE_TEMPLATE/`.
- **Fork**: your own copy of someone else's repository on GitHub, where you can change things and then propose them back with a pull request.
- **Dependabot**: GitHub's helper that watches the packages a project uses: **alerts** for versions with a known security problem, and **version updates**, pull requests with newer versions (`.github/dependabot.yml`).

### Accessibility
- **Accessibility**: whether people with different abilities can use something: without a mouse, without seeing the screen, with low vision, and so on.
- **WCAG** (Web Content Accessibility Guidelines): the international guidelines for accessible web pages; level **AA** is the usual target, and it asks, for example, for a contrast of at least 4.5 to 1 for small text.
- **Contrast ratio**: how much lighter the background is than the text, from 1 to 1 (the same colour) to 21 to 1 (black on white).
- **Screen reader**: a program that reads the screen aloud and lets you move through a page with keys: VoiceOver on a Mac, NVDA or Narrator on Windows, Orca on Linux.
- **Focus**: the one control that receives what you type; the Tab key moves it to the next one. A **focus indicator** (usually an outline) shows where it is.
- **Keyboard trap**: a place on a page the focus can enter but not leave with the keyboard.
- **Accessibility tree**: the browser's list of what's on a page (headings, paragraphs, buttons, fields) with their names, which is what a screen reader reads.
- **Alt text**: the description of a picture that a screen reader reads instead of it.
- **axe-core**: an open-source engine of accessibility rules that most checkers use; `tools/check_accessibility.py` runs it on every page of the app.
- **Playwright**: a library that drives a real browser from a program; the screenshots and the accessibility check use it.
- **Landmark**: a region of a page a screen reader can jump to (the main part, the navigation, ...).

### Releases
- **Git hook**: a small script Git runs by itself at a certain moment. `.githooks/pre-push` runs the safety gate before every push, once switched on with `git config core.hooksPath .githooks`.
- **Release (GitHub)**: a page built on a tag, with the version's notes and a download of the code as it was.
- **Patch release**: a version that only fixes something (the third number: v1.0.1).
- **Uninstall guide**: [`docs/UNINSTALL.md`](UNINSTALL.md), every place StrainScope can leave something behind, and how to remove it in a safe order.

## The Handbook, releases and the roadmaps (docs HANDBOOK, ROADMAP, PRODUCT_ROADMAP)

- **Handbook**: [`docs/HANDBOOK.md`](HANDBOOK.md), the one living document that walks the whole journey from a blank laptop to the finished product and links every specialised guide. Read it first; it's updated in the same commit as every change. [`docs/interactive/journey.html`](interactive/journey.html) is the same journey as a clickable page, built from the Handbook.
- **Roadmap**: the ordered plan of what gets built next and why ([`docs/ROADMAP.md`](ROADMAP.md)); the **product roadmap** looks beyond this repository ([`docs/PRODUCT_ROADMAP.md`](PRODUCT_ROADMAP.md)).
- **Verdict / trigger**: in the product roadmap, every technology gets a verdict (*required now · recommended later · optional · not needed*) and a trigger, which is the observable event that would change it. The idea is to justify each tool instead of piling them up.
- **Tag (Git)**: a bookmark on one exact commit, named with a version number (`v0.1.0`), so anyone can return to that state. *Annotated* tags (`git tag -a`) also record who, when and why.
- **Semantic versioning**: version numbers as `MAJOR.MINOR.PATCH`: MINOR for a new usable level, PATCH for fixes, MAJOR 1 for the first complete release (v1.0.0, Phase 8); after 1.0, a new MAJOR number means something you rely on stopped working the old way.
- **Changelog**: [`CHANGELOG.md`](../CHANGELOG.md), the human-readable list of what changed in each version.

