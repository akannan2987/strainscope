"""
app/ui.py: what every page of the app shares.
=============================================
  * where the data lives (and how tests point the app somewhere else),
  * the shared mode for a copy other people use (Phase 7): the first start
    that builds the database, and messages a visitor can act on,
  * reading the committed results once and keeping them in memory (caching),
  * which strains are being shown (the library, or your upload),
  * small building blocks: the simulated-data note, help boxes, links to
    the guides, the explanation lines, the "suggest a fix" link under an
    answer, and the live log of a pipeline run.

How Streamlit runs a page, in one paragraph: every click, every slider move
and every new selection runs the page's script again from the top. That
sounds slow, but the expensive things (reading files, loading the graph) are
cached: the first run does the work, later runs reuse the answer as long as
the file behind it hasn't changed. What must survive a rerun (your upload,
the strain you picked) lives in st.session_state, a small notebook Streamlit
keeps for each browser tab. docs/07-app.md section 1 draws all this.
"""
from __future__ import annotations

import os
import re
import sys
import threading
import urllib.parse
from pathlib import Path

import pandas as pd
import streamlit as st

APP = Path(__file__).resolve().parent
ROOT = APP.parent
sys.path.insert(0, str(ROOT / "src"))
from strainscope import service as sv  # noqa: E402
from strainscope.sources.base import load_env  # noqa: E402

load_env()          # settings in the git-ignored .env count too (the shell, or a host's secrets, win)

# Where to read from. Tests (and anyone curious) can point the app at another
# database or results folder with these two environment variables.
DB_PATH = Path(os.environ.get("STRAINSCOPE_DB", sv.DB_PATH))
ARTIFACTS = Path(os.environ.get("STRAINSCOPE_ARTIFACTS", sv.ARTIFACTS))
# "public" is for a copy other people can reach (Phase 7): it hides the
# real-data buttons, builds the database by itself on the first start and
# allows no rebuild after that, and caps the AI features' requests per day.
# The default, "local", is for your own computer. On Streamlit Community
# Cloud the setting comes from the app's secrets: Streamlit puts every
# top-level secret into the environment when the app starts.
PUBLIC = os.environ.get("STRAINSCOPE_MODE", "local").strip().lower() == "public"

REPO = "https://github.com/akannan2987/strainscope"
DOCS = f"{REPO}/blob/master/docs"
MARK = {"mechanism": ":green-badge[how it works]", "data only": ":orange-badge[statistics only]",
        "missing": ":gray-badge[lacks]"}
SYMBOL = {"mechanism": "+", "data only": "?", "missing": "-"}


# =============================================================================
# Reading, with caching keyed on the file's modification time
# =============================================================================

def stamp(path: Path) -> float:
    """When a file last changed (0 if it doesn't exist). Passing this into a
    cached function means 'the answer is stale once the file changes'."""
    return path.stat().st_mtime if path.exists() else 0.0


@st.cache_data(show_spinner=False, max_entries=64)
def _artifact(name: str, changed: float, folder: str) -> pd.DataFrame | None:
    return sv.read_artifact(name, Path(folder))


def artifact(name: str) -> pd.DataFrame | None:
    """A committed result table, e.g. artifact('model/predictions.csv')."""
    return _artifact(name, stamp(ARTIFACTS / name), str(ARTIFACTS))


@st.cache_data(show_spinner=False, max_entries=4)
def _card(changed: float, folder: str) -> dict | None:
    return sv.model_card(Path(folder))


def card() -> dict | None:
    return _card(stamp(ARTIFACTS / "model" / "model_card.json"), str(ARTIFACTS))


@st.cache_data(show_spinner=False, max_entries=4)
def _tables(changed: float, db: str) -> pd.DataFrame:
    return sv.database_tables(Path(db))


def tables() -> pd.DataFrame:
    """Every table in the database with its row count."""
    return _tables(stamp(DB_PATH), str(DB_PATH))


@st.cache_data(show_spinner=False, max_entries=4)
def _status(db_changed: float, art_changed: float, db: str, folder: str, requests_today: str):
    return sv.status(Path(db), Path(folder))


def status():
    """The health check, read again when the database, the results or the
    number of model requests made today changes (so its AI line is current)."""
    from strainscope import llm
    return _status(stamp(DB_PATH), stamp(ARTIFACTS / "graph" / "edges.csv"), str(DB_PATH), str(ARTIFACTS),
                   llm.daily_cap().describe())


def has_database() -> bool:
    return {"genomics", "metabolomics", "phenotype"} <= set(tables()["table"])


# =============================================================================
# The first start of a shared copy (Phase 7)
# =============================================================================
# A hosted copy starts from the repository, which holds the results
# (artifacts/) but no database (data/ is never committed). Hosts also wipe
# their disk when an app restarts or wakes from sleep. So in shared mode the
# app builds the database itself, once, before the first page is drawn. The
# lock makes a second visitor who arrives during the build wait for it
# instead of starting another.

_FIRST_START = threading.Lock()
_first_start_tried = False       # one attempt per running copy: a failed build isn't retried on every click


def build_database_quietly() -> tuple[bool, list[str]]:
    """Run the 'database' pipeline (about 15 seconds) and return (finished, log)."""
    lines, ok = [], False
    for step, label, line in sv.run_pipeline("database"):
        lines.append(line)
        if step is None:
            ok = label == "done"
    return ok, lines


def first_start() -> None:
    """Shared mode only: build the database if there isn't one yet. If the
    build fails, it isn't tried again until the copy restarts (the owner
    reboots it); the pages that read the committed results still work."""
    global _first_start_tried
    if not PUBLIC or _first_start_tried or has_database():
        return
    with st.status("Preparing this copy: building the database from the committed results "
                   "(about 15 seconds, once)...", expanded=False) as box:
        with _FIRST_START:
            core = {"genomics", "metabolomics", "phenotype"}
            if not _first_start_tried and not core <= set(sv.database_tables(DB_PATH)["table"]):
                _first_start_tried = True               # checked again inside the lock: someone may have built it
                ok, log = build_database_quietly()
                if not ok:
                    box.update(label="The database couldn't be built. The pages that read the committed "
                                     "results still work.", state="error", expanded=True)
                    st.code("\n".join(log[-30:]), language=None)
                    return
        st.cache_data.clear()
        st.cache_resource.clear()
        box.update(label="This copy is ready.", state="complete")


@st.cache_resource(show_spinner="Loading the knowledge graph (a second or two, once)...", max_entries=2)
def _graph(changed: float, db_changed: float, folder: str, db: str):
    return sv.load_full_graph(Path(folder), Path(db))


def graph():
    """The Phase 5 graph, loaded once and shared by every page and tab.
    Nothing in the app changes it (uploads get their own copy)."""
    return _graph(stamp(ARTIFACTS / "graph" / "edges.csv"), stamp(DB_PATH), str(ARTIFACTS), str(DB_PATH))


@st.cache_data(show_spinner=False, max_entries=4)
def _layout(changed: float, folder: str) -> pd.DataFrame | None:
    import charts
    nodes, edges = sv.read_artifact("graph/nodes.csv", Path(folder)), sv.read_artifact("graph/edges.csv", Path(folder))
    return None if nodes is None else charts.knowledge_layout(nodes, edges)


def knowledge_layout() -> pd.DataFrame | None:
    return _layout(stamp(ARTIFACTS / "graph" / "edges.csv"), str(ARTIFACTS))


@st.cache_data(show_spinner=False, max_entries=4)
def _recipes(changed: float) -> list:
    return sv.cookbook_recipes()


def recipes() -> list:
    return _recipes(stamp(sv.COOKBOOK))


@st.cache_data(show_spinner=False, max_entries=32)
def _medians(changed: float, db: str, folder: str) -> dict:
    return sv.library_medians(Path(db), Path(folder))


def medians() -> dict:
    return _medians(stamp(DB_PATH), str(DB_PATH), str(ARTIFACTS))


# =============================================================================
# Which strains are shown: the library, or your upload
# =============================================================================

def upload() -> dict | None:
    """The scored upload kept for this browser tab, if there is one."""
    return st.session_state.get("upload")


def showing_upload() -> bool:
    return upload() is not None and st.session_state.get("source", "library") == "upload"


def ranking() -> pd.DataFrame | None:
    """The ranking for whatever is being shown, with the same columns either way:
    rank, strain_id, kingdom, probability, predicted_effective (+ is_effective for the library)."""
    if showing_upload():
        return upload()["scores"]
    pred = artifact("model/predictions.csv")
    if pred is None:
        return None
    pred = pred.assign(band=pred["probability"].map(sv.confidence_band))
    expl = artifact("graph/explanations.csv")
    if expl is not None:
        paths = expl.groupby("strain_id")["mechanism_paths"].first()
        pred = pred.assign(mechanism_paths=pred["strain_id"].map(paths).fillna(0).astype(int))
    nodes = artifact("graph/nodes.csv")
    if nodes is not None:
        genus = nodes[nodes["node_type"] == "Strain"].set_index("label")["genus"]
        pred = pred.assign(genus=pred["strain_id"].map(genus))
    return pred


def explanation(strain_id: str) -> pd.DataFrame:
    """One strain's reasons (rows like artifacts/graph/explanations.csv)."""
    if showing_upload():
        table = upload().get("explanations")
    else:
        table = artifact("graph/explanations.csv")
    if table is None or not len(table):
        return pd.DataFrame(columns=["kind", "text", "path", "provenance", "mechanism_paths"])
    return table[table["strain_id"] == strain_id]


def strain_graph():
    """The graph that holds the strains being shown."""
    return upload()["graph"] if showing_upload() else graph()


def show_source(source: str) -> None:
    """Switch between the library and the upload. Used as a button callback:
    callbacks run before the page reruns, which is the moment Streamlit
    allows changing a widget's value (here the sidebar's 'Strains shown')."""
    st.session_state["source"] = source
    st.session_state.pop("current_strain", None)


def forget_upload() -> None:
    for key in ("upload", "upload_result", "upload_fingerprint", "current_strain"):
        st.session_state.pop(key, None)
    st.session_state["source"] = "library"


def pick_strain(strain_id: str) -> None:
    """Remember a strain and open its page (used by the ranking table)."""
    st.session_state["current_strain"] = strain_id
    st.switch_page(PAGES["strain"])


# Page files, so pages can link to each other by name.
PAGES = {"home": "views/home.py", "about": "views/about.py", "ask": "views/ask.py",
         "ask_data": "views/ask_data.py", "ask_graph": "views/ask_graph.py",
         "ranking": "views/ranking.py", "strain": "views/strain.py",
         "graph": "views/knowledge_graph.py", "integration": "views/integration.py",
         "data": "views/data.py", "sql": "views/sql_console.py"}


# =============================================================================
# Small building blocks
# =============================================================================

def simulated_note() -> None:
    st.caption("All 600 library strains are simulated (Phase 1). The scores show the workflow working; "
               "they say nothing about real microbes.")


def doc(path: str, label: str | None = None) -> str:
    """A markdown link to a guide on GitHub, e.g. doc('06-knowledge-graph.md#7-...')."""
    return f"[{label or path.split('#')[0]}]({DOCS}/{path})"


def plain(markdown: str) -> str:
    """Markdown links turned into their text (the cookbook's relative links
    point at files, which a web page can't follow)."""
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown)


def needs(what: str, fix: str) -> None:
    """A friendly stop sign: what's missing and the one thing that fixes it.
    On a shared copy a visitor can't run commands, so the message says what
    they can do instead (and the command is kept for the owner)."""
    if PUBLIC:
        st.info(f"{what}\n\nThis shared copy builds what it needs when it starts, so reload the page in a "
                "minute. If the message stays, **About this copy** (in the sidebar) shows what's missing.")
        st.caption(f"For the owner of this copy: `{fix.splitlines()[0]}`")
        return
    st.info(f"{what}\n\nFix: open the **Data** page and build the database, or run:")
    st.code(fix, language="bash")


ISSUES = f"{REPO}/issues/new"


def feedback_link(page: str, question: str, verdict: str, shown: list[str]) -> str:
    """A link that opens a new GitHub issue with the question already filled
    in, so an answer that missed can become a golden question or a fix to the
    documents. Nothing is sent until the person reads it and presses Submit
    on GitHub (an issue there is public)."""
    body = (f"**Page:** {page}\n**Question:** {question}\n**What it said:** {verdict}\n"
            + ("**What it showed:**\n" + "\n".join(f"- {x}" for x in shown[:5]) + "\n" if shown else "")
            + "\n**What I expected instead:**\n\n")
    query = urllib.parse.urlencode({"title": f"{page}: {question[:80]}", "body": body})
    return f"{ISSUES}?{query}"


def suggest_fix(page: str, question: str, verdict: str, shown: list[str]) -> None:
    """The small "Not what you needed?" line under an answer."""
    st.link_button("Not what you needed? Suggest a fix", feedback_link(page, question, verdict, shown),
                   icon=":material/flag:", type="tertiary",
                   help="Opens a GitHub issue with your question filled in. You can edit it before sending, and "
                        "nothing is sent unless you press Submit there. Issues on GitHub are public.")


def model_note(cfg) -> str:
    """One line saying whether a language model is set up, for page footers,
    with a link to the how-to when none is."""
    from strainscope import llm
    if not cfg.on:
        who = "for the owner of this copy: " if PUBLIC else ""
        return f"Language model: {cfg.describe()}; {who}{doc('LANGUAGE_MODEL.md', 'how to switch one on')}"
    return f"Language model: {cfg.describe()}" + (f"; {llm.daily_cap().describe()}" if PUBLIC else "")


def reason_line(row) -> str:
    """One explanation row as a line of markdown with a coloured label."""
    kind = row["kind"] if isinstance(row, dict) else row.kind
    text = row["text"] if isinstance(row, dict) else row.text
    return f"{MARK.get(kind, '')} {SYMBOL.get(kind, '')} {text}"


def run_pipeline(name: str) -> bool:
    """Run one of the service layer's pipelines with a live log. Returns True
    when every step finished. Caches refresh by themselves afterwards, because
    each one is keyed on the files' modification times."""
    spec = sv.PIPELINES[name]
    lines: list[str] = []
    ok = False
    with st.status(f"{spec['title']} ({spec['takes']})", expanded=True) as box:
        log = st.empty()
        for step, label, line in sv.run_pipeline(name):
            if step is None:
                ok = label == "done"
                lines.append(line)
            else:
                lines.append(line)
                box.update(label=f"Step {step} of {len(spec['steps'])}: {label}")
            log.code("\n".join(lines[-40:]), language=None)
        box.update(label=("Finished: " if ok else "Stopped: ") + spec["title"],
                   state="complete" if ok else "error", expanded=not ok)
    if ok:
        st.cache_resource.clear()        # the graph and the model are re-read on the next run
        st.success("Done. Every page now reads the new files.")
    return ok
