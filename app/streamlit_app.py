"""
app/streamlit_app.py: the StrainScope app (Phase 6).
====================================================
Start it from the project folder, with the virtual environment active:

    python -m streamlit run app/streamlit_app.py

A browser tab opens at http://localhost:8501. Stop the app with Ctrl+C in the
terminal. The guide is docs/07-app.md.

THIS FILE
---------
It sets the page title and icon, draws the sidebar, and lists the pages. Each
page is its own small script in app/views/. Streamlit runs this file first on
every click, then the page that is open.

WHAT THE APP READS (and never changes)
--------------------------------------
  artifacts/integration/, artifacts/model/, artifacts/graph/   the committed results of Phases 3 to 5
  data/processed/strainscope.duckdb                              the database (read-only)
  docs/QUERY_COOKBOOK.md                                         the recipes in the SQL console
The only things that write files are the database build (on the Home and Data
pages) and the real-data fetch (on the Data page). They run the same scripts
you'd run by hand (src/strainscope/service.py, PIPELINES).
"""
import streamlit as st

import ui

st.set_page_config(page_title="StrainScope", page_icon=str(ui.ROOT / "docs" / "img" / "strainscope_icon.svg"),
                   layout="wide", menu_items={"About": "StrainScope: multi-omics, machine learning and a "
                                                       "knowledge graph for beneficial microbes. Simulated data. "
                                                       f"Source and guides: {ui.REPO}"})
st.logo(str(ui.ROOT / "docs" / "img" / "strainscope_wordmark.svg"), size="large",
        icon_image=str(ui.ROOT / "docs" / "img" / "strainscope_icon.svg"), link=ui.REPO)

# Each page's web address comes from its file name (app/views/ranking.py is
# http://localhost:8501/ranking). Keeping the two the same means one name for
# everything, and older Streamlit test runners need it to find a page (docs/07-app.md section 12).
pages = {
    "StrainScope": [st.Page(ui.PAGES["home"], title="Home", icon=":material/home:", default=True)],
    "Explore": [
        st.Page(ui.PAGES["ranking"], title="Ranking", icon=":material/format_list_numbered:"),
        st.Page(ui.PAGES["strain"], title="Strain page", icon=":material/coronavirus:"),
        st.Page(ui.PAGES["graph"], title="Knowledge graph", icon=":material/hub:"),
        st.Page(ui.PAGES["integration"], title="Integration", icon=":material/join_inner:"),
    ],
    "Work with data": [
        st.Page(ui.PAGES["data"], title="Data", icon=":material/database:"),
        st.Page(ui.PAGES["sql"], title="SQL console", icon=":material/terminal:"),
    ],
}
page = st.navigation(pages)

with st.sidebar:
    if ui.upload() is not None:
        n = len(ui.upload()["scores"])
        st.radio("Strains shown", ["library", "upload"], key="source", horizontal=True,
                 format_func=lambda s: "Library (600)" if s == "library" else f"My upload ({n})",
                 help="Ranking and Strain page show either the simulated library or the strains you uploaded "
                      "on the Data page. Your upload stays in this browser tab and is never saved.")
    st.caption("Simulated data · read-only database · "
               f"[guide]({ui.DOCS}/07-app.md) · [Handbook]({ui.DOCS}/HANDBOOK.md)")

page.run()
