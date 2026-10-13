"""
app/streamlit_app.py: the StrainScope app (Phases 6 to 9).
==========================================================
Start it from the project folder, with the virtual environment active:

    python -m streamlit run app/streamlit_app.py

A browser tab opens at http://localhost:8501. Stop the app with Ctrl+C in the
terminal. The guides are docs/07-app.md, docs/07b-docs-assistant.md (Ask
StrainScope) and docs/08-deployment-ai.md (the online copy, Ask the data,
Ask the graph and the plain-language explanations).

The same file is the entry point of the online copy on Streamlit Community
Cloud, which installs app/requirements.txt (exact versions) and runs it in
shared mode (STRAINSCOPE_MODE=public, from the app's secrets).

THIS FILE
---------
It sets the page title and icon, draws the sidebar (with the dataset every
page shows, Phase 9), and lists the pages. Each page is its own small script
in app/views/. Streamlit runs this file first on every click, then the page
that is open.

WHAT THE APP READS (and never changes)
--------------------------------------
  artifacts/integration/, artifacts/model/, artifacts/graph/   the committed results of Phases 3 to 5
  data/processed/strainscope.duckdb                              the database (read-only)
  data/processed/datasets/<name>/                                a dataset's own data and results (Phase 9)
  docs/QUERY_COOKBOOK.md                                         the recipes in the SQL console
  README.md, docs/*.md, the docstrings in src/ and app/          what Ask StrainScope answers from
The only things that write files are the database build (on the Home and Data
pages, and by itself on the first start of a shared copy), the rebuild from
scratch and the real-data fetch (on the Data page), and the Workflow page,
which saves datasets and runs every phase on them inside their own folders.
They run the same scripts you'd run by hand (src/strainscope/service.py,
PIPELINES; src/strainscope/pipeline.py, the one-command pipeline of Phase 8;
and src/strainscope/datasets.py, the datasets of Phase 9).
"""
import streamlit as st

import ui

st.set_page_config(page_title="StrainScope", page_icon=str(ui.ROOT / "docs" / "img" / "strainscope_icon.svg"),
                   layout="wide", menu_items={"About": "StrainScope: multi-omics, machine learning and a "
                                                       "knowledge graph for beneficial microbes. Simulated data. "
                                                       f"Source and guides: {ui.REPO}"})
st.logo(str(ui.ROOT / "docs" / "img" / "strainscope_wordmark.svg"), size="large",
        icon_image=str(ui.ROOT / "docs" / "img" / "strainscope_icon.svg"), link=ui.REPO)
ui.readable_colours()            # small text dark enough to read (the accessibility check, Phase 8)

# Each page's web address comes from its file name (app/views/ranking.py is
# http://localhost:8501/ranking). Keeping the two the same means one name for
# everything, and older Streamlit test runners need it to find a page (docs/07-app.md section 12).
pages = {
    "StrainScope": [
        st.Page(ui.PAGES["home"], title="Home", icon=":material/home:", default=True),
        st.Page(ui.PAGES["about"], title="About this copy", icon=":material/monitor_heart:"),
    ],
    "Ask": [
        st.Page(ui.PAGES["ask"], title="Ask StrainScope", icon=":material/question_answer:"),
        st.Page(ui.PAGES["ask_data"], title="Ask the data", icon=":material/table_chart:"),
        st.Page(ui.PAGES["ask_graph"], title="Ask the graph", icon=":material/account_tree:"),
    ],
    "Explore": [
        st.Page(ui.PAGES["ranking"], title="Ranking", icon=":material/format_list_numbered:"),
        st.Page(ui.PAGES["strain"], title="Strain page", icon=":material/coronavirus:"),
        st.Page(ui.PAGES["graph"], title="Knowledge graph", icon=":material/hub:"),
        st.Page(ui.PAGES["integration"], title="Integration", icon=":material/join_inner:"),
    ],
    "Work with data": [
        st.Page(ui.PAGES["workflow"], title="Workflow", icon=":material/play_circle:"),
        st.Page(ui.PAGES["data"], title="Data", icon=":material/database:"),
        st.Page(ui.PAGES["sql"], title="SQL console", icon=":material/terminal:"),
    ],
}
page = st.navigation(pages)
ui.first_start()                 # shared mode: build the database on the first visit (Phase 7)
ui.tidy_shared_copy()            # shared mode: delete visitors' datasets an hour after their last use (Phase 9)


def _pick_dataset() -> None:
    """The sidebar box changed: switch every page to that dataset."""
    ui.choose_dataset(st.session_state["sidebar_dataset"])


with st.sidebar:
    choices = [ui.LIBRARY, *ui.dataset_names()]
    st.session_state["sidebar_dataset"] = ui.dataset() or ui.LIBRARY
    st.selectbox("Dataset", choices, key="sidebar_dataset", on_change=_pick_dataset,
                 format_func=lambda n: ui.label(n),
                 help="Which data every page shows: the built-in simulated library, or a dataset made on the "
                      "Workflow page (your own data, or a fresh simulation).")
    if ui.upload() is not None:
        n = len(ui.upload()["scores"])
        whole = f"All {ui.info().get('strains', '')} strains".replace("  ", " ")
        st.radio("Strains shown", ["library", "upload"], key="source", horizontal=True,
                 format_func=lambda s: whole if s == "library" else f"My upload ({n})",
                 help="Ranking and Strain page show either the dataset's strains or the strains you uploaded "
                      "on the Data page and scored with its model. Your upload is kept for this browser tab "
                      "only and never saved.")
    kind = {"library": "Simulated data", "simulated": "Simulated data", "yours": "Your data"}[ui.info()["kind"]]
    st.caption(("Shared copy · " if ui.PUBLIC else "") + f"{kind} · read-only database · "
               f"[guide]({ui.DOCS}/07-app.md) · [Handbook]({ui.DOCS}/HANDBOOK.md)")

page.run()
