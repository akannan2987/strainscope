"""app/views/sql_console.py: ask the database anything in SQL, safely.
The recipes of docs/QUERY_COOKBOOK.md are one click away; every query runs
through the service layer's four guards (read-only, no file access, a time
limit, a row limit)."""
import streamlit as st

import ui
from strainscope import service as sv

st.title("SQL console")
st.markdown(
    "SQL is the language databases understand. Each question here runs against "
    "`data/processed/strainscope.duckdb`, **read-only**: you can look at anything and change nothing. "
    f"New to SQL? Start with the recipes below; each one is explained in "
    f"{ui.doc('QUERY_COOKBOOK.md', 'docs/QUERY_COOKBOOK.md')}.")
if not ui.has_database():
    ui.needs("The console needs the database.", "python src/strainscope/harmonize.py")
    st.stop()

recipes = ui.recipes()
present = set(ui.tables()["table"])
sections = list(dict.fromkeys(r.section for r in recipes))


def _use_recipe():
    """Copy the chosen recipe into the editor (a callback, so it runs before
    the editor is drawn: the only moment its text may be replaced)."""
    pick = st.session_state.get("recipe")
    if pick is not None:
        st.session_state["sql_text"] = recipes[pick].sql


if "sql_text" not in st.session_state:
    st.session_state["sql_text"] = recipes[0].sql if recipes else "SELECT * FROM phenotype LIMIT 5;"

with st.container(border=True):
    st.markdown("**Recipes from the Query Cookbook**")
    c1, c2 = st.columns([1, 2])
    section = c1.selectbox("Section", sections, key="recipe_section")
    options = [i for i, r in enumerate(recipes) if r.section == section]

    def _label(i):
        missing = [t for t in recipes[i].tables if t not in present]
        return recipes[i].question + (" (needs real data)" if missing else "")

    c2.selectbox("Question", options, format_func=_label, key="recipe")
    chosen = recipes[st.session_state["recipe"]] if st.session_state.get("recipe") in options else recipes[options[0]]
    if chosen.note:
        st.caption("What to expect: " + ui.plain(chosen.note))
    st.button("Put this recipe in the editor", on_click=_use_recipe)

st.markdown("<style>textarea {font-family: ui-monospace, Consolas, Menlo, monospace !important;}</style>",
            unsafe_allow_html=True)                 # SQL is easier to read in a fixed-width font
sql = st.text_area("Your query", key="sql_text", height=200,
                   help="One query, or several separated by ';' (only the last one's result is shown).")
run = st.button("Run", type="primary")
if run:
    st.session_state["sql_result"] = (sql, sv.query_database(sql, ui.DB_PATH))
if "sql_result" in st.session_state:
    ran, result = st.session_state["sql_result"]
    if ran != sql:
        st.caption("The editor has changed since this result. Press Run to update it.")
    if result.error:
        st.error(result.error)
    elif result.table is not None:
        st.caption(f"{len(result.table):,} row(s) in {result.seconds:.2f} s"
                   + (f". Only the first {sv.SQL_MAX_ROWS:,} rows are returned; add a LIMIT or GROUP BY."
                      if result.truncated else ""))
        st.dataframe(result.table, hide_index=True, width="stretch")
        st.download_button("Download the result (CSV)", result.table.to_csv(index=False), "query_result.csv", "text/csv")

with st.expander("Tables in the database"):
    t = ui.tables()
    for group, grp in t.groupby("group", sort=False):
        st.markdown(f"**{group}**: " + ", ".join(f"`{n}` ({r:,})" for n, r in zip(grp["table"], grp["rows"])))
    st.caption("See a table's columns: `DESCRIBE phenotype;`  ·  Every table: `SHOW TABLES;`")

with st.expander("Why you can't break anything here"):
    st.markdown(
        f"1. The database is opened **read-only**, so CREATE, INSERT, UPDATE and DELETE are refused.\n"
        f"2. **File access is off**: a query can't read or write files on the computer, and that setting is "
        f"locked so a query can't switch it back on.\n"
        f"3. A query still running after **{sv.SQL_TIMEOUT_S} seconds** is stopped.\n"
        f"4. At most **{sv.SQL_MAX_ROWS:,} rows** come back.\n\n"
        "The terminal console (`python src/strainscope/sql.py`) opens the database the same way, read-only "
        "with file access off; there, Ctrl+C stops a long query.")
