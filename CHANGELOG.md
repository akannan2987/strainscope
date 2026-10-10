# Changelog

All notable changes to StrainScope are recorded here, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`: a new MINOR version marks a new usable level of the project (see the tags in [`docs/ROADMAP.md`](docs/ROADMAP.md#version-tags)), a PATCH marks a fix or a documentation improvement, and 1.0.0 marks the first complete release.

Where a step is explained: [`docs/HANDBOOK.md`](docs/HANDBOOK.md) — the day-0-to-product guide that links every phase guide.

## [Unreleased]

Next up: Phase 4 — machine learning, honestly evaluated (`docs/05-machine-learning.md`). See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## [0.1.1] — 2026-10-10 — a safer safety gate, copy-safe commands

A fix release: two problems found while releasing v0.1.0, fixed, tested and documented ([Handbook Stage 7.1](docs/HANDBOOK.md#stage-71--fix-release-v011-a-safer-safety-gate-and-copy-safe-commands)).

### Fixed
- `check-public-safe.sh` now checks every file a commit could publish: the files Git already tracks **and** the new, not-ignored files that `git add -A` is about to add. The documented routine runs the gate before `git add -A`, so the old gate never checked a brand-new file on its first commit. A first attempt (`git grep --untracked`) turned out to skip force-added ignored files; the gate now runs two searches and merges them. It also prints how many tracked and new files it read.
- Every command, commit message and tag message in the documentation uses plain keyboard characters only. A tag message pasted with a long dash (`—`) had arrived in Git garbled; the documented `v0.1.0` tag message now matches the corrected one (`v0.1.0: data foundation and multi-omics integration`).

### Added
- `tests/test_safety_gate.py`: five tests that run the gate in throw-away Git repositories (clean; new file with a key; ignored `.env`; force-added ignored file; link anchor without false alarm). One fails on the old gate. 37 tests in total; the gate tests are skipped on Windows, where the gate runs from Git Bash.
- `docs/01-setup.md` Part H: a diagram of the three kinds of files (tracked, new, ignored) and which ones the gate reads; *Notes from the build* for the gate; a new section *Copy commands safely: plain keyboard characters only*, with a table of look-alike characters.
- `docs/04-integration.md` §17: how to check a tag message (`git tag -n1`) and replace a garbled one.
- `docs/HANDBOOK.md`: Stage 7.1 (this release, with a before/after diagram), a copy-safety note in Stage 2, and three new rows in *When something goes wrong*.
- `docs/GLOSSARY.md`: tracked / new (untracked) / ignored file, staging, force-add, plain keyboard characters (ASCII), regression test, patch release.

### Changed
- `docs/ROADMAP.md`: the fix release in the phase plan; patch releases explained under *Version tags*; Phase 8 gains an optional pre-push hook so the gate runs by itself.
- `README.md`, `docs/PRODUCT_ROADMAP.md`: version and test counts.

## [0.1.0] — 2026-10-09 — data foundation and integration

From a blank laptop to a graded multi-omics signature (Phases 0–3).

### Added
- **Phase 3 — multi-omics integration** ([`docs/04-integration.md`](docs/04-integration.md)).
  - `src/strainscope/integrate.py` with the verbs `prepare`, `twin`, `publish` and `all`: aligns the genomics and metabolomics blocks on `strain_id`; fills gaps within each kingdom without ever looking at the outcome; drops near-constant housekeeping genes (`ef1a`, `rpb1`, `ssu_rRNA`); writes as-measured and centred-within-kingdom block versions plus a preparation ledger; runs the Python counterpart (single blocks, early, sparse early, PLS-DA and late integration, a kingdom-only control and a label-shuffling control) on shared repeated cross-validation folds; grades every signature against the planted truth; measures gene ↔ product correlations and R ↔ Python agreement; publishes every result as an `int_*` table in the database.
  - `R/diablo_integration.R`: DIABLO (mixOmics) — compares as-measured with centred blocks, chooses the number of components with the one-standard-deviation rule, tunes the number of features per block, cross-validates the final model (5 folds × 10 repeats), measures the price of sparsity and selection stability, writes hand-off CSV files and mixOmics' four standard figures.
  - `tests/test_integrate.py`: 14 tests, including an R ↔ Python contract test on the hand-off file names (32 tests in total).
  - `figures/make_phase3_figures.py`: three concept figures, seven result figures, and the interactive `docs/interactive/integration_explorer.html`; the Plotly library is now shared as `docs/interactive/plotly.min.js` so each interactive page stays small.
  - `artifacts/integration/`: the small committed result tables the app will read.
- **The Handbook** — [`docs/HANDBOOK.md`](docs/HANDBOOK.md): one living document describing every step from day 0 to the finished product, with what, why, time, checkpoint and commit message per stage, an index of every file, and a troubleshooting map.
- **Roadmaps** — [`docs/ROADMAP.md`](docs/ROADMAP.md) (what this repository builds and in which order, including the *Ask StrainScope* documentation assistant (Phase 6b) and the MCP server (Phase 7b)) and [`docs/PRODUCT_ROADMAP.md`](docs/PRODUCT_ROADMAP.md) (what an industrial version would add, with a verdict and trigger for every technology).
- **Illustrations** — `figures/make_illustrations.py` draws `docs/img/strainscope_logo.svg`, `docs/img/strainscope_icon.svg` and `docs/img/journey_map.svg` (the journey map reads its status from one list, so it can never drift from the roadmap).
- This changelog.

### Changed
- README: logo, Handbook first, Phase 3 results, the new phases (6b, 7b, 8), corrected run commands and repository map.
- Setup guide: R commands use `Rscript -e` everywhere (in PowerShell, `R` is an alias for "repeat last command"); the mixOmics installation points to [`docs/04-integration.md` §6](docs/04-integration.md#6-step-2--install-mixomics-into-the-projects-r-library-once-per-machine); tests are described as present from Phase 1b onward.
- Glossary: Phase 3 terms (integration, DIABLO, block, component, loading, keepX, design matrix, balanced error rate, AUC, repeated cross-validation, negative control, y-scrambling, stability, one-SD rule, centring, contract test, and more).
- Query Cookbook: section 8, *Integration results (Phase 3)*.
- Every phase guide: breadcrumbs link the Handbook; "one-command pipeline" now points to Phase 8.

### Fixed
- `check-public-safe.sh`: the credential check now requires a key to start a word, so a link anchor such as `#ask-strainscope-…` (which contains `sk-` followed by letters) is no longer reported as an API key; real-shaped keys after `=`, a space or a quote are still caught ([`docs/04-integration.md` §12](docs/04-integration.md#12-notes-from-the-build-kept-on-purpose)).

### Removed
- A stray empty `__init__.py` at the project root (committed by mistake; the package's real one lives in `src/strainscope/`).

## History before the first tag

Phases 0–2 were built before versioning began; their commits on `master`, oldest first:

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
