"""app/views/home.py: the front page. What StrainScope is, the headline
numbers, where to go next, and a health check of everything the app reads."""
import streamlit as st

import ui

st.title("StrainScope")
st.markdown(
    "Hundreds of candidate microbes could protect a crop, and a lab can only test a few dozen properly each "
    "season. StrainScope reads each strain's genes and the chemicals it makes, predicts which strains are "
    "worth testing, and shows **why**, with a source for every step of the reasoning.")
ui.simulated_note()

checks = ui.status()
if not ui.has_database():
    st.warning("There's no database yet, so the SQL console, the example upload and some numbers are "
               "missing. The rankings, graph and charts already work, because they read the committed "
               "results in `artifacts/`.")
    if st.button("Build the database now (about 15 seconds)", type="primary"):
        ui.run_pipeline("database")

# -- the headline numbers ------------------------------------------------------
pred, card = ui.artifact("model/predictions.csv"), ui.card()
summary = ui.artifact("graph/graph_summary.csv")
cols = st.columns(4)
if pred is not None:
    eff = int(pred["is_effective"].sum())
    cols[0].metric("Strains in the library", f"{len(pred)}", f"{eff} effective ({eff / len(pred):.0%})",
                   delta_color="off", delta_arrow="off", help="Effective = disease suppressed by at least 65 % in the simulated trial.")
if card is not None:
    perf = card["cross_validated_performance"]
    cols[1].metric("Model error (balanced)", f"{perf['ber']:.3f}", f"AUC {perf['auc']:.3f}", delta_color="off", delta_arrow="off",
                   help="Measured on strains the model hadn't seen (5 folds x 10 repeats). A coin scores 0.50.")
    top = card["top_n_check"]
    cols[2].metric(f"Effective among the top {top['n']}", f"{top['truly_effective']}",
                   f"chance: about {top['expected_by_chance']:.0f}", delta_color="off", delta_arrow="off",
                   help="If a team tested the 50 best-ranked strains, how many would really work?")
if summary is not None:
    n_nodes = int(summary.loc[summary["kind"] == "nodes", "count"].sum())
    n_edges = int(summary.loc[summary["kind"] == "edges", "count"].sum())
    cols[3].metric("Knowledge graph", f"{n_nodes:,} nodes", f"{n_edges:,} edges", delta_color="off", delta_arrow="off",
                   help="Every edge records where it came from.")

# -- where to go ---------------------------------------------------------------
st.header("Where to start")
a1, a2, a3 = st.columns(3)
with a1:
    st.page_link(ui.PAGES["ask"], label="Ask StrainScope", icon=":material/question_answer:")
    st.caption("A question about the project, answered from its own guides with links to the exact section. "
               "Try \"How do I score my own strains?\"")
with a2:
    st.page_link(ui.PAGES["ask_data"], label="Ask the data", icon=":material/table_chart:")
    st.caption("A question about the data in plain words, answered with a query you can see and the table it "
               "returns.")
with a3:
    st.page_link(ui.PAGES["ask_graph"], label="Ask the graph", icon=":material/account_tree:")
    st.caption("How things connect: answers built by walking the knowledge graph, every step with its source.")
left, right = st.columns(2)
with left:
    st.page_link(ui.PAGES["ranking"], label="Ranking", icon=":material/format_list_numbered:")
    st.caption("All strains, best first. Slide to choose how many you could test and see how many would work.")
    st.page_link(ui.PAGES["strain"], label="Strain page", icon=":material/coronavirus:")
    st.caption("One strain: its score, the reasons behind it, and its corner of the knowledge graph.")
    st.page_link(ui.PAGES["graph"], label="Knowledge graph", icon=":material/hub:")
    st.caption("The network of genes, compounds and modes of action. Find the path between any two things.")
with right:
    st.page_link(ui.PAGES["integration"], label="Integration", icon=":material/join_inner:")
    st.caption("How genes and chemistry were read together (Phase 3), graded against the planted truth.")
    st.page_link(ui.PAGES["data"], label="Data", icon=":material/database:")
    st.caption("The simulated library, your own strains (upload a CSV), and real data from public databases.")
    st.page_link(ui.PAGES["sql"], label="SQL console", icon=":material/terminal:")
    st.caption("Ask the database anything in SQL, read-only, with the Query Cookbook's recipes one click away.")

# -- the health check --------------------------------------------------------
with st.expander("What the app is reading (health check)", expanded=not all(c.ok is not False for c in checks)):
    mark = {True: ":green[✓]", False: ":red[✗]", None: ":gray[·]"}
    for c in checks:
        st.markdown(f"{mark[c.ok]} **{c.name}**: {c.detail}")
        if c.fix and c.ok is not True:
            st.caption(("For the owner: " if ui.PUBLIC else "To add: " if c.ok is None else "To fix: ") + f"`{c.fix}`")
    st.caption("The same check from a terminal: `python src/strainscope/service.py status`. More on the "
               "**About this copy** page.")

with st.expander("How this app works"):
    st.markdown(
        "The app is the last link in a chain. The scripts of Phases 1 to 5 did the heavy work once, on a laptop, "
        "and saved small result files in `artifacts/` plus a database. The app only **reads** them, which is why "
        "every page opens quickly. Every click reruns the page from the top; the files are read once and kept "
        "in memory until they change.")
    st.graphviz_chart("""
digraph {
  rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];
  scripts [label="Phases 1 to 5\\nsrc/strainscope/*.py", fillcolor="#E8F0FE", color="#5B8DEF"];
  art [label="artifacts/\\ncommitted results", fillcolor="#EAECEF", color="#8A94A6", shape=folder];
  db [label="strainscope.duckdb\\n(read-only here)", fillcolor="#FFF3CD", color="#C9A227", shape=cylinder];
  svc [label="the service layer\\nsrc/strainscope/service.py", fillcolor="#E6F4EA", color="#4CAF7D"];
  app [label="this app\\napp/streamlit_app.py", fillcolor="#E6F4EA", color="#2E7D5B"];
  you [label="you", shape=ellipse, fillcolor="#FFFFFF", color="#5f6b7a"];
  scripts -> art; scripts -> db; art -> svc; db -> svc; svc -> app; app -> you [dir=both];
}""")
    st.markdown(f"The full story, with every step explained: {ui.doc('07-app.md', 'docs/07-app.md')}.")
