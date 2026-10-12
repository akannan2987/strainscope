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
| 5 | Knowledge graph & networks | [`docs/06-knowledge-graph.md`](06-knowledge-graph.md) | the domain model written first (`src/strainscope/ontology.py`: ten node types, eleven relations, a mode of action for every weapon); a NetworkX graph strain → gene → compound → mode of action → outcome, with real KEGG pathways, RefMet classes and BacDive strains when fetched, Phase 3's gene ↔ product correlations and Phase 4's importances; a source on every edge, checked against the ontology; hubs, communities graded against the planted arsenals, knowledge vs data; explanations of every ranking as walks through the graph; `why`, `path` and `show` questions; results in the database (`kg_*`) and `artifacts/graph/` | ✅ | **v0.2.0** |
| 6 | The app | [`docs/07-app.md`](07-app.md) | a thin, tested service layer (`src/strainscope/service.py`) shared by the terminal, the app and the later AI features; a Streamlit app with seven pages: Home (headline numbers, a health check), Ranking ("if we can test N strains, how many would work?", *likely / borderline / unlikely* bands, the model's report), a page per strain (its reasons as walks through the graph, its corner of the graph), the knowledge graph (network, path finder, look-up, communities), integration, Data (the library; **upload your own strains**: checked, scored, explained, never stored; real data) and a SQL console behind four guards with the cookbook built in; cross-platform start, SSH-tunnel and firewall recipes for RHEL 8 VMs; a shared-use switch (`STRAINSCOPE_MODE=public`) | ✅ | none |
| 6b | Ask StrainScope: the documentation assistant | [`docs/07b-docs-assistant.md`](07b-docs-assistant.md) | `src/strainscope/ask.py` (a word-based search over every guide, glossary entry and docstring, in ~120-word passages, no download) and an *Ask StrainScope* page in the app: answers with the matching passages word for word and links to the exact heading; a gate of four checks (instructions, unknown words, a weak match, word coverage) decides between answered, closest and refused before anything is shown; starter questions and "you might also ask"; a golden question set run with the tests, with one known limitation recorded; optional written answers from a local (Ollama) or hosted model, only for answered questions and only from the passages, which they must cite; `ask_docs` in the service layer for Phase 7b; a test that every link between the documents resolves (details below) | ✅ | **v0.3.0** |
| 7 | Deployment + AI layer | [`docs/08-deployment-ai.md`](08-deployment-ai.md) | the online copy on Streamlit Community Cloud in shared mode (`STRAINSCOPE_MODE=public` from the host's Secrets box): exact package versions (`app/requirements.txt`, scikit-learn pinned to the model card), the database built on the first start, messages a visitor can act on, and a health page (*About this copy*); one connection to a language model for every assistant (`src/strainscope/llm.py`) with a daily cap in shared mode; results in plain words, by rules (`src/strainscope/narrate.py`); **Ask the data** (`src/strainscope/ask_data.py`: a tested Query Cookbook recipe first, a model's query only when none fits, behind a fifth guard and the console's four, the model never seeing a row); **Ask the graph** (`src/strainscope/ask_graph.py`, GraphRAG: names found in the question, walks through the graph as numbered facts with sources, a strain question answered by rules); golden questions for both (37 and 23); a *Suggest a fix* link under every answer (a prefilled GitHub issue); the path picture drawn in walking order; optionally the interactive pages on GitHub Pages (`docs/index.html`) | ✅ | none |
| 7b | MCP server | `docs/08b-mcp-server.md` | a small Model Context Protocol server exposing read-only tools (`ask_docs`, `ask_data`, `ask_graph`, `query_database`, `get_signature`, `rank_strain`, `explain_strain`) so AI assistants can use StrainScope directly, with every call validated and logged; the service layer already has a door for each of the assistants | ⏳ next | none |
| 8 | Packaging & release | `docs/09-packaging.md` | the one-command pipeline (`python src/strainscope/pipeline.py`), also behind a button in the app; tests on Windows, macOS and Linux at every push (continuous integration), the app's own tests included; LICENSE (MIT), a citation file (`CITATION.cff`), a contribution guide and issue templates for people who want to help; automatic alerts for outdated or unsafe dependencies; a keyboard and screen-reader check of the app; CHANGELOG, uninstall guide; an optional container; an optional Git *pre-push hook* that runs the safety gate automatically, so nobody can forget it; the 1.0 tag | ⏳ | **v1.0.0** |

Guides without links don't exist yet. Each one appears when its phase is built.

### What "finished" means: the product checklist

Everything a person needs from StrainScope, as a list, with where each piece is (or will be) built. When every row says ✅, this repository is a complete product; what a larger, multi-user version would add is in the [product roadmap](PRODUCT_ROADMAP.md).

| A user can... | Built in | Status |
|---|---|---|
| rebuild every number from scratch, identically, on Windows, macOS or RHEL 8 | Phases 0 to 5 | ✅ |
| read why every step exists, from a blank laptop on ([Handbook](HANDBOOK.md), guides, [Glossary](GLOSSARY.md), [interactive journey](interactive/journey.html)) | every phase | ✅ living |
| see the ranking, each strain's reasons and the knowledge graph without writing code | Phase 6 | ✅ |
| bring their own strains and get them checked, scored and explained, privately | Phase 6 | ✅ |
| ask the data anything in SQL without being able to break it | Phases 2 and 6 | ✅ |
| run the app on their own computer or a VM with one command | Phase 6 | ✅ |
| ask questions about the project itself and get linked answers | Phase 6b | ✅ |
| open the app from a link, with nothing installed | Phase 7 | ✅ online at [strainscope.streamlit.app](https://strainscope.streamlit.app) ([guide §9](08-deployment-ai.md#9-step-5-put-the-app-online-streamlit-community-cloud)) |
| read results in plain language, ask the data in plain language, get answers that cite the graph | Phase 7 | ✅ |
| let an AI assistant use StrainScope's tools safely | Phase 7b | ⏳ |
| rebuild everything with one command (or one button) | Phase 8 | ⏳ |
| trust that every change was tested on three operating systems | Phase 8 | ⏳ |
| reuse, cite and contribute (licence, citation file, contribution guide, issue templates) | Phase 8 | ⏳ |
| install, update and uninstall cleanly, or run it in a container | Phase 8 | ⏳ |
| rely on its safety: secrets never committed (a host's secrets in its own box), read-only data access, uploads never stored, a language model that never sees data and has a daily cap, dependency alerts | Phases 1c, 6, 7 and 8 | ✅ / ⏳ |
| use it with a keyboard or a screen reader (colour is never the only signal) | Phases 6 and 8 | ✅ / ⏳ |

### Why this order

- **Data before analysis, analysis before product.** Every later box reads what an earlier box wrote, so the order follows the arrows of the [architecture diagram](00-architecture.md#4-the-boxes-and-why-each-one-exists).
- **Integration (3) before machine learning (4).** Integration answers *which features matter and do the blocks agree*; machine learning answers *how well can we predict*. The first tells the second which questions are worth asking. Phase 4 also fixes, inside its pipelines, the small label-free leak that Phase 3 documented.
- **The graph (5) before the app (6).** The app shows the graph, and the graph needs Phase 3's correlations and Phase 4's importances as edge weights.
- **Ask StrainScope (6b) right after the app.** By then the documentation covers the whole path from a blank laptop to a usable app, so the assistant has real material to answer from and its golden question set can be realistic. Building it at that point also means Phase 7 finds the language-model connection already in place.
- **Deployment and the AI layer (7) before the MCP server (7b).** The MCP server exposes the same functions the app and the assistants already use (since Phase 7 the service layer has a door for each: `ask_docs`, `ask_data`, `ask_graph`, `explain_in_words`). Built last, it only adds a new way in to machinery that already exists.
- **Packaging (8) last.** The one-command pipeline, cross-platform continuous integration and the 1.0 tag all assume the rest of the project is finished.

## Ask StrainScope: the documentation assistant, in detail

A question box over StrainScope's own documentation. You type something like *"how do I install mixOmics on Windows?"*, *"what is a balanced error rate?"* or *"why centre within kingdom?"* and get an answer straight away, with links to the exact sections. Think of a librarian who only lends from this one library, and who tells you so when you ask for a book it doesn't have. Levels 1 and 2 are built; the guide is [`docs/07b-docs-assistant.md`](07b-docs-assistant.md).

| Level | Arrives in | What it does |
|---|---|---|
| 1: find and quote | Phase 6b ✅ | splits every document (README, Handbook, guides, glossary, cookbook, roadmaps, code docstrings) into sections; finds the sections that best match a question (word-based search with scikit-learn, no download); returns them verbatim, with links to file and heading; shows starter questions when the box is empty, and "you might also ask" suggestions drawn from related headings |
| 2: grounded answers | Phase 6b ✅ (optional, off by default), switched on by `STRAINSCOPE_ASK_BACKEND` | writes a short answer using **only the sections it found**, and cites them; three backends sit behind one interface: *none* (level 1 only, the default), *local* (an open model served on your own computer by Ollama on Windows, macOS or Linux, so nothing leaves the laptop) and *hosted* (any provider with an OpenAI-compatible interface, with `.env` holding the API key, exactly as in Phase 1c) |
| 3: everywhere | Phase 7 ✅, Phase 7b ⏳ | the same engine in the online copy (written answers on once a hosted model's key is in its Secrets box, within the daily cap) and as the `ask_docs` tool of the MCP server (`ask_docs` already exists in the service layer) |

**Ground rules** (each one is enforced by a test in `tests/test_ask.py`):

- **Out-of-scope questions are refused.** The assistant doesn't guess. If half or more of a question's words appear in no document, or even the best-matching section is a weak match, it says so and lists what it *can* help with, and it does this *before* any language model could be called. (A question that never reaches the model can't come back with an invented answer.)
- **Every answer cites its sources**: file and heading, as clickable links, with the passage word for word.
- **"Not documented yet" is a valid answer.** A question whose words are mostly in the documents, but not answered by any one passage, gets the *closest* sections, marked as such.
- **A golden question set** runs with the tests on every change. It pairs in-scope questions with the sections that count as a right answer, and adds off-topic and trick questions ("ignore your instructions and...") that must be refused and undocumented ones that must not be answered. A question the search is known to get wrong stays in the set as a known limitation.
- **Only documentation text is ever sent** to a language model: the question and up to three passages. Data and keys are never in the text, and only a question the search answered confidently is sent at all. An answer that cites nothing is not shown.

## The AI layer (Phase 7), in short

Three assistants and one rule-based writer, all with the same shape: find first, decide before showing anything, and let a language model (optional) do no more than rewrite what was found. The guide is [`docs/08-deployment-ai.md`](08-deployment-ai.md); what each may send to a model is in its §1, and every row of that table is checked by a test.

| Feature | Without a model | With a model (optional) | Never sent to a model |
|---|---|---|---|
| Ask StrainScope (Phase 6b) | the passages that answer, with links | a short answer citing them | anything but the question and up to three passages |
| Ask the data | a tested Query Cookbook recipe, run through four guards | a new query when no recipe fits, behind a fifth guard | any row of data |
| Ask the graph | numbered facts from walks through the graph, with sources | a short answer citing them, with no number of its own | anything about a strain |
| In plain words | a paragraph written by rules from the results | nothing: no model is used | everything |

## Deferred items and their triggers

| Item | Status | Trigger / approach |
|---|---|---|
| Tier 3 real sources: MGnify (environmental microbiomes), ENA (raw sequence archive) | 🔒 | a phase that can use them (nested pagination and large files need more care than a quick adapter would give them); the "one socket, many plugs" framework already accepts each of them as one new file |
| Real-data swap-in for the synthetic core | 🔒 | a public dataset with genes **and** chemistry **and** an outcome for the same strains (none exists today); the hand-off files of Phase 3 are the slot it would plug into |
| Graph database (Neo4j) | 🔒 | the NetworkX graph outgrows memory or needs multi-user queries; `artifacts/graph/knowledge_layer.graphml` and the two plain tables `nodes.csv` / `edges.csv` can be imported into Neo4j (APOC for the GraphML, `LOAD CSV` for the tables) |
| Shared external ontologies (NCBI Taxonomy, ChEBI, Gene Ontology) mapped onto `src/strainscope/ontology.py` | 🔒 | real data brings real names that need reconciling (the same compound under several names, reclassified genera) |
| Graph machine learning (node embeddings, graph neural networks) | 🔒 | a graph built from real relationships, much larger than today's, and a question the tabular model of Phase 4 can't answer |
| Production web stack (FastAPI back end + React/TypeScript front end + PostgreSQL) | 🔒 | more than one regular user, logins, or a request for a richer interface than Streamlit (see the [product roadmap](PRODUCT_ROADMAP.md)) |
| Embedding-based search for Ask StrainScope | 🔒 | word-based search misses questions phrased differently from the documents (the golden set's known limitation, "Does the app have a dark mode?", is one); a small local embedding model is then added behind the same interface, and the golden set says whether it's better |
| Follow-up questions in the assistants (a conversation) | 🔒 | people ask follow-ups that only make sense with the previous question ("and on Windows?"); the previous question's words would then be carried into the next search |
| Feedback on the assistants' answers | ✅ Phase 7 | the trigger (a public copy other people use) fired with Phase 7: a *Suggest a fix* link under every answer opens a GitHub issue with the question filled in, and missed answers become golden questions or documentation fixes |
| Feedback stored in the app (ratings, a list of missed questions) | 🔒 | logins (the production web stack above), or more suggestions than GitHub issues can comfortably hold; the app keeps no record of visitors today |
| Model-written wording for the plain-language explanations | 🔒 | readers find the rule-written paragraphs hard to follow; it would send a strain's results to a model, so only with a model on the same computer, and never for uploads |
| A model that summarises query results (Ask the data) | 🔒 | tables too large to read at a glance become common; it would send rows, so only with a model on the same computer |
| A custom address for the online copy (its own domain) | 🔒 | the project gets a public name or site of its own; the `streamlit.app` address is enough until then |
| Read-only AI agent that plans multi-step analyses | 🔒 | the MCP server (7b) is stable, since an agent can only be as safe as the tools it's allowed to call |
| Batch correction for uploaded strains | 🔒 | the first upload from a real lab: uploads with a `batch_id` column would get Phase 2's median scaling before scoring (today the app says uploads must already be on the library's scale) |
| Uploading genomes instead of gene calls (FASTA or GFF files, gene calls computed on the way in) | 🔒 | users with sequenced strains and no gene table; needs an annotation step such as antiSMASH (product roadmap A3) |
| Saved views and notes per user in the app | 🔒 | a second regular user (it needs logins, which is the production web stack above) |
| Usage analytics for the app | 🔒 | the online copy exists (Phase 7), but nothing needs the numbers yet. If its owner ever does, the README will say what is counted. Streamlit's own statistics are switched off (`.streamlit/config.toml`) |
| Pinned dependency versions for development (lock file for Python) | 🔒 | the first time an upgrade breaks a test (`renv.lock` already pins the R side, and since Phase 7 `app/requirements.txt` pins the online copy) |

## Version tags

A **tag** is a bookmark on one exact commit, named with a version number, so anyone can return to exactly that state later. Tags mark the points where the project is usable end to end at a new level:

- **v0.1.0**: data foundation and integration (Phases 0 to 3), taking you from a blank laptop to a graded multi-omics signature.
- **v0.2.0**: the analysis is complete (Phases 4 and 5), with predictions and the knowledge graph. *Released with Phase 5.*
- **v0.3.0**: usable by anyone (Phases 6 and 6b), with the app and Ask StrainScope. *Released with Phase 6b.*
- **v1.0.0**: the first complete release (Phases 7 and 8): online, with the AI layer, the MCP server, the one-command pipeline and cross-platform CI. *Planned with Phase 8.* Phase 7 itself gets no tag; the online copy shows the latest release and says that newer changes are listed under *[Unreleased]* in `CHANGELOG.md`.

Between those, **patch releases** (the third number: v0.1.1, v0.1.2, ...) ship fixes found through real use. Each one is tested, documented in [`CHANGELOG.md`](../CHANGELOG.md) and the [Handbook](HANDBOOK.md), and tagged like any other version. So far:

- **v0.1.1**: the safety gate also checks new, not-yet-added files, and every documented command, commit and tag message uses plain keyboard characters ([Handbook Stage 7.1](HANDBOOK.md#stage-71-fix-release-v011-a-safer-safety-gate-and-copy-safe-commands)).

Tag messages, like commit messages, use plain keyboard characters only (see [`docs/01-setup.md` Part H](01-setup.md#copy-commands-safely-plain-keyboard-characters-only)).

The steps for creating and pushing a tag are in the commit ritual of the phase that earns it (and in [`docs/01-setup.md` Part H](01-setup.md#part-h-initialise-git-and-push-with-the-master--beta--develop-workflow)).

## How this document is maintained

At the end of every phase, in the same commit: flip the phase's status mark, link its guide, move any deferred item whose trigger has fired from 🔒 to ⏳, update the stage in the [Handbook](HANDBOOK.md) and the README's build log, and regenerate the journey map (`python figures/make_illustrations.py` after editing its `STAGES` list). If this roadmap and the repository ever disagree, that's a bug to fix.
