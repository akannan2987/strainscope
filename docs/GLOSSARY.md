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
- **Synthetic (simulated) data**: data created by a program rather than measured in a lab. It's an honest and useful option when real data is private, rare, or unavailable; you could call it a flight simulator for the workflow.
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

## The Handbook, releases and the planned phases (docs HANDBOOK, ROADMAP, PRODUCT_ROADMAP)

- **Handbook**: [`docs/HANDBOOK.md`](HANDBOOK.md), the one living document that walks the whole journey from a blank laptop to the finished product and links every specialised guide. Read it first; it's updated in the same commit as every change.
- **Roadmap**: the ordered plan of what gets built next and why ([`docs/ROADMAP.md`](ROADMAP.md)); the **product roadmap** looks beyond this repository ([`docs/PRODUCT_ROADMAP.md`](PRODUCT_ROADMAP.md)).
- **Verdict / trigger**: in the product roadmap, every technology gets a verdict (*required now · recommended later · optional · not needed*) and a trigger, which is the observable event that would change it. The idea is to justify each tool instead of piling them up.
- **Tag (Git)**: a bookmark on one exact commit, named with a version number (`v0.1.0`), so anyone can return to that state. *Annotated* tags (`git tag -a`) also record who, when and why.
- **Semantic versioning**: version numbers as `MAJOR.MINOR.PATCH`: MINOR for a new usable level, PATCH for fixes, MAJOR 1 for the first complete release.
- **Changelog**: [`CHANGELOG.md`](../CHANGELOG.md), the human-readable list of what changed in each version.
- **Ontology** *(Phase 5)*: the agreed rules of what kinds of things exist in a domain and how they may connect (a strain *carries* a gene, a gene *helps make* a compound). You can think of it as a family tree for concepts.
- **Knowledge graph** *(Phase 5)*: the filled-in family tree, with actual strains, genes, compounds and pathways as dots (nodes) joined by labelled lines (edges) you can walk.
- **Hub**: a node with unusually many connections; often a central gene or compound.
- **RAG (retrieval-augmented generation)** *(Phase 6b to 7)*: find the relevant passages first, then let a language model write an answer *only from them*, citing them. It's an open-book exam with the page numbers written down.
- **Ask StrainScope** *(Phase 6b)*: the project's documentation assistant. It answers from the project's own documents with links, and refuses questions that aren't about StrainScope.
- **Out-of-scope refusal**: the assistant's polite "that isn't about this project" when even the best-matching passage matches weakly. It happens *before* any language model is called, so nothing can be invented.
- **Golden question set**: a fixed list of questions with known right answers (and off-topic questions that must be refused), run with the tests on every change.
- **Language model (LLM)**: a program trained on large amounts of text that writes fluent text. Here it's optional and only ever rephrases supplied facts or passages.
- **Ollama**: free software that runs open language models on your own computer (Windows, macOS, Linux), so nothing leaves the laptop.
- **Text-to-SQL / data assistant** *(Phase 7)*: turning a question in plain words into a SQL query, run read-only, with the query shown so it can be checked.
- **GraphRAG** *(Phase 7)*: RAG where the "passages" are paths walked through the knowledge graph, cited as the route taken.
- **MCP (Model Context Protocol)** *(Phase 7b)*: an open standard that lets AI assistants call a program's tools in a uniform way (a USB port for AI assistants, more or less).
- **Continuous integration (CI)** *(Phase 8)*: a service (here GitHub Actions) that runs the tests automatically on fresh Windows, macOS and Linux machines at every push.
- **Container** *(Phase 8, optional)*: a sealed, portable box holding a program plus everything it needs to run (Python, R, packages), so it runs the same anywhere.

