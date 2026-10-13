"""app/views/knowledge_graph.py: the knowledge graph of Phase 5. The
network itself, a path finder, a look-up for any node, hubs and
communities, and where the biology and the statistics agree."""
import streamlit as st

import charts
import ui
from strainscope import graph as kg

st.title("Knowledge graph")
G, layout = ui.graph(), ui.knowledge_layout()
if G is None or layout is None:
    ui.needs("The graph comes from Phase 5, and its files aren't there yet.",
             ui.fix_command("python src/strainscope/graph.py all"))
    st.stop()
edges = ui.artifact("graph/edges.csv")
st.markdown(
    "Everything the project knows, as things and the connections between them: a strain **carries** a gene, the "
    "gene **makes** a compound, the compound **acts by** a mode of action, which **contributes to** disease "
    "suppression. Every connection records where it came from. "
    f"The ideas are explained in {ui.doc('06-knowledge-graph.md', 'docs/06-knowledge-graph.md')}.")
ui.simulated_note()

net, find, look, groups, agree = st.tabs(["The network", "Find a path", "Look something up",
                                          "Hubs and communities", "Knowledge vs data"])
labels = {d["label"]: n for n, d in G.nodes(data=True) if d["node_type"] != "ReferenceStrain"}
concepts = sorted((lab for lab, n in labels.items() if G.nodes[n]["node_type"] != "Strain"), key=str.lower)


def _quoted(name: str) -> str:
    """Names with spaces need quotes on the command line."""
    return f'"{name}"' if " " in name else name

# =============================================================================
with net:
    types = sorted(layout["node_type"].unique())
    c1, c2 = st.columns([3, 2])
    chosen = c1.multiselect("Show", types, default=types, key="net_types")
    focus = c2.selectbox("Highlight one thing and its neighbours", ["(nothing)"] + sorted(layout["label"], key=str.lower),
                         key="net_focus")
    highlight = None
    if focus != "(nothing)":
        n = layout.loc[layout["label"] == focus, "node_id"].iloc[0]
        neighbours = set(G.successors(n)) | set(G.predecessors(n))
        highlight = {n} | (neighbours & set(layout["node_id"]))
    ui.chart(charts.network_figure(layout, edges, chosen, highlight))
    st.caption("Strains, genera and the three housekeeping genes are left out so the concepts stay readable. "
               "Drag to move, scroll to zoom, double-click to reset. Red dotted lines are statistics-only links "
               "from Phases 3 and 4.")

# =============================================================================
with find:
    st.markdown("How are two things connected? The search prefers a route that says *how* (a mechanism) "
                "over a one-step shortcut that only says *the data links them*.")
    c1, c2 = st.columns(2)
    everything = concepts + sorted(lab for lab, n in labels.items() if G.nodes[n]["node_type"] == "Strain")
    start = c1.selectbox("From", everything, index=everything.index("ituA") if "ituA" in everything else 0,
                         key="path_from")
    end = c2.selectbox("To", everything, index=everything.index("disease suppression")
                       if "disease suppression" in everything else 0, key="path_to")
    try:
        hops = kg.path(G, start, end)
    except KeyError as err:
        hops = None
        st.warning(err.args[0])
    if hops == []:
        st.info(f"No path between {start} and {end} in the knowledge layer.")
    elif hops:
        ui.chart(charts.path_figure(hops))
        for i, h in enumerate(hops, start=1):
            stats = h["relation"] == "associated_with"
            note = " :orange-badge[statistics only, no known mechanism]" if stats else ""
            st.markdown(f"{i}. **{h['from']}** *{h['relation']}* **{h['to']}**{note}")
            st.caption(f"source: {h['provenance']}" + (f" · {h['evidence']}" if h["evidence"] else ""))
        if ui.builtin():
            st.caption(f"From a terminal: `python src/strainscope/graph.py path {_quoted(start)} {_quoted(end)}`")
    if ui.builtin():
        st.caption("Try accE to disease suppression: the decoy has only a statistic, no mechanism.")

# =============================================================================
with look:
    what = st.selectbox("Anything in the graph", concepts, index=concepts.index("iturin") if "iturin" in concepts else 0,
                        key="look_up")
    info = kg.show(G, what)
    a = info["attributes"]
    st.markdown(f"## {a['label']}\n*{a['node_type']}*" + (f": {a['description']}" if a.get("description") else ""))
    facts = {k: v for k, v in a.items() if k not in ("label", "node_type", "description")}
    if facts:
        st.dataframe([{"attribute": k, "value": str(v)} for k, v in facts.items()], hide_index=True, width="content")
    for rel, grp in sorted(info["neighbours"].items()):
        names = grp["labels"]
        shown = ", ".join(names) if len(names) <= 40 else ", ".join(names[:40]) + f" ... ({len(names)} in total)"
        st.markdown(f"**{rel}** {shown}")
        st.caption(f"source: {'; '.join(grp['sources'])}")
    if ui.builtin():
        st.caption(f"From a terminal: `python src/strainscope/graph.py show {_quoted(what)}`")

# =============================================================================
with groups:
    hubs, comm, check = (ui.artifact("graph/hubs.csv"), ui.artifact("graph/communities.csv"),
                         ui.artifact("graph/community_check.csv"))
    if hubs is not None:
        st.markdown("**Hubs.** The most connected things. The top of this list is a reminder that 'most "
                    "connected' isn't 'most important': nearly every strain carries the housekeeping genes.")
        c1, c2 = st.columns(2)
        c1.markdown("Touching the most strains")
        c1.dataframe(hubs.nlargest(8, "strains_connected")[["label", "node_type", "strains_connected", "role"]],
                     hide_index=True, width="stretch")
        c2.markdown("The biggest bridges between concepts (betweenness)")
        c2.dataframe(hubs.nlargest(8, "betweenness")[["label", "node_type", "concept_degree", "betweenness"]],
                     hide_index=True, width="stretch")
    if comm is not None and check is not None:
        c = check.iloc[0]
        if int(c["signal_features"]):
            st.markdown(f"**Communities.** Features that turn up in the same strains, grouped with the Louvain "
                        f"method. Graded against the planted arsenals: purity **{c['purity']:.2f}**, adjusted "
                        f"Rand index **{c['ari']:.2f}** (1 = a perfect match).")
        else:
            st.markdown("**Communities.** Features that turn up in the same strains, grouped with the Louvain "
                        "method. Your own data has no planted arsenals, so the groups aren't graded: read them "
                        "as hints of which genes and compounds travel together.")
        linked = comm[comm["community"] > 0]
        for k, grp in linked.groupby("community"):
            main = grp["arsenal"].value_counts()
            st.markdown(f"- community {k}: {len(grp)} features, mostly {main.index[0]} ({main.iloc[0]}/{len(grp)}): "
                        + ", ".join(sorted(grp["label"], key=str.lower)))
        st.caption("No strong ties: " + ", ".join(sorted(comm.loc[comm["community"] <= 0, "label"], key=str.lower)))

# =============================================================================
with agree:
    kvd = ui.artifact("graph/knowledge_vs_data.csv")
    if kvd is not None:
        st.markdown("Each gene and compound sorted by what supports a link to disease suppression: a known "
                    "mechanism, the data (Phase 3 or 4), both, or neither. The red box is the one to watch on "
                    "real data: a feature the model leans on that nothing explains is either a discovery or a problem.")
        style = {"confirmed": st.success, "mechanism only": st.info, "data only": st.error}
        for verdict, grp in kvd.groupby("verdict", sort=False):
            show = next((f for key, f in style.items() if verdict.startswith(key)), st.markdown)
            show(f"**{verdict}** ({len(grp)}): " + ", ".join(sorted(grp["label"], key=str.lower)))
