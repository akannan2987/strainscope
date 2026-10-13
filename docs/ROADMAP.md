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
| 7.1 | Fix | [`docs/LANGUAGE_MODEL.md` §9](LANGUAGE_MODEL.md#9-how-a-written-answer-is-asked-for-and-checked), [Handbook Stage 12.1](HANDBOOK.md#stage-121-fix-for-small-language-models-the-model-check-and-clearer-suggestions) | small language models cite their sources: the request for a written answer shows the citation rule with an example sentence, one worked example and a reminder (`cited_messages()` in `src/strainscope/llm.py`; with llama3.2:3b, 0 of 4 answers shown before, 4 of 4 after); the model check (`python src/strainscope/service.py check-model`); *You might also ask about* names the part behind a heading a guide repeats (no bare *Steps*); Ask StrainScope gives a model only the strong matches (the best passage, and the next ones only at three quarters of its match or more, `model_hits()`), after a weak third match steered a written answer off the question; two golden questions for the language-model how-to | ✅ | none |
| 7b | MCP server | [`docs/08b-mcp-server.md`](08b-mcp-server.md) | a Model Context Protocol server (`src/strainscope/mcp_server.py`) through which AI assistant apps (Claude Desktop, Claude Code and others) use StrainScope directly: nine read-only tools, the seven planned (`ask_docs`, `ask_data`, `ask_graph`, `query_database`, `get_signature`, `rank_strain`, `explain_strain`) plus `describe_database` and `shortlist`, each a thin door onto the service layer; checked input with refusals as sentences, SQL behind five guards and at most 200 rows, MCP tool annotations marking every tool read-only, a call log without results; the commands `tools`, `call`, `check` (a real MCP session over stdio) and `config` (the settings for an app, with this computer's paths); `mcp` kept off the online copy | ✅ | none |
| 8 | Packaging & release | [`docs/09-packaging.md`](09-packaging.md) | the one-command pipeline (`src/strainscope/pipeline.py`: the plans `everything`, `database`, `real` and `probe`, and `compare`, which checks every rebuilt number against the committed one to within 0.001), also behind a button in the app; ties in the ranking in strain-id order, so it's the same on every computer; continuous integration (`.github/workflows/ci.yml`): eleven jobs at every push to master, on Windows, macOS and Linux with Python 3.12 and 3.14, on RHEL 8 (Red Hat's UBI 8 image), with the online copy's exact versions, a keyboard and screen-reader check, the safety gate and the container; LICENSE (MIT), `CITATION.cff`, `CONTRIBUTING.md`, `SECURITY.md`, issue forms and a pull-request checklist; Dependabot alerts and monthly update suggestions; the keyboard and screen-reader check (`tools/check_accessibility.py`) and the fixes it led to; the container (`Dockerfile`); the optional pre-push hook (`.githooks/pre-push`); `config --write` and `--remove` for Claude Desktop; the uninstall guide ([`docs/UNINSTALL.md`](UNINSTALL.md)); the 1.0 release | ✅ | **v1.0.0** |
| 9 | The whole workflow on your own data | [`docs/10-workflow-and-your-data.md`](10-workflow-and-your-data.md) | **datasets**: a folder each under `data/processed/datasets/`, in the library's layout, chosen by one setting (`STRAINSCOPE_DATASET`, read by `src/strainscope/paths.py`), so the scripts of Phases 1 to 5 run on any data without touching the library; three tables of your own (genes, compounds, trial results) checked cell by cell before anything is saved (`src/strainscope/datasets.py`: errors, warnings and notes with spreadsheet row numbers, limits, the four kingdoms), or a fresh simulated library with any seed and size; the `simulate` and `workflow` plans and `pipeline.py --dataset NAME`; no grading without an answer key; quick settings (2 repeats instead of 10); each step's state from its receipt (done, run again, to do) and what it found (`datasets.py show`); `compare --dataset`, which showed that seed 42 with 600 strains rebuilds the library; the app's **Workflow** page and a Dataset box in the sidebar that switches every page; on a shared copy, datasets per browser tab, deleted after an hour, quick settings and lower limits, one run at a time; nothing about your own data sent to a language model; the 1.1 release | ✅ | **v1.1.0** |

Every phase is built, and every guide is linked. Fixes found through use become patch releases (below).

### What "finished" means: the product checklist

Everything a person needs from StrainScope, as a list, with where each piece is built. Every row has said ✅ since Phase 8, and Phase 9 added two more rows, both ✅; what a larger, multi-user version would add is in the [product roadmap](PRODUCT_ROADMAP.md).

| A user can... | Built in | Status |
|---|---|---|
| rebuild every number from scratch, identically, on Windows, macOS or RHEL 8 | Phases 0 to 5 | ✅ (checked at every push since Phase 8; on ARM processors, such as Macs with an M chip, the random forest's numbers differ slightly: [why](09-packaging.md#18-notes-from-the-build-kept-on-purpose)) |
| read why every step exists, from a blank laptop on ([Handbook](HANDBOOK.md), guides, [Glossary](GLOSSARY.md), [interactive journey](interactive/journey.html)) | every phase | ✅ living |
| see the ranking, each strain's reasons and the knowledge graph without writing code | Phase 6 | ✅ |
| bring their own strains and get them checked, scored and explained, privately | Phase 6 | ✅ |
| ask the data anything in SQL without being able to break it | Phases 2 and 6 | ✅ |
| run the app on their own computer or a VM with one command | Phase 6 | ✅ |
| ask questions about the project itself and get linked answers | Phase 6b | ✅ |
| open the app from a link, with nothing installed | Phase 7 | ✅ online at [strainscope.streamlit.app](https://strainscope.streamlit.app) ([guide §9](08-deployment-ai.md#9-step-5-put-the-app-online-streamlit-community-cloud)) |
| read results in plain language, ask the data in plain language, get answers that cite the graph | Phase 7 | ✅ |
| switch on a language model for written answers, at home or online, and off again, and check that it cites its sources | Phases 6b and 7, fix 7.1 (Handbook Stage 12.1) | ✅ ([how](LANGUAGE_MODEL.md), [the check](LANGUAGE_MODEL.md#9-how-a-written-answer-is-asked-for-and-checked)) |
| let an AI assistant use StrainScope's tools safely | Phase 7b | ✅ ([how to connect one](08b-mcp-server.md#9-step-5-connect-an-assistant-app)) |
| rebuild everything with one command (or one button), and check that the numbers match | Phase 8 | ✅ ([how](09-packaging.md#5-step-1-rebuild-everything-with-one-command)) |
| trust that every change was tested on three operating systems (and RHEL 8) | Phase 8 | ✅ ([the tests](09-packaging.md#12-step-8-push-and-watch-the-automatic-tests)) |
| reuse, cite and contribute (licence, citation file, contribution guide, issue templates, a security policy) | Phase 8 | ✅ ([`CONTRIBUTING.md`](../CONTRIBUTING.md)) |
| install, update and uninstall cleanly, or run it in a container | Phase 8 | ✅ ([how](09-packaging.md#15-install-update-uninstall), [uninstall](UNINSTALL.md)) |
| run every phase, from cleaning to the knowledge graph, on their own strains (three tables, checked first), from the app or one command, without touching the library | Phase 9 | ✅ ([how](10-workflow-and-your-data.md#8-step-4-run-every-phase-on-it), [the Workflow page](10-workflow-and-your-data.md#10-step-6-the-same-in-the-app-the-workflow-page)) |
| try the whole workflow on a fresh simulated library of any seed and size, and check that the library's own seed rebuilds it | Phase 9 | ✅ ([how](10-workflow-and-your-data.md#11-step-7-a-fresh-simulated-library-and-the-library-rebuilt)) |
| rely on its safety: secrets never committed (a host's secrets in its own box), read-only data access (for people and for assistant apps, with every MCP call logged), uploads never stored, a language model that never sees data and has a daily cap, nothing about your own datasets sent to a model, a shared copy's datasets kept per visitor and deleted after an hour, dependency alerts | Phases 1c, 6, 7, 7b, 8 and 9 | ✅ |
| use it with a keyboard or a screen reader (colour is never the only signal) | Phases 6 and 8 | ✅ ([the check](09-packaging.md#10-step-6-the-keyboard-and-screen-reader-check)) |

### Why this order

- **Data before analysis, analysis before product.** Every later box reads what an earlier box wrote, so the order follows the arrows of the [architecture diagram](00-architecture.md#4-the-boxes-and-why-each-one-exists).
- **Integration (3) before machine learning (4).** Integration answers *which features matter and do the blocks agree*; machine learning answers *how well can we predict*. The first tells the second which questions are worth asking. Phase 4 also fixes, inside its pipelines, the small label-free leak that Phase 3 documented.
- **The graph (5) before the app (6).** The app shows the graph, and the graph needs Phase 3's correlations and Phase 4's importances as edge weights.
- **Ask StrainScope (6b) right after the app.** By then the documentation covers the whole path from a blank laptop to a usable app, so the assistant has real material to answer from and its golden question set can be realistic. Building it at that point also means Phase 7 finds the language-model connection already in place.
- **Deployment and the AI layer (7) before the MCP server (7b).** The MCP server exposes the same functions the app and the assistants already use (since Phase 7 the service layer has a door for each: `ask_docs`, `ask_data`, `ask_graph`, `explain_in_words`). Built last, it only adds a new way in to machinery that already exists. That's how it turned out: Phase 7b added no new computation, only the doors, their checks and a log.
- **Packaging (8) after the analysis and the app.** The one-command pipeline, cross-platform continuous integration and the 1.0 tag all assume the rest of the project is finished.
- **Your own data (9) after the release.** Running every phase on any data reuses Phase 8's plans and its live log, and `compare` gave a fixed reference: with the 1.0 results committed, a simulated dataset with the library's own seed had to reproduce them, which checked that the changes for datasets left the library alone.

## Ask StrainScope: the documentation assistant, in detail

A question box over StrainScope's own documentation. You type something like *"how do I install mixOmics on Windows?"*, *"what is a balanced error rate?"* or *"why centre within kingdom?"* and get an answer straight away, with links to the exact sections. Think of a librarian who only lends from this one library, and who tells you so when you ask for a book it doesn't have. Levels 1 and 2 are built; the guide is [`docs/07b-docs-assistant.md`](07b-docs-assistant.md).

| Level | Arrives in | What it does |
|---|---|---|
| 1: find and quote | Phase 6b ✅ | splits every document (README, Handbook, guides, glossary, cookbook, roadmaps, code docstrings) into sections; finds the sections that best match a question (word-based search with scikit-learn, no download); returns them verbatim, with links to file and heading; shows starter questions when the box is empty, and "you might also ask" suggestions drawn from related headings |
| 2: grounded answers | Phase 6b ✅ (optional, off by default), switched on by `STRAINSCOPE_ASK_BACKEND` | writes a short answer using **only the sections it found**, and cites them; three backends sit behind one interface: *none* (level 1 only, the default), *local* (an open model served on your own computer by Ollama on Windows, macOS or Linux, so nothing leaves the laptop) and *hosted* (any provider with an OpenAI-compatible interface, with `.env` holding the API key, exactly as in Phase 1c) |
| 3: everywhere | Phase 7 ✅, Phase 7b ✅ | the same engine in the online copy (written answers on once a hosted model's key is in its Secrets box, within the daily cap) and as the `ask_docs` tool of the MCP server, which assistant apps call ([`docs/08b-mcp-server.md`](08b-mcp-server.md)) |

**Ground rules** (each one is enforced by a test in `tests/test_ask.py`):

- **Out-of-scope questions are refused.** The assistant doesn't guess. If half or more of a question's words appear in no document, or even the best-matching section is a weak match, it says so and lists what it *can* help with, and it does this *before* any language model could be called. (A question that never reaches the model can't come back with an invented answer.)
- **Every answer cites its sources**: file and heading, as clickable links, with the passage word for word.
- **"Not documented yet" is a valid answer.** A question whose words are mostly in the documents, but not answered by any one passage, gets the *closest* sections, marked as such.
- **A golden question set** runs with the tests on every change. It pairs in-scope questions with the sections that count as a right answer, and adds off-topic and trick questions ("ignore your instructions and...") that must be refused and undocumented ones that must not be answered. A question the search is known to get wrong stays in the set as a known limitation.
- **Only documentation text is ever sent** to a language model: the fixed rules (with one made-up worked example of a cited answer), the question and up to three passages (the best one, and the others only if they match nearly as well). Data and keys are never in the text, and only a question the search answered confidently is sent at all. An answer that cites nothing is not shown.

## The AI layer (Phase 7), in short

Three assistants and one rule-based writer, all with the same shape: find first, decide before showing anything, and let a language model (optional) do no more than rewrite what was found. The guide is [`docs/08-deployment-ai.md`](08-deployment-ai.md); what each may send to a model is in its §1, and every row of that table is checked by a test.

| Feature | Without a model | With a model (optional) | Never sent to a model |
|---|---|---|---|
| Ask StrainScope (Phase 6b) | the passages that answer, with links | a short answer citing them | anything but its rules, the question and up to three passages |
| Ask the data | a tested Query Cookbook recipe, run through four guards | a new query when no recipe fits, behind a fifth guard | any row of data |
| Ask the graph | numbered facts from walks through the graph, with sources | a short answer citing them, with no number of its own | anything about a strain |
| In plain words | a paragraph written by rules from the results | nothing: no model is used | everything |

With a dataset of your own chosen (Phase 9), Ask the data and Ask the graph don't ask a model at all: your column names and your strains' facts aren't public, so the recipes, facts and routes answer alone.

The MCP server (Phase 7b) uses no model of its own. An assistant app that calls its tools brings its own model, and that model sees what the tools return; [`docs/08b-mcp-server.md` §1](08b-mcp-server.md#what-the-assistant-sees) lists what each tool can show.

No model is switched on by default, here or online. [`docs/LANGUAGE_MODEL.md`](LANGUAGE_MODEL.md) shows every way to switch one on and off (Ollama on your own computer, a hosted provider at home, a hosted provider for the online copy), what each one sends and costs, what to do when something goes wrong, and how to check that a model cites its sources (`python src/strainscope/service.py check-model`, added in fix 7.1, [Handbook Stage 12.1](HANDBOOK.md#stage-121-fix-for-small-language-models-the-model-check-and-clearer-suggestions), after a small model was found citing nothing).

## Deferred items and their triggers

| Item | Status | Trigger / approach |
|---|---|---|
| Tier 3 real sources: MGnify (environmental microbiomes), ENA (raw sequence archive) | 🔒 | a phase that can use them (nested pagination and large files need more care than a quick adapter would give them); the "one socket, many plugs" framework already accepts each of them as one new file |
| Real-data swap-in for the synthetic core | 🔒 | a public dataset with genes **and** chemistry **and** an outcome for the same strains (none exists today); since Phase 9 it would come in as a dataset of three tables, through the checks |
| Graph database (Neo4j) | 🔒 | the NetworkX graph outgrows memory or needs multi-user queries; `artifacts/graph/knowledge_layer.graphml` and the two plain tables `nodes.csv` / `edges.csv` can be imported into Neo4j (APOC for the GraphML, `LOAD CSV` for the tables) |
| Shared external ontologies (NCBI Taxonomy, ChEBI, Gene Ontology) mapped onto `src/strainscope/ontology.py` | 🔒 | real data brings real names that need reconciling (the same compound under several names, reclassified genera) |
| Graph machine learning (node embeddings, graph neural networks) | 🔒 | a graph built from real relationships, much larger than today's, and a question the tabular model of Phase 4 can't answer |
| Production web stack (FastAPI back end + React/TypeScript front end + PostgreSQL) | 🔒 | more than one regular user, logins, or a request for a richer interface than Streamlit (see the [product roadmap](PRODUCT_ROADMAP.md)) |
| Embedding-based search for Ask StrainScope | 🔒 | word-based search misses questions phrased differently from the documents (the golden set's known limitation, "Does the app have a dark mode?", is one); a small local embedding model is then added behind the same interface, and the golden set says whether it's better |
| Follow-up questions in the assistants (a conversation) | 🔒 | people ask follow-ups that only make sense with the previous question ("and on Windows?"); the previous question's words would then be carried into the next search |
| Feedback on the assistants' answers | ✅ Phase 7 | the trigger (a public copy other people use) fired with Phase 7: a *Suggest a fix* link under every answer opens a GitHub issue with the question filled in, and missed answers become golden questions or documentation fixes |
| Feedback stored in the app (ratings, a list of missed questions) | 🔒 | logins (the production web stack above), or more suggestions than GitHub issues can comfortably hold; the app keeps no record of visitors today |
| A language model on the public online copy | 🔒 | the owner wants written answers for visitors and accepts that their questions go to a provider on the owner's key, within the daily cap; setup C of [`docs/LANGUAGE_MODEL.md`](LANGUAGE_MODEL.md) switches it on in a few minutes |
| Model-written wording for the plain-language explanations | 🔒 | readers find the rule-written paragraphs hard to follow; it would send a strain's results to a model, so only with a model on the same computer, and never for uploads |
| The model check as a button on *About this copy* | 🔒 | the owner of an online copy switches a model on there (setup C) and wants to check it without a terminal; it would send four requests on the owner's key, so the button would be for the owner only, which needs logins (the production web stack above) or a setting only the owner can change |
| A model that summarises query results (Ask the data) | 🔒 | tables too large to read at a glance become common; it would send rows, so only with a model on the same computer |
| A custom address for the online copy (its own domain) | 🔒 | the project gets a public name or site of its own; the `streamlit.app` address is enough until then |
| Read-only AI agent that plans multi-step analyses | 🔒 | the MCP server (built in 7b) has been used for a while without changes to its tools, since an agent can only be as safe as the tools it's allowed to call, and a question comes up that assistant apps can't plan by chaining the tools themselves (they already chain a few calls) |
| An MCP server other people reach over the internet (the "streamable HTTP" transport) | 🔒 | people want StrainScope's tools in their assistant without installing anything; it needs a host that keeps connections open (the Streamlit host doesn't), sign-in or a key per user, and rate limits, so it belongs with the production web stack above |
| MCP resources and prompts (documents an app can attach, ready-made requests) | 🔒 | the assistant apps people use make good use of them, or the call log shows the same few questions again and again; the tools cover the same ground until then |
| Scoring your own strains through the MCP server | 🔒 | someone with their own strains works mainly through an assistant app; it needs a tool that reads one file the user names, with the app's upload checks, and a decision about uploads reaching the app's model (today uploads stay in the app's memory and no tool reads files) |
| Batch correction for uploaded strains | 🔒 | the first upload from a real lab: uploads with a `batch_id` column would get Phase 2's median scaling before scoring (today the Data page says uploads must already be on the library's scale; a dataset of your own, Phase 9, is cleaned with the batch correction when it has a `batch_id`) |
| Uploading genomes instead of gene calls (FASTA or GFF files, gene calls computed on the way in) | 🔒 | users with sequenced strains and no gene table; needs an annotation step such as antiSMASH (product roadmap A3) |
| Saved views and notes per user in the app | 🔒 | a second regular user (it needs logins, which is the production web stack above) |
| Usage analytics for the app | 🔒 | the online copy exists (Phase 7), but nothing needs the numbers yet. If its owner ever does, the README will say what is counted. Streamlit's own statistics are switched off (`.streamlit/config.toml`) |
| Pinned dependency versions for development (lock file for Python) | 🔒 | the first time an upgrade breaks a test, which continuous integration with the newest packages (Phase 8) notices the day it happens (`renv.lock` already pins the R side, and since Phase 7 `app/requirements.txt` pins the online copy) |
| A Python package on PyPI (`pip install strainscope`) | 🔒 | other code wants to import StrainScope's functions; StrainScope is a project to build and learn from, with data and documents, more than a library (Phase 8, decision list) |
| A permanent identifier (DOI) for each release, through Zenodo | 🔒 | someone cites a fixed version in a paper; `CITATION.cff` already gives the version and date |
| The container image in a registry (ready to download) | 🔒 | people want to run the container without building it, or a host requires a ready image; the build is tested at every push |
| DIABLO (R) in continuous integration | 🔒 | a change to `R/diablo_integration.R` or `renv.lock`; installing R and mixOmics on three systems at every push would take longer than everything else together, and the committed DIABLO results are checked by the tests and `compare` |
| Dependabot's security-update pull requests | 🔒 | a branch setup in which master takes pull requests directly; they always go to the default branch, which would skip develop, so only the alerts are on (Phase 8 §13) |
| Excel workbooks as a dataset's input (`.xlsx`) | 🔒 | a lab whose system exports only workbooks; it needs another package and rules for sheets, merged cells and dates, while every spreadsheet program already saves CSV (Phase 9 §3) |
| One combined table instead of three | 🔒 | people keep their strains in one wide sheet and find splitting it a burden; it needs a way to tell a gene column from a compound column, such as a prefix on every name |
| The MCP server's `config` helper for a dataset | 🔒 | someone wants their assistant app to answer about their own dataset; the server already reads `STRAINSCOPE_DATASET` and says "your own data", so `config --dataset NAME` would only add the setting to the app's entry |
| Mechanisms for your own genes and compounds | 🔒 | a dataset of real strains whose important columns the domain model doesn't know; they'd be added to `src/strainscope/ontology.py` (or a file of the user's own read beside it), product roadmap C5 |
| Other groups of microbes (viruses, protozoa) in a dataset | 🔒 | a domain model with their weapons and a molecular layer they share; today a dataset takes the four kingdoms of Phase 1 only |
| A queue for many visitors at once on a shared copy | 🔒 | more visitors want to run datasets than one run at a time serves; a real queue belongs to a hosted product with logins (product roadmap B5 and D7) |

## Version tags

A **tag** is a bookmark on one exact commit, named with a version number, so anyone can return to exactly that state later. Tags mark the points where the project is usable end to end at a new level:

- **v0.1.0**: data foundation and integration (Phases 0 to 3), taking you from a blank laptop to a graded multi-omics signature.
- **v0.2.0**: the analysis is complete (Phases 4 and 5), with predictions and the knowledge graph. *Released with Phase 5.*
- **v0.3.0**: usable by anyone (Phases 6 and 6b), with the app and Ask StrainScope. *Released with Phase 6b.*
- **v1.0.0**: the first complete release (Phases 7 and 8): online, with the AI layer, the MCP server, the one-command pipeline, tests on every system at every push, and the files for reuse and citation. *Released with Phase 8*, after every automatic test had passed on the tagged commit. Phase 7 itself got no tag; the online copy shows the latest release and says when newer changes are listed under *[Unreleased]* in `CHANGELOG.md`.
- **v1.1.0**: every phase on your own data (Phase 9): datasets, their checks, and the Workflow page. The second number moves because something new arrived and nothing that worked before changed. *Released with Phase 9*, after the automatic tests passed.

Between those, **patch releases** (the third number: v0.1.1, v0.1.2, ...) ship fixes found through real use. Each one is tested, documented in [`CHANGELOG.md`](../CHANGELOG.md) and the [Handbook](HANDBOOK.md), and tagged like any other version. So far:

- **v0.1.1**: the safety gate also checks new, not-yet-added files, and every documented command, commit and tag message uses plain keyboard characters ([Handbook Stage 7.1](HANDBOOK.md#stage-71-fix-release-v011-a-safer-safety-gate-and-copy-safe-commands)).

Tag messages, like commit messages, use plain keyboard characters only (see [`docs/01-setup.md` Part H](01-setup.md#copy-commands-safely-plain-keyboard-characters-only)).

The steps for creating and pushing a tag are in the commit ritual of the phase that earns it (and in [`docs/01-setup.md` Part H](01-setup.md#part-h-initialise-git-and-push-with-the-master--beta--develop-workflow)).

## How this document is maintained

At the end of every phase, in the same commit: flip the phase's status mark, link its guide, move any deferred item whose trigger has fired from 🔒 to ⏳, update the stage in the [Handbook](HANDBOOK.md) and the README's build log, and regenerate the journey map (`python figures/make_illustrations.py` after editing its `STAGES` list). If this roadmap and the repository ever disagree, that's a bug to fix.
