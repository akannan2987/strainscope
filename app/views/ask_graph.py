"""app/views/ask_graph.py: Ask the graph (Phase 7, GraphRAG). A question about
how things connect, answered by walking the knowledge graph of Phase 5: the
route drawn, and numbered facts, each with its source. A question about one
strain gets that strain's explanation in plain words. With a language model
set up, a short answer that cites the facts appears above them. The engine
is src/strainscope/ask_graph.py; the guide is docs/08-deployment-ai.md
(section 7)."""
import streamlit as st

import charts
import ui
from strainscope import ask_graph as gq
from strainscope import llm
from strainscope.ontology import KNOWLEDGE_TYPES

BOX = {gq.ANSWERED: st.success, gq.CLOSEST: st.warning, gq.REFUSED: st.info, gq.VAGUE: st.info}
ICON = {gq.ANSWERED: ":material/account_tree:", gq.CLOSEST: ":material/help:", gq.REFUSED: ":material/block:",
        gq.VAGUE: ":material/edit:"}


def _set_question(text: str) -> None:
    st.session_state["graph_question"] = text


st.title("Ask the graph")
st.markdown("How are two things connected? What does a compound do? Ask, and the answer is a **walk through "
            "the knowledge graph**: numbered facts, each with the source it came from, and the route drawn. "
            "Name a gene, compound, mode of action or strain the way the graph does (ituA, iturin, iron "
            "competition, STRAIN_0485).")
G = ui.graph()
if G is None:
    ui.needs("Ask the graph needs Phase 5's graph.", "python src/strainscope/graph.py all")
    st.stop()

cfg = llm.settings()
question = st.text_input("Your question", key="graph_question", placeholder="e.g. How does iturin suppress disease?",
                         help="Press Enter to ask.")
write = False
if cfg.on:
    write = None if st.toggle(f"Also write a short answer ({cfg.model})", value=True, key="graph_write",
                              help="A language model writes a few sentences from the numbered facts and must "
                                   "cite them. It sees only the question, those facts (from the domain model and "
                                   "public references) and StrainScope's fixed rules; questions about a strain never "
                                   "reach it.") else False

if not question.strip():
    st.markdown("**Try one of these:**")
    cols = st.columns(2)
    for n, q in enumerate(gq.STARTERS):
        cols[n % 2].button(q, key=f"graph_starter_{n}", on_click=_set_question, args=(q,), width="stretch")
else:
    with st.spinner("Walking the graph..."):
        answer = gq.ask(question, G, write=write, cfg=cfg if write is not False else None)
    BOX[answer.verdict](answer.message, icon=ICON[answer.verdict])

    if answer.written:
        with st.container(border=True):
            st.markdown(f"**Written answer** · {answer.written_by}")
            st.markdown(answer.written)
            st.caption("Written by a language model from the numbered facts below, which it had to cite. "
                       "Check it against them.")
    elif answer.note:
        st.caption(f"No written answer: {answer.note}")

    if answer.story:
        with st.container(border=True):
            st.markdown("**In plain words**")
            for para in answer.story.split("\n\n"):
                st.markdown(para)
        if st.button(f"Open the page of {answer.strain}", icon=":material/coronavirus:"):
            ui.pick_strain(answer.strain)
    if answer.hops:
        st.markdown("**The route**")
        st.plotly_chart(charts.path_figure(answer.hops), width="stretch")
    if answer.facts:
        st.markdown("**The facts**" + (" (the walks behind the explanation)" if answer.story else ""))
        for n, f in enumerate(answer.facts, start=1):
            stats = "statistics only" in f.text
            note = " :orange-badge[statistics only]" if stats else ""
            st.markdown(f"[{n}] {f.text}{note}")
            st.caption(f"source: {f.source}")
    ui.suggest_fix("Ask the graph", question, answer.verdict, [f.text for f in answer.facts])

st.divider()
nodes = sum(1 for _, d in G.nodes(data=True) if d["node_type"] in KNOWLEDGE_TYPES)
st.caption(f"The knowledge layer has {nodes:,} things to ask about, plus the strains. {ui.model_note(cfg)}. "
           f"How it works: {ui.doc('08-deployment-ai.md', 'docs/08-deployment-ai.md')}. The same from a terminal: "
           "`python src/strainscope/ask_graph.py \"your question\"`.")
