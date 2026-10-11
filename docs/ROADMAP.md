# Roadmap: what this repository builds, in what order, and why

[← README](../README.md) · [Handbook](HANDBOOK.md) · [Product roadmap](PRODUCT_ROADMAP.md) · [Architecture](00-architecture.md) · [Glossary](GLOSSARY.md)

**Prerequisites:** [`docs/00-architecture.md`](00-architecture.md) (the boxes this plan builds).
**Learning goal:** know exactly what has been built, what comes next and in which order, *why* the order is what it is, and what would turn a deferred idea into a scheduled one.

This document covers this repository only: everything needed for a complete, usable, documented product that runs on a laptop and online. What a larger, industrial version would add (cloud data platforms, a multi-user web front end, regulation, pricing) is described in the [product roadmap](PRODUCT_ROADMAP.md). Progress is mirrored in the [Handbook](HANDBOOK.md) and in the README's *Build log*. All three are updated in the same commit, so they don't drift apart.

## How to read status

| Mark | Meaning |
|---|---|
| ✅ | built, tested, documented, on `master` |
| 🔧 | in progress on `develop` |
| ⏳ | scheduled, not started |
| 🔒 | deferred; the trigger that would schedule it is stated |

## The journey at a glance

![The StrainScope journey](img/journey_map.svg)

## The phase plan

| # | Phase | Guide | What it builds | Status | Tag |
|---|---|---|---|---|---|
| 0 | Architecture | [`docs/00-architecture.md`](00-architecture.md) | every box of the system, explained from zero | ✅ | none |
| 0b | Setup | [`docs/01-setup.md`](01-setup.md) | Python + venv, R + renv, Git with `master`/`beta`/`develop` and the pre-push safety gate, on Windows, macOS and RHEL 8 | ✅ | none |
| 1 | Synthetic data | [`docs/02-data-generation.md`](02-data-generation.md) | the seeded multi-kingdom generator: 600 strains × 31 genes × 20 metabolites + phenotype, with mess injected on purpose | ✅ | none |
| 1b | Real data | [`docs/02b-real-data-ingestion.md`](02b-real-data-ingestion.md) | the ingestion framework (probe → fetch → tidy, evidence locker, provenance log): BacDive, PubChem, KEGG | ✅ | none |
| 1c | More real sources | [`docs/02c-more-real-sources.md`](02c-more-real-sources.md) | NCBI Datasets (genomes, four kingdoms) + Metabolomics Workbench (RefMet); API keys handled safely | ✅ | none |
| 2 | Cleaning & database | [`docs/03-harmonization-qc.md`](03-harmonization-qc.md) | six-rule cleaning with a ledger; DuckDB; the read-only SQL console; the [Query Cookbook](QUERY_COOKBOOK.md) | ✅ | none |
| 3 | Multi-omics integration | [`docs/04-integration.md`](04-integration.md) | block preparation; DIABLO (R/mixOmics) with tuning and cross-validation; the Python twin (early, late, PLS-DA, lasso) with controls; graded signatures; R↔Python agreement; results in the database; the [Handbook](HANDBOOK.md) and both roadmaps | ✅ | **v0.1.0** |
| 3.1 | Fix release | [`CHANGELOG.md`](../CHANGELOG.md), [`docs/01-setup.md` Part H](01-setup.md#the-pre-push-safety-gate-check-public-safesh) | the safety gate also checks new files (and force-added ignored ones), with its own tests (`tests/test_safety_gate.py`); every documented command, commit and tag message in plain keyboard characters | ✅ | **v0.1.1** |
| 4 | Machine learning | [`docs/05-machine-learning.md`](05-machine-learning.md) | leak-proof pipelines (preparation re-learned inside every fold, the Phase 3 leak measured and closed, a real leak shown on noise); a baseline, an elastic net (tuned by nested cross-validation), a random forest and gradient boosting on the same folds; class weights; calibration (Platt scaling); permutation importance graded against the planted truth; error analysis; the calibrated winner saved with a model card; out-of-fold ranking in `artifacts/model/` | ✅ | none |
| 5 | Knowledge graph & networks | `docs/06-knowledge-graph.md` | the domain model (an ontology written in English first); a NetworkX graph strain → gene → metabolite → pathway → outcome, seeded with real KEGG/RefMet edges and Phase 3's gene ↔ product correlations; hubs, communities, paths | ⏳ next | **v0.2.0** |
| 6 | The app | `docs/07-app.md` | the Streamlit app: data picker (Upload · Synthetic · Fetch-real), integration and ranking views, the graph view, the SQL console with the cookbook built in | ⏳ | none |
| 6b | Ask StrainScope: the documentation assistant | `docs/07b-docs-assistant.md` | `python src/strainscope/ask.py "question"` and an app tab: answers from the project's own documents with links to the exact section; refuses questions outside the project; starter questions and "you might also ask"; a golden question set in the tests (details below) | ⏳ | **v0.3.0** |
| 7 | Deployment + AI layer | `docs/08-deployment-ai.md` | free public deployment (Streamlit Community Cloud), secrets on the host; plain-language explanations of results; grounded answers in Ask StrainScope; a read-only data assistant (question → SQL → answer, with guardrails); GraphRAG (answers by walking the graph) | ⏳ | none |
| 7b | MCP server | `docs/08b-mcp-server.md` | a small Model Context Protocol server exposing read-only tools (`ask_docs`, `query_database`, `get_signature`, `rank_strain`) so AI assistants can use StrainScope directly, with every call validated and logged | ⏳ | none |
| 8 | Packaging & release | `docs/09-packaging.md` | the one-command pipeline (`python src/strainscope/pipeline.py`); tests on Windows, macOS and Linux at every push (continuous integration); LICENSE (MIT), CHANGELOG, uninstall guide; an optional container; an optional Git *pre-push hook* that runs the safety gate automatically, so nobody can forget it; the 1.0 tag | ⏳ | **v1.0.0** |

Guides without links don't exist yet. Each one appears when its phase is built.

### Why this order

- **Data before analysis, analysis before product.** Every later box reads what an earlier box wrote, so the order follows the arrows of the [architecture diagram](00-architecture.md#4-the-boxes-and-why-each-one-exists).
- **Integration (3) before machine learning (4).** Integration answers *which features matter and do the blocks agree*; machine learning answers *how well can we predict*. The first tells the second which questions are worth asking. Phase 4 also fixes, inside its pipelines, the small label-free leak that Phase 3 documented.
- **The graph (5) before the app (6).** The app shows the graph, and the graph needs Phase 3's correlations and Phase 4's importances as edge weights.
- **Ask StrainScope (6b) right after the app.** By then the documentation covers the whole path from a blank laptop to a usable app, so the assistant has real material to answer from and its golden question set can be realistic. Building it at that point also means Phase 7 finds the language-model connection already in place.
- **Deployment and the AI layer (7) before the MCP server (7b).** The MCP server exposes the same functions the app and the assistant already use. Built last, it only adds a new way in to machinery that already exists.
- **Packaging (8) last.** The one-command pipeline, cross-platform continuous integration and the 1.0 tag all assume the rest of the project is finished.

## Ask StrainScope: the documentation assistant, in detail

A question box over StrainScope's own documentation. You type something like *"how do I install mixOmics on Windows?"*, *"what is a balanced error rate?"* or *"why centre within kingdom?"* and get an answer straight away, with links to the exact sections. Think of a librarian who only lends from this one library, and who tells you so when you ask for a book it doesn't have.

| Level | Arrives in | What it does |
|---|---|---|
| 1: find and quote | Phase 6b | splits every document (README, Handbook, guides, glossary, cookbook, roadmaps, code docstrings) into sections; finds the sections that best match a question (word-based search with scikit-learn, no download); returns them verbatim, with links to file and heading; shows starter questions when the box is empty, and "you might also ask" suggestions drawn from related headings |
| 2: grounded answers | Phase 6b (optional), switched on by environment variable | writes a short answer using **only the sections it found**, and cites them; three backends sit behind one interface: *none* (level 1 only, the default), *local* (an open model served on your own computer by Ollama on Windows, macOS or Linux, so nothing leaves the laptop) and *hosted* (any provider with an OpenAI-compatible interface, with `.env` holding the API key, exactly as in Phase 1c) |
| 3: everywhere | Phases 7 and 7b | the same engine as a chat panel in the deployed app and as the `ask_docs` tool of the MCP server |

**Ground rules** (each one is enforced by a test):

- **Out-of-scope questions are refused.** The assistant doesn't guess. If even the best-matching section is a weak match, it replies that the question isn't about StrainScope and lists what it *can* help with, and it does this *before* any language model is called. (A question that never reaches the model can't come back with an invented answer.)
- **Every answer cites its sources**: file and heading, as clickable links.
- **"Not documented yet" is a valid answer.** An in-scope question with no good section returns the closest sections and says so.
- **A golden question set** runs with the tests on every change. It pairs in-scope questions with the section each one should cite, and adds off-topic and trick questions ("ignore your instructions and…") that must be refused.
- **Only documentation text is ever sent** to a language model. Data and keys are never sent.

## Deferred items and their triggers

| Item | Status | Trigger / approach |
|---|---|---|
| Tier 3 real sources: MGnify (environmental microbiomes), ENA (raw sequence archive) | 🔒 | a phase that can use them (nested pagination and large files need more care than a quick adapter would give them); the "one socket, many plugs" framework already accepts each of them as one new file |
| Real-data swap-in for the synthetic core | 🔒 | a public dataset with genes **and** chemistry **and** an outcome for the same strains (none exists today); the hand-off files of Phase 3 are the slot it would plug into |
| Graph database (Neo4j) | 🔒 | the NetworkX graph outgrows memory or needs multi-user queries |
| Production web stack (FastAPI back end + React/TypeScript front end + PostgreSQL) | 🔒 | more than one regular user, logins, or a request for a richer interface than Streamlit (see the [product roadmap](PRODUCT_ROADMAP.md)) |
| Embedding-based search for Ask StrainScope | 🔒 | word-based search misses questions phrased differently from the documents; a small local embedding model is then added behind the same interface |
| Read-only AI agent that plans multi-step analyses | 🔒 | the MCP server (7b) is stable, since an agent can only be as safe as the tools it's allowed to call |
| Pinned dependency versions (lock file for Python) | 🔒 | the first time an upgrade breaks a test (`renv.lock` already pins the R side) |

## Version tags

A **tag** is a bookmark on one exact commit, named with a version number, so anyone can return to exactly that state later. Tags mark the points where the project is usable end to end at a new level:

- **v0.1.0**: data foundation and integration (Phases 0 to 3), taking you from a blank laptop to a graded multi-omics signature.
- **v0.2.0**: the analysis is complete (Phases 4 and 5), with predictions and the knowledge graph.
- **v0.3.0**: usable by anyone (Phases 6 and 6b), with the app and Ask StrainScope.
- **v1.0.0**: released (Phases 7 and 8). It's online, with the AI layer, the MCP server, the one-command pipeline and cross-platform CI.

Between those, **patch releases** (the third number: v0.1.1, v0.1.2, ...) ship fixes found through real use. Each one is tested, documented in [`CHANGELOG.md`](../CHANGELOG.md) and the [Handbook](HANDBOOK.md), and tagged like any other version. So far:

- **v0.1.1**: the safety gate also checks new, not-yet-added files, and every documented command, commit and tag message uses plain keyboard characters ([Handbook Stage 7.1](HANDBOOK.md#stage-71-fix-release-v011-a-safer-safety-gate-and-copy-safe-commands)).

Tag messages, like commit messages, use plain keyboard characters only (see [`docs/01-setup.md` Part H](01-setup.md#copy-commands-safely-plain-keyboard-characters-only)).

The steps for creating and pushing a tag are in the commit ritual of the phase that earns it (and in [`docs/01-setup.md` Part H](01-setup.md#part-h-initialise-git-and-push-with-the-master--beta--develop-workflow)).

## How this document is maintained

At the end of every phase, in the same commit: flip the phase's status mark, link its guide, move any deferred item whose trigger has fired from 🔒 to ⏳, update the stage in the [Handbook](HANDBOOK.md) and the README's build log, and regenerate the journey map (`python figures/make_illustrations.py` after editing its `STAGES` list). If this roadmap and the repository ever disagree, that's a bug to fix.
