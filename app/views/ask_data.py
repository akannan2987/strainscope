"""app/views/ask_data.py: Ask the data (Phase 7). A question about the data in
plain words, answered with a SQL query you can see: a tested recipe from the
Query Cookbook, or, when a language model is set up and no recipe fits, a
query the model wrote. Either way the query runs through the SQL console's
four guards (a model's query passes a fifth guard first), and the model
never sees a row. The engine is src/strainscope/ask_data.py; the guide is
docs/08-deployment-ai.md (section 6)."""
import streamlit as st

import ui
from strainscope import ask_data as qa
from strainscope import llm

BOX = {qa.RECIPE: st.success, qa.WRITTEN: st.success, qa.CLOSEST: st.warning, qa.REFUSED: st.info,
       qa.VAGUE: st.info}
ICON = {qa.RECIPE: ":material/menu_book:", qa.WRITTEN: ":material/edit_note:", qa.CLOSEST: ":material/help:",
        qa.REFUSED: ":material/block:", qa.VAGUE: ":material/edit:"}


def _set_question(text: str) -> None:
    """Button callback: put a question in the box (callbacks run before the
    page reruns, which is when Streamlit allows changing a widget's value)."""
    st.session_state["data_question"] = text


st.title("Ask the data")
st.markdown("A question about the data in plain words, answered with a **SQL query you can see** and the table "
            "it returns. The answer comes from a tested recipe of the Query Cookbook whenever one fits. The "
            "database is read-only here, as everywhere in the app.")
ui.simulated_note()
if not ui.has_database():
    ui.needs("Ask the data needs the database.", "python src/strainscope/harmonize.py")
    st.stop()

cfg = llm.settings()
question = st.text_input("Your question", key="data_question", placeholder="e.g. Which strains are borderline?",
                         help="Press Enter to ask. Name what you want to see: strains, a kingdom, a gene, "
                              "a model, the graph.")
use_model = False
if cfg.on:
    use_model = st.toggle(f"When no recipe fits, let {cfg.model} write a query", value=True, key="data_write",
                          help="The model is sent your question, the table and column names and a few recipes "
                               "as examples. It never sees a row of data. Its query is checked by five guards "
                               "and shown above the result.")

if not question.strip():
    st.markdown("**Try one of these:**")
    cols = st.columns(2)
    for n, q in enumerate(qa.STARTERS):
        cols[n % 2].button(q, key=f"data_starter_{n}", on_click=_set_question, args=(q,), width="stretch")
else:
    with st.spinner("Looking for a recipe and running it..."):
        answer = qa.ask(question, ui.DB_PATH, write=use_model, cfg=cfg if use_model else None)
    BOX[answer.verdict](answer.message, icon=ICON[answer.verdict])
    if answer.note and answer.verdict == qa.CLOSEST and use_model:
        st.caption(f"No new query: {answer.note}")
    elif answer.verdict == qa.CLOSEST and not cfg.on:
        st.caption("With a language model switched on, this page writes a new query for a question like this "
                   f"one ({ui.doc('08-deployment-ai.md', 'docs/08-deployment-ai.md')}, section 10). "
                   "**About this copy** shows whether one is.")

    if answer.sql:
        if answer.verdict == qa.WRITTEN:
            st.caption(f"Written by {answer.written_by} from your question and the table names. Read it before "
                       "you trust the result.")
        st.code(answer.sql, language="sql")
        if answer.verdict in (qa.RECIPE, qa.WRITTEN) and st.button("Open this query in the SQL console",
                                                                   icon=":material/terminal:"):
            st.session_state["sql_handoff"] = answer.sql
            st.switch_page(ui.PAGES["sql"])
    if answer.result is not None:
        if answer.result.error:
            st.error(answer.result.error)
        else:
            st.caption(qa.summary(answer.result) + f" ({answer.result.seconds:.2f} s)")
            if answer.table is not None and not answer.table.empty:
                st.dataframe(answer.table, hide_index=True, width="stretch")
                st.download_button("Download the result (CSV)", answer.table.to_csv(index=False),
                                   "strainscope_answer.csv", "text/csv")

    if answer.options:
        label = "Other recipes close to it:" if answer.verdict in (qa.RECIPE, qa.WRITTEN) else "The closest recipes:"
        st.markdown(f"**{label}**")
        for h in answer.options:
            st.button(h.recipe.question, key=f"data_option_{h.number}", on_click=_set_question,
                      args=(h.recipe.question,), help=f"Query Cookbook, section {h.recipe.section}",
                      width="stretch")
    ui.suggest_fix("Ask the data", question, answer.verdict,
                   [answer.recipe.recipe.question] if answer.recipe else [h.recipe.question for h in answer.options])

st.divider()
st.caption(f"{len(qa.recipe_index().recipes)} tested recipes from "
           f"{ui.doc('QUERY_COOKBOOK.md', 'docs/QUERY_COOKBOOK.md')}. {ui.model_note(cfg)}. How it works: "
           f"{ui.doc('08-deployment-ai.md', 'docs/08-deployment-ai.md')}. The same from a terminal: "
           "`python src/strainscope/ask_data.py \"your question\"`.")
