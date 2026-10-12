"""
app/charts.py: every chart the app draws, as plain functions.
=============================================================
Each function takes small tables (pandas DataFrames) and returns a Plotly
figure. Nothing here knows about Streamlit, so the charts can be tested on
their own (tests/test_app.py) and reused elsewhere.

The colours are the project palette used by every figure in figures/ and
every diagram in docs/, so the app and the documentation look alike.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from strainscope.ontology import NODE_TYPES  # noqa: E402

BLUE, GREEN, GOLD, GREY, PURPLE, RED = ("#5B8DEF", "#4CAF7D", "#C9A227",
                                        "#8A94A6", "#9C6ADE", "#D9634C")
INK, SOFT, DARK_GREEN, PALE = "#1F2933", "#5f6b7a", "#2E7D5B", "#C7CDD6"
KINGDOM_COLOURS = {"Bacteria": BLUE, "Fungi": GREEN, "Yeast": GOLD, "Oomycete": PURPLE}
TYPE_COLOURS = {t: d["colour"] for t, d in NODE_TYPES.items()}
ROLE_COLOURS = {"signal": DARK_GREEN, "decoy": RED, "housekeeping": GREY,
                "context (kingdom label, used for centring)": GOLD}
EDGE_STYLES = {                       # line colour, dash, label in the legend
    "fact": (GREY, "solid", "carries or produces"),
    "mechanism": (DARK_GREEN, "solid", "how it works (domain model)"),
    "statistics": (RED, "dot", "statistics only (no known mechanism)"),
    "without gene": ("#B8860B", "dashdot", "makes it without carrying the gene"),
    "lacks": (PALE, "dash", "lacks (common in its kingdom)"),
}
COLUMN_TITLES = ["strain", "genes", "compounds", "how it works", "outcome"]


def _base(fig: go.Figure, height: int, **layout) -> go.Figure:
    fig.update_layout(template="plotly_white", height=height,
                      margin=dict(l=10, r=10, t=40, b=10),
                      font=dict(color=INK), **layout)
    return fig


# =============================================================================
# The ranking (Phase 4)
# =============================================================================

def top_n_figure(pred: pd.DataFrame, n: int) -> go.Figure:
    """How many truly effective strains you'd find by testing the top N,
    against picking at random and against a perfect list."""
    ranked = pred.sort_values("rank")
    hits = ranked["is_effective"].cumsum().to_numpy()
    xs = np.arange(1, len(ranked) + 1)
    total, base = int(ranked["is_effective"].sum()), ranked["is_effective"].mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=np.minimum(xs, total), name="a perfect list",
                             line=dict(color=PALE, dash="dot")))
    fig.add_trace(go.Scatter(x=xs, y=hits, name="the model's ranking", line=dict(color=DARK_GREEN, width=3),
                             hovertemplate="top %{x}: %{y} effective<extra></extra>"))
    fig.add_trace(go.Scatter(x=xs, y=xs * base, name="picking at random", line=dict(color=GREY, dash="dash"),
                             hovertemplate="top %{x}: about %{y:.0f} by chance<extra></extra>"))
    found = int(hits[n - 1])
    fig.add_trace(go.Scatter(x=[n], y=[found], mode="markers+text", showlegend=False,
                             marker=dict(size=12, color=DARK_GREEN, line=dict(color="white", width=2)),
                             text=[f"  {found} of {n}"], textposition="middle right", hoverinfo="skip"))
    fig.add_vline(x=n, line=dict(color=SOFT, width=1, dash="dot"))
    return _base(fig, 330, xaxis_title="strains tested (from the top of the ranking)",
                 yaxis_title="truly effective among them", legend=dict(orientation="h", y=1.12))


def probability_strip(pred: pd.DataFrame, highlight: str | None = None) -> go.Figure:
    """Every library strain's predicted chance, one row per kingdom, with
    one strain picked out. A quick way to see where a strain sits."""
    fig = go.Figure()
    rng = np.random.default_rng(42)          # the same jitter every time
    kingdoms = [k for k in KINGDOM_COLOURS if k in set(pred["kingdom"])]
    for i, k in enumerate(kingdoms):
        part = pred[pred["kingdom"] == k]
        fig.add_trace(go.Scatter(
            x=part["probability"], y=i + rng.uniform(-0.25, 0.25, len(part)), mode="markers", name=k,
            marker=dict(size=5, color=KINGDOM_COLOURS[k], opacity=0.45),
            text=part["strain_id"], hovertemplate="%{text}: %{x:.0%}<extra></extra>"))
    if highlight is not None and highlight in set(pred["strain_id"]):
        row = pred[pred["strain_id"] == highlight].iloc[0]
        y = kingdoms.index(row["kingdom"]) if row["kingdom"] in kingdoms else 0
        fig.add_trace(go.Scatter(x=[row["probability"]], y=[y], mode="markers+text", showlegend=False,
                                 marker=dict(size=16, color=INK, symbol="diamond", line=dict(color="white", width=2)),
                                 text=[highlight], hoverinfo="skip",
                                 textposition="top left" if row["probability"] > 0.85 else
                                 ("top right" if row["probability"] < 0.15 else "top center")))
    return _base(fig, 260, xaxis=dict(title="predicted chance of being effective", tickformat=".0%", range=[-0.02, 1.02]),
                 yaxis=dict(tickvals=list(range(len(kingdoms))), ticktext=kingdoms, title=None),
                 showlegend=False)


def model_scoreboard_figure(board: pd.DataFrame) -> go.Figure:
    """Balanced error rate of every model (lower is better), with a coin's 0.5."""
    b = board.sort_values("ber_mean", ascending=False)
    colours = [DARK_GREEN if w in (True, "True") else GREY for w in b["is_winner"]]
    fig = go.Figure(go.Bar(x=b["ber_mean"], y=b["model"].str.split(" \\(").str[0], orientation="h",
                           marker_color=colours, error_x=dict(type="data", array=b["ber_sd"], color=INK),
                           text=b["ber_mean"].map("{:.3f}".format), textposition="inside",
                           insidetextanchor="start", textfont=dict(color="white"),
                           hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
    fig.add_vline(x=0.5, line=dict(color=RED, dash="dash"), annotation_text="a coin: 0.50",
                  annotation_position="top")
    return _base(fig, 300, xaxis=dict(title="balanced error rate (lower is better)", range=[0, 0.62]),
                 yaxis_title=None)


def calibration_figure(curve: pd.DataFrame) -> go.Figure:
    """Does a predicted 70 % come true about 70 % of the time? Points on the
    diagonal mean yes."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], name="perfectly calibrated",
                             line=dict(color=PALE, dash="dot"), hoverinfo="skip"))
    for version, colour, name in (("raw", GOLD, "before calibration"), ("calibrated", DARK_GREEN, "after calibration")):
        part = curve[curve["version"] == version]
        fig.add_trace(go.Scatter(x=part["mean_predicted"], y=part["observed_rate"], mode="lines+markers",
                                 name=name, line=dict(color=colour), marker=dict(size=7),
                                 customdata=part["n"], hovertemplate="predicted %{x:.0%}, came true %{y:.0%} "
                                                                     "(%{customdata} predictions)<extra></extra>"))
    return _base(fig, 330, xaxis=dict(title="predicted chance", tickformat=".0%"),
                 yaxis=dict(title="share that were effective", tickformat=".0%"),
                 legend=dict(orientation="h", y=1.12))


def importance_figure(imp: pd.DataFrame, top: int = 15) -> go.Figure:
    """What the winning model leans on: how much its AUC drops when a
    feature is shuffled. Colour says whether the feature is a planted driver."""
    part = imp.sort_values("importance_mean", ascending=False).head(top).iloc[::-1]
    colours = [ROLE_COLOURS.get(r, GREY) for r in part["role"]]
    labels = [f"{f} ✓" if rel in (True, "True") else f for f, rel in zip(part["feature"], part["reliably_important"])]
    fig = go.Figure(go.Bar(x=part["importance_mean"], y=labels, orientation="h", marker_color=colours,
                           error_x=dict(type="data", array=part["importance_sd"], color=SOFT),
                           customdata=part["role"],
                           hovertemplate="%{y}: AUC drops %{x:.3f} (%{customdata})<extra></extra>"))
    return _base(fig, 30 + 26 * len(part), xaxis_title="AUC lost when the feature is shuffled", yaxis_title=None)


# =============================================================================
# Integration (Phase 3)
# =============================================================================

def signature_figure(sig: pd.DataFrame, ann: pd.DataFrame | None) -> go.Figure:
    """DIABLO's first-component signature: how often each feature was picked
    across re-fits (stability). The dashed line is the 80 % 'robust' bar."""
    part = sig[sig["component"] == 1].copy()
    roles = dict(zip(ann["feature"], ann["role"])) if ann is not None else {}
    part["role"] = part["feature"].map(roles).fillna("signal")
    part = part.sort_values(["stability", "feature"], ascending=[True, False])
    colours = [RED if r == "decoy" else (BLUE if b == "genomics" else GOLD)
               for r, b in zip(part["role"], part["block"])]
    fig = go.Figure(go.Bar(x=part["stability"], y=part["feature"], orientation="h", marker_color=colours,
                           customdata=np.stack([part["block"], part["role"], part["loading"]], axis=1),
                           hovertemplate="%{y} (%{customdata[0]}, %{customdata[1]}): picked in %{x:.0%} "
                                         "of re-fits, loading %{customdata[2]}<extra></extra>"))
    fig.add_vline(x=0.8, line=dict(color=INK, dash="dash"), annotation_text="robust: 80 %",
                  annotation_position="top")
    return _base(fig, 40 + 18 * len(part), xaxis=dict(title="stability (share of re-fits that picked it)",
                                                      tickformat=".0%", range=[0, 1.05]), yaxis_title=None)


def integration_scoreboard_figure(board: pd.DataFrame, diablo_ber: float | None) -> go.Figure:
    """Every way of combining the blocks, scored on the same folds."""
    b = board.sort_values("ber_mean", ascending=False)
    names, ber, sd = list(b["approach"]), list(b["ber_mean"]), list(b["ber_sd"])
    colours = [GREY if "control" in a.lower() or "shuffled" in a.lower() else BLUE for a in names]
    if diablo_ber is not None:
        names.append("DIABLO (R, mixOmics)")
        ber.append(diablo_ber)
        sd.append(0.0)
        colours.append(DARK_GREEN)
        order = np.argsort(ber)[::-1]
        names, ber, sd, colours = ([x[i] for i in order] for x in (names, ber, sd, colours))
    fig = go.Figure(go.Bar(x=ber, y=names, orientation="h", marker_color=colours,
                           error_x=dict(type="data", array=sd, color=INK),
                           text=[f"{v:.3f}" for v in ber], textposition="inside",
                           insidetextanchor="start", textfont=dict(color="white"),
                           hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
    fig.add_vline(x=0.5, line=dict(color=RED, dash="dash"), annotation_text="a coin: 0.50",
                  annotation_position="top")
    return _base(fig, 60 + 34 * len(names), xaxis=dict(title="balanced error rate (lower is better)",
                                                       range=[0, 0.62]), yaxis_title=None)


def correlation_heatmap(cross: pd.DataFrame) -> go.Figure:
    """How strongly each gene's presence goes with each compound's level
    (Spearman correlation). The bright cells on the diagonal-ish pattern are
    genes and the compounds they make."""
    grid = cross.pivot(index="gene", columns="metabolite", values="spearman_rho")
    fig = go.Figure(go.Heatmap(z=grid.values, x=grid.columns, y=grid.index, zmin=-1, zmax=1,
                               colorscale=[[0, BLUE], [0.5, "#FFFFFF"], [1, RED]],
                               colorbar=dict(title="rho"),
                               hovertemplate="%{y} and %{x}: rho %{z:.2f}<extra></extra>"))
    return _base(fig, 40 + 19 * len(grid), xaxis=dict(tickangle=-45, dtick=1),
                 yaxis=dict(autorange="reversed", dtick=1))


# =============================================================================
# The knowledge graph (Phase 5)
# =============================================================================

def neighbourhood_figure(nodes: pd.DataFrame, edges: pd.DataFrame) -> go.Figure:
    """One strain's corner of the graph in five columns, read left to right:
    the strain, what it carries, what it makes, how that works, what it leads to."""
    pos = nodes.set_index("node_id")[["x", "y"]]
    fig = go.Figure()
    for style, (colour, dash, name) in EDGE_STYLES.items():
        part = edges[edges["style"] == style]
        if part.empty:
            continue
        xs, ys, mx, my, tips = [], [], [], [], []
        for r in part.itertuples(index=False):
            (x0, y0), (x1, y1) = pos.loc[r.from_id], pos.loc[r.to_id]
            xs += [x0, x1, None]
            ys += [y0, y1, None]
            mx.append((x0 + x1) / 2)
            my.append((y0 + y1) / 2)
            tips.append(f"{r.relation}<br><i>source: {r.provenance}</i>")
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=name, hoverinfo="skip",
                                 line=dict(color=colour, width=2 if style != "fact" else 1.2, dash=dash)))
        fig.add_trace(go.Scatter(x=mx, y=my, mode="markers", showlegend=False, hovertext=tips, hoverinfo="text",
                                 marker=dict(size=8, color=colour, opacity=0.0)))
    for t in ["Strain", "Gene", "Compound", "ModeOfAction", "Outcome"]:
        part = nodes[nodes["node_type"] == t]
        if part.empty:
            continue
        lacks = part["status"] == "lacks"
        hover = [f"<b>{r.label}</b> ({t})<br>{r.description}" + (f"<br>{r.detail}" if r.detail else "")
                 for r in part.itertuples()]
        fig.add_trace(go.Scatter(
            x=part["x"], y=part["y"], mode="markers", name=t if t != "ModeOfAction" else "mode of action",
            hovertext=hover, hoverinfo="text",
            marker=dict(size=22 if t == "Strain" else 14, symbol="circle",
                        color=["#FFFFFF" if lk else TYPE_COLOURS[t] for lk in lacks],
                        line=dict(color=[GREY if lk else "white" for lk in lacks], width=2))))
        for r, lk in zip(part.itertuples(), lacks):     # labels on a white card, so no line hides them
            fig.add_annotation(x=r.x, y=r.y, text=f"{r.label} (lacks)" if lk else r.label, showarrow=False,
                               xanchor="right" if t == "Strain" else "left", xshift=-14 if t == "Strain" else 10,
                               font=dict(size=11, color=SOFT if lk else INK),
                               bgcolor="rgba(255,255,255,0.85)", borderpad=1)
    top = nodes["y"].max() + 1.1 if len(nodes) else 1
    for i, title in enumerate(COLUMN_TITLES):
        fig.add_annotation(x=i, y=top, text=f"<b>{title}</b>", showarrow=False, font=dict(color=SOFT))
    rows = max(nodes["x"].value_counts()) if len(nodes) else 1
    return _base(fig, max(320, 60 + 34 * rows),
                 xaxis=dict(visible=False, range=[-0.6, 4.9]), yaxis=dict(visible=False),
                 legend=dict(orientation="h", y=-0.04), hoverlabel=dict(align="left"))


def knowledge_layout(nodes: pd.DataFrame, edges: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    """Positions for the knowledge layer (genes, compounds, modes of action,
    outcomes, and real pathways and classes when present). Strains, genera,
    kingdoms and housekeeping genes are left out so the concepts stay readable.
    The same seed as docs/interactive/graph_explorer.html gives the same picture."""
    import networkx as nx
    types = {"Gene", "Compound", "ModeOfAction", "Outcome", "Pathway", "ChemicalClass"}
    keep = nodes[nodes["node_type"].isin(types) & (nodes.get("role", pd.Series(index=nodes.index)) != "housekeeping")]
    K = nx.Graph()
    K.add_nodes_from(keep["node_id"])
    for r in edges.itertuples(index=False):
        if r.from_id in K and r.to_id in K:
            K.add_edge(r.from_id, r.to_id)
    K.remove_nodes_from([v for v in list(K.nodes) if K.degree(v) == 0])
    pos = nx.spring_layout(K, seed=seed, k=0.35)
    out = keep[keep["node_id"].isin(pos)].copy()
    out["x"] = out["node_id"].map(lambda v: pos[v][0])
    out["y"] = out["node_id"].map(lambda v: pos[v][1])
    out["degree"] = out["node_id"].map(dict(K.degree()))
    return out


def network_figure(layout: pd.DataFrame, edges: pd.DataFrame, types: list[str] | None = None,
                   highlight: set[str] | None = None) -> go.Figure:
    """The knowledge layer as a network you can pan and zoom. Red dotted
    lines are statistics-only links; a highlighted node and its neighbours
    are drawn larger, the rest faded."""
    lay = layout if types is None else layout[layout["node_type"].isin(types)]
    pos = lay.set_index("node_id")[["x", "y"]]
    inside = edges[edges["from_id"].isin(pos.index) & edges["to_id"].isin(pos.index)]
    fig = go.Figure()
    for stats, (colour, dash, name) in ((False, ("#B8BEC8", "solid", "mechanism or fact")),
                                        (True, (RED, "dot", "statistics only"))):
        part = inside[(inside["relation"] == "associated_with") == stats]
        xs, ys = [], []
        for r in part.itertuples(index=False):
            on = highlight is None or (r.from_id in highlight and r.to_id in highlight)
            if not on:
                continue
            xs += [pos.loc[r.from_id, "x"], pos.loc[r.to_id, "x"], None]
            ys += [pos.loc[r.from_id, "y"], pos.loc[r.to_id, "y"], None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=name, hoverinfo="skip",
                                 line=dict(color=colour, width=1.4 if highlight else 0.8, dash=dash)))
    for t in ["Gene", "Compound", "ModeOfAction", "Outcome", "Pathway", "ChemicalClass"]:
        part = lay[lay["node_type"] == t]
        if part.empty:
            continue
        lit = [highlight is None or v in highlight for v in part["node_id"]]
        hover = [f"<b>{r.label}</b> ({t})<br>{r.description if isinstance(r.description, str) else ''}"
                 for r in part.itertuples()]
        fig.add_trace(go.Scatter(
            x=part["x"], y=part["y"], mode="markers+text", name=t if t != "ModeOfAction" else "mode of action",
            text=[lab if on else "" for lab, on in zip(part["label"], lit)], textposition="top center",
            textfont=dict(size=10), hovertext=hover, hoverinfo="text",
            marker=dict(size=[(9 + 2.2 * np.sqrt(d)) * (1.25 if (highlight and on) else 1) for d in part["degree"]],
                        color=TYPE_COLOURS[t], opacity=[1.0 if on else 0.18 for on in lit],
                        line=dict(color="white", width=1))))
    return _base(fig, 640, xaxis=dict(visible=False), yaxis=dict(visible=False),
                 legend=dict(orientation="h", y=-0.03), hoverlabel=dict(align="left"))


def path_figure(hops: list[dict]) -> go.Figure:
    """A path as a chain of boxes, left to right in the order the walk visits
    them, one arrow per step. Each arrow points the way its edge points, so
    a step the walk takes backwards (fenA works by the same mode of action
    as ituA) has an arrow pointing left. A statistics-only step is red and
    dotted, as everywhere else."""
    labels = [hops[0].get("step_from", hops[0]["from"])] + [h.get("step_to", h["to"]) for h in hops] if hops else []
    fig = go.Figure()
    for i, h in enumerate(hops):
        stats = h["relation"] == "associated_with"
        back = h.get("step_from", h["from"]) != h["from"]       # the edge points against the walk
        head, tail = (i, i + 1) if back else (i + 1, i)
        fig.add_annotation(x=head, y=0, ax=tail, ay=0, xref="x", yref="y", axref="x", ayref="y",
                           showarrow=True, arrowhead=3, arrowsize=1.2, arrowwidth=2,
                           arrowcolor=RED if stats else DARK_GREEN, standoff=34, startstandoff=34, text="")
        fig.add_annotation(x=i + 0.5, y=0.32, text=f"<i>{h['relation']}</i>", showarrow=False,
                           font=dict(color=RED if stats else DARK_GREEN, size=11))
    fig.add_trace(go.Scatter(x=list(range(len(labels))), y=[0] * len(labels), mode="markers+text",
                             text=labels, textposition="bottom center", hoverinfo="text",
                             marker=dict(size=26, color=BLUE, line=dict(color="white", width=2)),
                             showlegend=False))
    return _base(fig, 210, xaxis=dict(visible=False, range=[-0.6, max(len(labels) - 0.4, 0.6)]),
                 yaxis=dict(visible=False, range=[-0.8, 0.6]))
