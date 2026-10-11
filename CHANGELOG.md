# Changelog

All notable changes to StrainScope are recorded here, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/), where version numbers look like `MAJOR.MINOR.PATCH`. A new MINOR version marks a new usable level of the project (see the tags in [`docs/ROADMAP.md`](docs/ROADMAP.md#version-tags)), a PATCH marks a fix or a documentation improvement, and 1.0.0 marks the first complete release.

Each step is explained in [`docs/HANDBOOK.md`](docs/HANDBOOK.md), the day-0-to-product guide that links to every phase guide.

## [Unreleased]

Nothing yet. Next up: Phase 6, the app ([`docs/ROADMAP.md`](docs/ROADMAP.md)).

## [0.2.0] - 2026-10-11: the analysis is complete

Phases 4 and 5, released together: the data is now cleaned, integrated, predicted and explained ([why this tag](docs/ROADMAP.md#version-tags)).

### Added
- **Phase 5: the knowledge graph** ([`docs/06-knowledge-graph.md`](docs/06-knowledge-graph.md)).
  - `src/strainscope/ontology.py`: the domain model written before any data is loaded: ten node types (Kingdom, Genus, Strain, Gene, Compound, ModeOfAction, Outcome, and with the real tables Pathway, ChemicalClass, ReferenceStrain), eleven relations with the node types each may join, a mode of action for every weapon in the library, and an edge checker.
  - `src/strainscope/graph.py` with the verbs `build`, `analyse`, `explain`, `publish` and `all`, plus the questions `why`, `path` and `show`. The graph (679 nodes and 8,096 edges without the real tables) is built from the clean tables, the domain model, the real KEGG / RefMet / BacDive / NCBI tables when present and the results of Phases 3 and 4; every edge is checked against the ontology and records its source. "Produces" means at least 4 times a compound's median level. Mechanisms (`acts_by`) and statistical associations (`associated_with`) are kept apart. Hubs and betweenness; communities of co-occurring features (phi >= 0.15, Louvain, seed 42) graded against the planted arsenals (purity 0.94, adjusted Rand index 0.93); a knowledge-vs-data table (30 features confirmed by both, `accE` flagged as "statistics only"). An explanation for every strain: mechanism paths, data-only flags, missing weapons, and compounds measured without their gene (possible spikes or missing calls). Path searches prefer a mechanism to a statistics-only shortcut. Results in `artifacts/graph/` (two plain tables for the graph, a GraphML copy of the knowledge layer, hubs, communities, explanations) and eleven `kg_*` tables in the database.
  - `tests/test_graph.py`: 12 tests, with and without stand-ins for the real tables (61 tests in total).
  - `figures/make_phase5_figures.py`: three concept figures (graph vocabulary on a toy network, a table vs a graph, the ontology map drawn from `src/strainscope/ontology.py`), six result figures (the mechanism map, hubs, communities, knowledge vs data, two strains explained, and the real context when the real tables are present) and the interactive `docs/interactive/graph_explorer.html`.
  - `docs/QUERY_COOKBOOK.md` section 10 (including a graph walk as a recursive SQL query); `docs/GLOSSARY.md` Phase 5 terms.
- **Phase 4: machine learning, measured carefully** ([`docs/05-machine-learning.md`](docs/05-machine-learning.md)).
  - `src/strainscope/model.py` with the verbs `compare`, `calibrate`, `explain`, `final`, `publish` and `all`. `KingdomPrep` turns Phase 3's preparation rules into a scikit-learn step re-learned inside every fold (no leakage; handles gaps and unseen kingdoms; never reads the outcome). Four models on the same 5 x 10 folds (a baseline, an elastic net tuned by nested cross-validation, a random forest, gradient boosting), plus a shuffled-label control; scores: balanced error at 0.5 and at the base rate, AUC, average precision, Brier score, accuracy. A leak check (Phase 3's label-free leak: harmless; a label-using leak on noise: AUC 0.594). The one-SD rule picks the winner (the elastic net, balanced error 0.128 +/- 0.007, AUC 0.948). Platt-scaling calibration (pooled calibration error 0.081 -> 0.033). Permutation importance judged across folds with a minimum effect, graded against the planted truth (22 of 23 true drivers) and compared with DIABLO. Error analysis by kingdom, distance from the 65 % cut-off and missing readings; the hard strains listed. The calibrated winner saved (`artifacts/model/strainscope_model.joblib`, under 20 KB) with a model card (`artifacts/model/model_card.json`); `load_model()` warns on a scikit-learn version mismatch; `score_strains()` scores new strains. The out-of-fold ranking (`artifacts/model/predictions.csv`): 47 of the top 50 are truly effective (chance: 12). Fourteen `ml_*` tables in the database.
  - `tests/test_model.py`: 12 tests, including the whole chain end to end on 90 hand-made strains and a regression test for the saved model's module name (49 tests in total).
  - `figures/make_phase4_figures.py`: three concept figures (a 100-strain pictograph of class imbalance, leaky vs leak-proof preparation, calibration the weather-forecast way), six result figures and the interactive `docs/interactive/model_explorer.html`.
  - `docs/QUERY_COOKBOOK.md` section 9; `docs/GLOSSARY.md` Phase 4 terms.

### Changed
- `docs/HANDBOOK.md` Stages 8 and 9 done (version 1.4), `docs/ROADMAP.md`, `README.md`, `docs/00-architecture.md`, `docs/PRODUCT_ROADMAP.md`, `docs/04-integration.md`, `docs/05-machine-learning.md` and the journey map (`figures/make_illustrations.py`, `docs/img/journey_map.svg`): Phases 4 and 5 complete, v0.2.0 released, Phase 6 next.
- The roadmaps: the MCP server (Phase 7b) gains an `explain_strain` tool built on Phase 5's explanations; external ontologies and graph machine learning are recorded as deferred items with their triggers; the product roadmap notes what Phase 5 already prepares for explanations (C1), GraphRAG (C3) and ontologies (C5).
- `docs/05-machine-learning.md` §13: a note on the harmless joblib `DeprecationWarning` seen with newer NumPy versions.
- A style pass over every guide, the README, this changelog, code comments, printed messages and figure text. The writing is plainer, uses straight punctuation (no long dashes, no curly quotes) and repeats itself less. Headings that changed have their links updated. Program output in the guides matches the new messages, and no numbers or results changed.
- `src/strainscope/sources/base.py`: shorter User-Agent text (`StrainScope/1.0 (educational multi-omics project)`).
- `src/strainscope/generate_data.py`: the ledger line `strains (samples) ......` was missing its closing bracket.
- `check-public-safe.sh`: warning lines start with `!` and messages use plain punctuation; the checks themselves are unchanged.

## [0.1.1] - 2026-10-10: a safer safety gate, copy-safe commands

A fix release for two problems found while releasing v0.1.0. Both are fixed, tested and documented ([Handbook Stage 7.1](docs/HANDBOOK.md#stage-71-fix-release-v011-a-safer-safety-gate-and-copy-safe-commands)).

### Fixed
- `check-public-safe.sh` now checks every file a commit could publish: the files Git already tracks **and** the new, not-ignored files that `git add -A` is about to add. The documented routine runs the gate before `git add -A`, so the old gate never checked a brand-new file on its first commit. A first attempt (`git grep --untracked`) turned out to skip force-added ignored files; the gate now runs two searches and merges them. It also prints how many tracked and new files it read.
- Every command, commit message and tag message in the documentation uses plain keyboard characters only. A tag message pasted with a long dash (&mdash;) had arrived in Git garbled; the documented `v0.1.0` tag message now matches the corrected one (`v0.1.0: data foundation and multi-omics integration`).

### Added
- `tests/test_safety_gate.py`: five tests that run the gate in throw-away Git repositories (clean; new file with a key; ignored `.env`; force-added ignored file; link anchor without false alarm). One fails on the old gate. 37 tests in total; the gate tests are skipped on Windows, where the gate runs from Git Bash.
- `docs/01-setup.md` Part H: a diagram of the three kinds of files (tracked, new, ignored) and which ones the gate reads; *Notes from the build* for the gate; a new section *Copy commands safely: plain keyboard characters only*, with a table of look-alike characters.
- `docs/04-integration.md` §17: how to check a tag message (`git tag -n1`) and replace a garbled one.
- `docs/HANDBOOK.md`: Stage 7.1 (this release, with a before/after diagram), a copy-safety note in Stage 2, and three new rows in *When something goes wrong*.
- `docs/GLOSSARY.md`: tracked / new (untracked) / ignored file, staging, force-add, plain keyboard characters (ASCII), regression test, patch release.

### Changed
- `docs/ROADMAP.md`: the fix release in the phase plan; patch releases explained under *Version tags*; Phase 8 gains an optional pre-push hook so the gate runs by itself.
- `README.md`, `docs/PRODUCT_ROADMAP.md`: version and test counts.

## [0.1.0] - 2026-10-09: data foundation and integration

From a blank laptop to a graded multi-omics signature (Phases 0 to 3).

### Added
- **Phase 3: multi-omics integration** ([`docs/04-integration.md`](docs/04-integration.md)).
  - `src/strainscope/integrate.py` with the verbs `prepare`, `twin`, `publish` and `all`: aligns the genomics and metabolomics blocks on `strain_id`; fills gaps within each kingdom without ever looking at the outcome; drops near-constant housekeeping genes (`ef1a`, `rpb1`, `ssu_rRNA`); writes as-measured and centred-within-kingdom block versions plus a preparation ledger; runs the Python counterpart (single blocks, early, sparse early, PLS-DA and late integration, a kingdom-only control and a label-shuffling control) on shared repeated cross-validation folds; grades every signature against the planted truth; measures gene ↔ product correlations and R ↔ Python agreement; publishes every result as an `int_*` table in the database.
  - `R/diablo_integration.R`: DIABLO (mixOmics). It compares as-measured with centred blocks, chooses the number of components with the one-standard-deviation rule, tunes the number of features per block, cross-validates the final model (5 folds × 10 repeats), measures the price of sparsity and selection stability, and writes hand-off CSV files and mixOmics' four standard figures.
  - `tests/test_integrate.py`: 14 tests, including an R ↔ Python contract test on the hand-off file names (32 tests in total).
  - `figures/make_phase3_figures.py`: three concept figures, seven result figures, and the interactive `docs/interactive/integration_explorer.html`; the Plotly library is now shared as `docs/interactive/plotly.min.js` so each interactive page stays small.
  - `artifacts/integration/`: the small committed result tables the app will read.
- **The Handbook** ([`docs/HANDBOOK.md`](docs/HANDBOOK.md)): one living document describing every step from day 0 to the finished product, with what, why, time, checkpoint and commit message per stage, an index of every file, and a troubleshooting map.
- **Roadmaps**: [`docs/ROADMAP.md`](docs/ROADMAP.md) (what this repository builds and in which order, including the *Ask StrainScope* documentation assistant (Phase 6b) and the MCP server (Phase 7b)) and [`docs/PRODUCT_ROADMAP.md`](docs/PRODUCT_ROADMAP.md) (what an industrial version would add, with a verdict and trigger for every technology).
- **Illustrations**: `figures/make_illustrations.py` draws `docs/img/strainscope_logo.svg`, `docs/img/strainscope_icon.svg` and `docs/img/journey_map.svg` (the journey map reads its status from one list, so it can never drift from the roadmap).
- This changelog.

### Changed
- README: logo, Handbook first, Phase 3 results, the new phases (6b, 7b, 8), corrected run commands and repository map.
- Setup guide: R commands use `Rscript -e` everywhere (in PowerShell, `R` is an alias for "repeat last command"); the mixOmics installation points to [`docs/04-integration.md` §6](docs/04-integration.md#6-step-2-install-mixomics-into-the-projects-r-library-once-per-machine); tests are described as present from Phase 1b onward.
- Glossary: Phase 3 terms (integration, DIABLO, block, component, loading, keepX, design matrix, balanced error rate, AUC, repeated cross-validation, negative control, y-scrambling, stability, one-SD rule, centring, contract test, and more).
- Query Cookbook: section 8, *Integration results (Phase 3)*.
- Every phase guide: breadcrumbs link the Handbook; "one-command pipeline" now points to Phase 8.

### Fixed
- `check-public-safe.sh`: the credential check now requires a key to start a word, so a link anchor such as `#ask-strainscope-…` (which contains `sk-` followed by letters) is no longer reported as an API key; real-shaped keys after `=`, a space or a quote are still caught ([`docs/04-integration.md` §12](docs/04-integration.md#12-notes-from-the-build-kept-on-purpose)).

### Removed
- A stray empty `__init__.py` at the project root (committed by mistake; the package's real one lives in `src/strainscope/`).

## History before the first tag

Phases 0 to 2 were built before versioning began. These are their commits on `master`, oldest first:

| Date | Phase | Commit |
|---|---|---|
| 2026-08-24 | 0 · structure | `chore: initialise project structure, docs, and toolbox` |
| 2026-08-26 | 0 · architecture + setup | `docs: add architecture, setup runbook, README, and public-safety gate` |
| 2026-08-26 | 1 · synthetic data | `feat: add Phase 1 synthetic multi-omics data generator, figures, and glossary` |
| 2026-08-27 | 1 · four kingdoms | `feat: broaden dataset to multi-kingdom microbial strains (bacteria, fungi, yeasts, oomycetes)` |
| 2026-08-27 | 1b · real data | `feat: add real-data ingestion framework with BacDive, PubChem, and KEGG adapters` |
| 2026-08-27 | 2 · cleaning + database | `feat: add cleaning pipeline with ledger, DuckDB database, SQL console, and cookbook` |
| 2026-08-27 | 1c · more sources | `feat: add NCBI Datasets and Metabolomics Workbench adapters with API-key handling` |
| 2026-10-09 | housekeeping | `chore: stop tracking R session history` |
