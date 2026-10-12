"""app/views/strain.py: one strain's page. Its score and rank, the reasons
behind them (walks through the knowledge graph, each with its sources), its
corner of the graph drawn as five columns, and where it sits among the rest."""
import pandas as pd
import streamlit as st

import charts
import ui
from strainscope import service as sv

pred = ui.ranking()
G = ui.strain_graph()
if pred is None or G is None:
    ui.needs("The strain page needs Phase 4's ranking and Phase 5's graph.",
             "python src/strainscope/model.py all\npython src/strainscope/graph.py all")
    st.stop()

ids = pred.sort_values("rank")["strain_id"].tolist()
# The strain to show: the one picked in this tab (Ranking page, Previous/Next),
# else the one named in the address (?strain=...), else the top-ranked strain.
wanted = st.session_state.get("current_strain") or st.query_params.get("strain") or ids[0]
if wanted not in ids:
    wanted = ids[0]


def _remember():
    st.session_state["current_strain"] = st.session_state["strain_box"]


st.session_state["strain_box"] = wanted
top = st.columns([3, 1, 1])
strain = top[0].selectbox("Strain (best ranked first; type to search)", ids, key="strain_box", on_change=_remember)
st.session_state["current_strain"] = strain
st.query_params["strain"] = strain                  # the address bar now links straight to this strain
pos = ids.index(strain)
if top[1].button("Previous", disabled=pos == 0, width="stretch"):
    st.session_state["current_strain"] = ids[pos - 1]
    st.query_params["strain"] = ids[pos - 1]
    st.rerun()
if top[2].button("Next", disabled=pos == len(ids) - 1, width="stretch"):
    st.session_state["current_strain"] = ids[pos + 1]
    st.query_params["strain"] = ids[pos + 1]
    st.rerun()

row = pred[pred["strain_id"] == strain].iloc[0]
node = G.nodes.get(f"strain:{strain}", {})
st.title(strain)
genus = row.get("genus") if isinstance(row.get("genus"), str) else node.get("genus", "unknown")
st.markdown(f"*{genus}*, {str(row['kingdom']).lower()}"
            + (" · from your upload" if ui.showing_upload() else " · simulated library"))

expl = ui.explanation(strain)
paths = int(expl["mechanism_paths"].iloc[0]) if len(expl) else 0
threshold = (ui.card() or {}).get("decision_threshold", 0.5)
m = st.columns(4)
m[0].metric("Rank", f"{int(row['rank'])} of {len(pred)}")
band = sv.confidence_band(row["probability"])
m[1].metric("Chance of being effective", f"{row['probability']:.0%}",
            f"{band} · {'flagged' if row['probability'] >= threshold else 'not flagged'}",
            delta_color="off", delta_arrow="off",
            help=f"Likely above 70 %, borderline from 30 % to 70 %, unlikely below 30 %. 'Effective' means "
                 f"suppressing disease by at least 65 % in the trial, and strains just either side of that "
                 f"line are much alike, so a middling chance is called borderline. Flagged when the chance "
                 f"is above {threshold:.0%}, the library's share of effective strains.")
m[2].metric("Mechanism paths", paths, help="Routes in the knowledge graph from this strain, through a weapon "
                                           "and the way it works, to disease suppression.")
if "is_effective" in row.index and pd.notna(row.get("is_effective")):
    m[3].metric("In the simulated trial", "effective" if int(row["is_effective"]) == 1 else "not effective",
                help="The answer key, known only because the data is simulated.")
elif "library_rank" in row.index:
    lr = int(row["library_rank"])
    m[3].metric("Would rank in the library", f"{lr} of 600" if lr <= 600 else "below all 600")

# -- why it ranks here -----------------------------------------------------------
st.subheader("Why it ranks here")
if not len(expl):
    st.markdown("No mechanism path, no flags: the strain carries none of the weapons the graph knows about.")
for r in expl.itertuples(index=False):
    st.markdown(ui.reason_line(r))
    with st.expander("the walk and its sources", expanded=False):
        st.markdown(f"`{r.path}`")
        st.caption(f"Sources: {r.provenance}")
shown = int((expl["kind"] == "mechanism").sum()) if len(expl) else 0
if paths > shown:
    st.caption(f"Plus {paths - shown} more mechanism path(s); the picture below shows them all.")
with st.expander("How to read these lines"):
    st.markdown(
        "- :green-badge[how it works] **+** the strain carries a weapon gene (and, when measured, makes its "
        "compound) that works in a known way against disease. Up to three are listed, the ones the model "
        "relies on most.\n"
        "- :orange-badge[statistics only] **?** the model leans on this feature, but nothing known explains "
        "why. It's shown so you don't mistake it for a reason.\n"
        "- :gray-badge[lacks] **-** a weapon that at least 30 % of strains of its kingdom carry, and this one "
        "doesn't. A missing gene call is never counted as 'lacks'.\n\n"
        f"Every line is a walk through the knowledge graph ({ui.doc('06-knowledge-graph.md', 'docs/06-knowledge-graph.md')} "
        "section 7).")

# -- its corner of the graph --------------------------------------------------------
st.subheader("Its corner of the knowledge graph")
st.caption("Read left to right: what it carries, what it makes, how that works, what it leads to. Hollow "
           "circles are weapons it lacks. Hover a dot or the middle of a line for details and sources.")
nodes, edges = sv.neighbourhood(G, strain, expl)
st.plotly_chart(charts.neighbourhood_figure(nodes, edges), width="stretch")

# -- where it sits ------------------------------------------------------------------------
st.subheader("Where it sits among the others")
st.plotly_chart(charts.probability_strip(pred, strain), width="stretch")
with st.expander("Everything it carries and produces"):
    carried = sorted(G.nodes[v]["label"] for _, v, e in G.out_edges(f"strain:{strain}", data=True)
                     if e["relation"] == "carries")
    produced = sorted(((G.nodes[v]["label"], e.get("weight")) for _, v, e in
                       G.out_edges(f"strain:{strain}", data=True) if e["relation"] == "produces"),
                      key=lambda x: -(x[1] or 0))
    st.markdown("**Genes it carries:** " + (", ".join(carried) or "none recorded"))
    st.markdown("**Compounds it produces** (at least 4 times the library's usual level): "
                + (", ".join(f"{c} ({w:.1f}x)" for c, w in produced) or "none"))
    st.caption("From a terminal: `python src/strainscope/graph.py show " + strain + "`"
               if not ui.showing_upload() else "Uploaded strains are not in the saved graph, so `graph.py show` "
                                               "doesn't know them; this page does.")
