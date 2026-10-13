"""
src/strainscope/graph.py (StrainScope Phase 5): the knowledge graph.
====================================================================

WHAT THIS MODULE DOES (in one sentence)
---------------------------------------
It turns everything the project knows (the clean tables, the domain model in
src/strainscope/ontology.py, the real KEGG / RefMet / BacDive / NCBI tables
when you have them, and the results of Phases 3 and 4) into one network of
things and connections, then uses that network to find hubs and communities,
to check the data against the biology, and to explain in plain words why a
strain ranks where it does, with a source on every step.

THE VERBS (run them from the project root, venv active)
------------------------------------------------------
    python src/strainscope/graph.py build      # tables + domain model -> the graph files
    python src/strainscope/graph.py analyse    # hubs, communities, knowledge vs data
    python src/strainscope/graph.py explain    # "why does this strain rank here?" for every strain
    python src/strainscope/graph.py publish    # artifacts/graph/*.csv -> DuckDB tables (kg_*)
    python src/strainscope/graph.py all        # the four above, in order (well under a minute)

and three ways to ask the finished graph a question:

    python src/strainscope/graph.py why STRAIN_0485       # one strain's explanation
    python src/strainscope/graph.py path ituA "disease suppression"
    python src/strainscope/graph.py show iturin           # a node and its neighbours

WHERE THINGS GO
---------------
  artifacts/graph/            the graph (nodes.csv, edges.csv, a GraphML copy)
                              and small result tables (committed: the app reads them)
  data/processed/strainscope.duckdb   gains kg_* tables after `publish`

Inside a dataset of Phase 9 (src/strainscope/paths.py) the same files go into
that dataset's folder. A gene or compound the domain model knows by name gets
its mechanism there too; one it doesn't know is linked to the outcome only by
the statistics of Phases 3 and 4, and its edges say "your data".

THE DECISIONS, WRITTEN DOWN (each is explained in docs/06-knowledge-graph.md)
---------------------------------------------------------------------------
1. ONTOLOGY FIRST. The kinds of nodes and connections are fixed in ontology.py
   before any data is read; an edge the ontology doesn't allow stops the build.
2. A SOURCE ON EVERY EDGE. Each connection records where it came from (the
   synthetic library, the domain model, KEGG, RefMet, BacDive, Phase 3 or
   Phase 4). A graph that can't say where a claim came from can't be trusted.
3. "PRODUCES" MEANS CLEARLY ABOVE BACKGROUND. The lab reads a little of every
   compound in every strain. A strain counts as producing a compound when its
   (cleaned) level is at least DETECTION_FOLD times that compound's median
   across all strains. Missing readings create no edge (unknown is not "no").
4. MECHANISM AND STATISTICS ARE KEPT APART. "acts_by" edges (from the domain
   model) say HOW something could work; "associated_with" edges (from Phases 3
   and 4) say the data links it to the outcome. Explanations use both and say
   which is which.
5. COMMUNITIES FROM CO-OCCURRENCE, GRADED. Genes and compounds that tend to
   turn up in the same strains are linked (phi correlation >= MIN_PHI) and
   grouped with the Louvain method (seed 42). Because the data is simulated,
   the groups can be graded against the planted arsenals.
6. CONCEPT ANALYSES IGNORE THE 600 STRAINS. Hubs between ideas and path
   queries run on the "knowledge layer" (ontology.KNOWLEDGE_TYPES), so the
   strain nodes don't drown out a few dozen concept nodes.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Make `strainscope` importable no matter where the script is run from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strainscope import paths  # noqa: E402
from strainscope.integrate import DB_PATH, ROOT, feature_annotations  # noqa: E402
from strainscope.ontology import (  # noqa: E402  (after the path fix)
    DOMAIN_SOURCE, FEATURE_MODES, KNOWLEDGE_TYPES, MODES_OF_ACTION, NODE_TYPES,
    OUTCOMES, RELATIONS, check_edge, ontology_tables)

ARTIFACTS = paths.HERE.graph            # artifacts/graph, or a dataset's (Phase 9)
INTEGRATION = paths.HERE.integration
MODEL = paths.HERE.model

SEED = 42                 # the project's one seed (Louvain is randomised)
DETECTION_FOLD = 4.0      # "produces" = at least 4x the compound's median level
MIN_PHI = 0.15            # co-occurrence strong enough to draw an edge
DIABLO_ROBUST = 0.8       # Phase 3's "robust" stability threshold
TOP_REASONS = 3           # reasons shown per strain
STATS_COST = 2.5          # a statistics-only hop counts as 2.5 steps in path searches
COMMON_IN_KINGDOM = 0.30  # a weapon this common in a kingdom is "expected"
TARGET = "disease suppression"
KINGDOM_WORD = {"Bacteria": "bacterial", "Fungi": "fungal", "Yeast": "yeast", "Oomycete": "oomycete"}

# Short, consistent provenance labels (stored on every edge).
P_SYNTH = ("your data (cleaned in Phase 2)" if paths.setting("kind", "library") == "yours"
           else "synthetic library (Phase 1, cleaned in Phase 2)")
P_DOMAIN = DOMAIN_SOURCE
P_PHASE3 = "Phase 3 (DIABLO signature, stability >= 0.8)"
P_PHASE4 = "Phase 4 (permutation importance of the winning model)"
P_KEGG = "KEGG (academic use)"
P_REFMET = "RefMet (Metabolomics Workbench)"
P_BACDIVE = "BacDive (DSMZ)"
P_NCBI = "NCBI Datasets"

PREFIX = {"Kingdom": "kingdom", "Genus": "genus", "Strain": "strain", "Gene": "gene",
          "Compound": "compound", "ModeOfAction": "mode", "Outcome": "outcome",
          "Pathway": "pathway", "ChemicalClass": "class", "ReferenceStrain": "refstrain"}


def node_id(node_type: str, name: str) -> str:
    """A readable, unique id such as 'gene:ituA' or 'compound:iturin'. The
    prefix keeps a gene and a compound with similar names apart."""
    return f"{PREFIX[node_type]}:{name}"


# =============================================================================
# 1. READ THE INPUTS
# =============================================================================

def _read_csv(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


def load_inputs(db_path: Path = DB_PATH, integration_dir: Path = INTEGRATION,
                model_dir: Path = MODEL) -> dict:
    """Everything the graph is built from. The clean tables are required;
    real tables and the Phase 3 and 4 results are used when present."""
    import duckdb
    if not Path(db_path).exists():
        sys.exit(f"No database at {db_path}.\n"
                 "Build it first:  python src/strainscope/harmonize.py")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = set(con.execute(
            "SELECT table_name FROM information_schema.tables").fetchdf()["table_name"])
        missing = {"genomics", "metabolomics", "phenotype"} - tables
        if missing:
            sys.exit(f"The database lacks {sorted(missing)}. Re-run: python src/strainscope/harmonize.py")
        data = {name: con.execute(f"SELECT * FROM {name} ORDER BY strain_id").fetchdf()
                for name in ("genomics", "metabolomics", "phenotype")}
        real = {name: con.execute(f"SELECT * FROM {name}").fetchdf()
                for name in sorted(tables) if name.startswith("real_")}
    finally:
        con.close()
    card_path = Path(model_dir) / "model_card.json"
    card = json.loads(card_path.read_text(encoding="utf-8")) if card_path.exists() else None
    ann_path = Path(integration_dir) / "feature_annotations.csv"   # every column of this data (Phase 3)
    return {
        **data,
        "real": real,
        "annotations": pd.read_csv(ann_path) if ann_path.exists() else feature_annotations(),
        "correlations": _read_csv(Path(integration_dir) / "cross_block_correlation.csv"),
        "signature": _read_csv(Path(integration_dir) / "diablo_signature.csv"),
        "importance": _read_csv(Path(model_dir) / "feature_importance.csv"),
        "predictions": _read_csv(Path(model_dir) / "predictions.csv"),
        "winner": card["model_key"] if card else None,
        "winner_name": card["model"] if card else None,
    }


# =============================================================================
# 2. BUILD THE NODE AND EDGE TABLES
# =============================================================================

class _Tables:
    """Collects nodes and edges as plain rows; a graph library comes later.
    Two lists of dictionaries are the simplest possible graph format, and
    they turn straight into the two CSV files we commit."""

    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []

    def node(self, node_type: str, name: str, **attrs) -> str:
        nid = node_id(node_type, name)
        row = self.nodes.setdefault(nid, {"node_id": nid, "node_type": node_type, "label": name})
        row.update({k: v for k, v in attrs.items() if v is not None and v == v})  # drop None/NaN
        return nid

    def edge(self, from_id: str, relation: str, to_id: str, provenance: str,
             weight: float | None = None, evidence: str = "") -> None:
        self.edges.append({"from_id": from_id, "relation": relation, "to_id": to_id,
                           "weight": None if weight is None else round(float(weight), 4),
                           "provenance": provenance, "evidence": evidence})


def _detected(level: pd.Series) -> tuple[pd.Series, float]:
    """Which strains clearly produce a compound: level >= DETECTION_FOLD x median."""
    median = float(level.median())
    if not np.isfinite(median) or median <= 0:
        return pd.Series(False, index=level.index), median
    return level >= DETECTION_FOLD * median, median


def build_tables(inp: dict) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Turn the inputs into a node table and an edge table. Returns the two
    tables and a list of notes about anything skipped."""
    t, notes = _Tables(), []
    ann = inp["annotations"].set_index("feature")
    pheno = inp["phenotype"].set_index("strain_id")
    genomics = inp["genomics"].set_index("strain_id")
    metab = inp["metabolomics"].set_index("strain_id")

    # -- Phase 4 importance and Phase 3 stability, by feature ------------------
    importance, reliable = {}, {}
    if inp["importance"] is not None and inp["winner"]:
        imp = inp["importance"][inp["importance"]["model_key"] == inp["winner"]]
        importance = dict(zip(imp["feature"], imp["importance_mean"]))
        reliable = dict(zip(imp["feature"], imp["reliably_important"].astype(bool)))
    else:
        notes.append("no Phase 4 results: run python src/strainscope/model.py all for importance edges and rankings")
    stability = {}
    if inp["signature"] is not None:
        sig = inp["signature"][inp["signature"]["component"] == 1]
        stability = dict(zip(sig["feature"], sig["stability"]))
    else:
        notes.append("no DIABLO signature (Phase 3 hasn't run, or R isn't installed): the graph has no "
                     "DIABLO edges; the model's importance edges are there")
    rho = {}
    if inp["correlations"] is not None:
        pairs = inp["correlations"][inp["correlations"]["is_producer_pair"].astype(bool)]
        rho = {(g, m): r for g, m, r in zip(pairs["gene"], pairs["metabolite"], pairs["spearman_rho"])}

    # -- outcomes and modes of action (the domain model) -----------------------
    for outcome, desc in OUTCOMES.items():
        t.node("Outcome", outcome, description=desc)
    for mode, (desc, outcome) in MODES_OF_ACTION.items():
        mid = t.node("ModeOfAction", mode, description=desc)
        t.edge(mid, "contributes_to", node_id("Outcome", outcome), P_DOMAIN)

    # -- kingdoms, genera, strains ---------------------------------------------
    preds = (inp["predictions"].set_index("strain_id")
             if inp["predictions"] is not None else None)
    known_genus = pheno["genus"].notna() & (pheno["genus"].astype(str).str.strip() != "")
    for sid, row in pheno.iterrows():
        gid = None
        if known_genus[sid]:    # your own data may not record the genus (Phase 9): then no genus or kingdom node
            t.node("Kingdom", row["kingdom"], description=NODE_TYPES["Kingdom"]["description"])
            gid = t.node("Genus", row["genus"], kingdom=row["kingdom"])
        attrs = {"kingdom": row["kingdom"], "genus": row["genus"] if known_genus[sid] else "not recorded",
                 "suppression_score": float(row["suppression_score"]),
                 "is_effective": int(row["is_effective"])}
        if preds is not None and sid in preds.index:
            attrs.update(probability=float(preds.loc[sid, "probability"]),
                         rank=int(preds.loc[sid, "rank"]))
        s = t.node("Strain", sid, **attrs)
        if gid is not None:
            t.edge(s, "belongs_to", gid, P_SYNTH, evidence="genus column after Phase 2's fixes")
    for genus, kingdom in pheno.loc[known_genus, ["genus", "kingdom"]].drop_duplicates().itertuples(index=False):
        t.edge(node_id("Genus", genus), "in_kingdom", node_id("Kingdom", kingdom), P_SYNTH)

    # -- genes and compounds, with what we know about each ---------------------
    def feature_attrs(name: str) -> dict:
        a = {"role": ann.loc[name, "role"], "arsenal": ann.loc[name, "arsenal"],
             "description": ann.loc[name, "description"]} if name in ann.index else {"role": "unannotated"}
        if name in importance:
            a.update(importance=float(importance[name]), reliably_important=bool(reliable[name]))
        if name in stability:
            a["diablo_stability"] = float(stability[name])
        return a

    genes = [c for c in genomics.columns]
    compounds = [c for c in metab.columns]
    for g in genes:
        t.node("Gene", g, **feature_attrs(g))
    for c in compounds:
        t.node("Compound", c, **feature_attrs(c))

    # strain -> gene: carries (a gene call of 1; a missing call is no edge)
    for g in genes:
        carriers = genomics.index[genomics[g] == 1]
        gid = node_id("Gene", g)
        for sid in carriers:
            t.edge(node_id("Strain", sid), "carries", gid, P_SYNTH)
        t.nodes[gid]["n_strains"] = int(len(carriers))

    # strain -> compound: produces (clearly above background)
    for c in compounds:
        hit, median = _detected(metab[c])
        cid = node_id("Compound", c)
        for sid in metab.index[hit.fillna(False)]:
            fold = metab.loc[sid, c] / median
            t.edge(node_id("Strain", sid), "produces", cid, P_SYNTH, weight=fold,
                   evidence=f"{metab.loc[sid, c]:.1f} = {fold:.1f}x the median ({median:.2f})")
        t.nodes[cid].update(n_strains=int(hit.sum()), median_level=round(median, 3))

    # gene -> compound: makes (the producer pairs of the domain model)
    if "producer_gene" in ann.columns:
        for c, g in ann["producer_gene"].dropna().items():
            if g in genes and c in compounds:
                r = rho.get((g, c))
                ev = f"Phase 3 measured Spearman rho {r:.2f} between gene and product" if r is not None else ""
                t.edge(node_id("Gene", g), "makes", node_id("Compound", c), P_DOMAIN,
                       weight=r, evidence=ev)

    # gene/compound -> mode of action -> outcome: acts_by (the mechanism)
    for feature, modes in FEATURE_MODES.items():
        kind = "Gene" if feature in genes else "Compound" if feature in compounds else None
        if kind is None:
            continue
        for mode in modes:
            t.edge(node_id(kind, feature), "acts_by", node_id("ModeOfAction", mode), P_DOMAIN)

    # gene/compound -> outcome: associated_with (the statistics)
    target = node_id("Outcome", TARGET)
    for feature in genes + compounds:
        kind = "Gene" if feature in genes else "Compound"
        if reliable.get(feature):
            t.edge(node_id(kind, feature), "associated_with", target, P_PHASE4,
                   weight=importance[feature],
                   evidence=f"{inp['winner_name']}: AUC drops {importance[feature]:.3f} when shuffled")
        if stability.get(feature, 0) >= DIABLO_ROBUST:
            t.edge(node_id(kind, feature), "associated_with", target, P_PHASE3,
                   weight=stability[feature],
                   evidence=f"picked in {stability[feature]:.0%} of DIABLO re-fits")

    _add_real(t, inp["real"], compounds, notes)
    nodes = pd.DataFrame(list(t.nodes.values()))
    edges = pd.DataFrame(t.edges)
    return nodes, edges, notes


def _add_real(t: _Tables, real: dict, compounds: list[str], notes: list[str]) -> None:
    """Add the real-data layer when the Phase 1b and 1c tables are present."""
    if not real:
        notes.append("no real tables yet (Phases 1b and 1c): the graph has no pathway, "
                      "chemical-class or reference-strain nodes")
        return
    pub = real.get("real_compounds")
    if pub is not None:
        for _, r in pub.iterrows():
            if r["metabolite"] in compounds:
                nid = node_id("Compound", r["metabolite"])
                if r.get("status") == "found":
                    t.nodes[nid].update({k: v for k, v in {
                        "pubchem_cid": r.get("cid"), "formula": r.get("molecular_formula"),
                        "molecular_weight": r.get("molecular_weight")}.items()
                        if v is not None and v == v and v != ""})
                elif r.get("status") == "not_a_small_molecule":
                    t.nodes[nid]["chemistry_note"] = str(r.get("note", ""))
    kegg = real.get("real_compound_pathways")
    if kegg is not None:
        for _, r in kegg.iterrows():
            if r["metabolite"] not in compounds or not isinstance(r["pathway_id"], str):
                continue
            name = r["pathway_name"] if isinstance(r.get("pathway_name"), str) and r["pathway_name"] else ""
            pid = t.node("Pathway", r["pathway_id"], description=name)
            t.edge(node_id("Compound", r["metabolite"]), "in_pathway", pid, P_KEGG,
                   evidence=f"KEGG {r['kegg_id']} in {r['pathway_id']}")
    refmet = real.get("real_refmet")
    if refmet is not None:
        for _, r in refmet.iterrows():
            if r["metabolite"] not in compounds or r.get("status") != "found":
                continue
            main, sup = r.get("main_class"), r.get("super_class")
            if isinstance(main, str) and main:
                mid = t.node("ChemicalClass", main, level="main class")
                t.edge(node_id("Compound", r["metabolite"]), "classified_as", mid, P_REFMET,
                       evidence=f"RefMet name {r.get('refmet_name', '')}")
                if isinstance(sup, str) and sup and sup != main:
                    sid = t.node("ChemicalClass", sup, level="super class")
                    if not any(e["from_id"] == mid and e["to_id"] == sid for e in t.edges):
                        t.edge(mid, "subclass_of", sid, P_REFMET)
    bac = real.get("real_strains")
    if bac is not None:
        for _, r in bac.iterrows():
            genus = r.get("genus")
            if not isinstance(genus, str) or not genus:
                continue
            gid = node_id("Genus", genus)
            if gid not in t.nodes:                       # a genus only BacDive knows
                t.node("Genus", genus, kingdom="Bacteria")
                t.edge(gid, "in_kingdom", t.node("Kingdom", "Bacteria"), P_BACDIVE)
            label = r.get("full_name") if isinstance(r.get("full_name"), str) and r.get("full_name") \
                else f"{genus} (BacDive {r['bacdive_id']})"
            rid = t.node("ReferenceStrain", f"BacDive {r['bacdive_id']}", full_name=label,
                         isolation_source=r.get("isolation_source"), country=r.get("country"))
            t.edge(rid, "belongs_to", gid, P_BACDIVE)
    genomes = real.get("real_genomes")
    if genomes is not None and len(genomes):
        size = pd.to_numeric(genomes["genome_length_bp"], errors="coerce") / 1e6
        per = genomes.assign(mb=size).groupby("genus_query")["mb"].agg(["count", "median"])
        for genus, row in per.iterrows():
            gid = node_id("Genus", genus)
            if gid in t.nodes:
                t.nodes[gid].update(n_real_genomes=int(row["count"]),
                                    median_genome_mb=round(float(row["median"]), 2),
                                    genome_source=P_NCBI)


def validate(nodes: pd.DataFrame, edges: pd.DataFrame) -> list[str]:
    """Every edge must be allowed by the ontology, point at existing nodes and
    carry a source. Returns a list of problems (empty means all good)."""
    types = dict(zip(nodes["node_id"], nodes["node_type"]))
    problems = []
    for e in edges.itertuples(index=False):
        if e.from_id not in types or e.to_id not in types:
            problems.append(f"edge {e.from_id} -{e.relation}-> {e.to_id} points at a missing node")
            continue
        why = check_edge(e.relation, types[e.from_id], types[e.to_id])
        if why:
            problems.append(f"{e.from_id} -{e.relation}-> {e.to_id}: {why}")
        if not isinstance(e.provenance, str) or not e.provenance:
            problems.append(f"{e.from_id} -{e.relation}-> {e.to_id} has no source")
    unknown = set(nodes["node_type"]) - set(NODE_TYPES)
    if unknown:
        problems.append(f"unknown node types: {sorted(unknown)}")
    return problems


# Columns that hold whole numbers (a CSV column with gaps reads back as
# decimals, so "rank 1" would print as "rank 1.0" without this).
INT_ATTRS = ("rank", "is_effective", "n_strains", "n_real_genomes", "pubchem_cid")


def to_networkx(nodes: pd.DataFrame, edges: pd.DataFrame):
    """The two tables as a NetworkX graph. A MultiDiGraph allows several
    edges between the same two nodes (one per source) and keeps direction."""
    import networkx as nx
    G = nx.MultiDiGraph()
    for row in nodes.to_dict("records"):
        attrs = {k: _plain(v) for k, v in row.items() if k != "node_id" and _plain(v) is not None}
        for k in INT_ATTRS:
            if isinstance(attrs.get(k), float):
                attrs[k] = int(attrs[k])
        G.add_node(row["node_id"], **attrs)
    for row in edges.to_dict("records"):
        G.add_edge(row["from_id"], row["to_id"], key=f"{row['relation']}|{row['provenance']}",
                   **{k: _plain(v) for k, v in row.items()
                      if k not in ("from_id", "to_id") and _plain(v) is not None})
    return G


def _plain(v):
    """numpy and pandas values -> plain Python (GraphML only accepts those);
    NaN and empty text -> None, which means 'leave the attribute out'."""
    if v is None:
        return None
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v, str):
        return v if v else None
    return str(v)


def build(db_path: Path = DB_PATH, integration_dir: Path = INTEGRATION, model_dir: Path = MODEL,
          artifacts_dir: Path = ARTIFACTS, verbose: bool = True) -> dict:
    """Build the graph and write it to artifacts/graph/."""
    import networkx as nx
    t0 = time.time()
    inp = load_inputs(db_path, integration_dir, model_dir)
    nodes, edges, notes = build_tables(inp)
    problems = validate(nodes, edges)
    if problems:
        sys.exit("The graph breaks the ontology; nothing was saved:\n  " + "\n  ".join(problems[:10]))
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    nodes.to_csv(artifacts_dir / "nodes.csv", index=False)
    edges.to_csv(artifacts_dir / "edges.csv", index=False)
    G = to_networkx(nodes, edges)
    knowledge = G.subgraph([n for n, d in G.nodes(data=True) if d["node_type"] in KNOWLEDGE_TYPES])
    nx.write_graphml(knowledge, artifacts_dir / "knowledge_layer.graphml")
    ont_nodes, ont_rels = ontology_tables()
    ont_nodes.to_csv(artifacts_dir / "ontology_node_types.csv", index=False)
    ont_rels.to_csv(artifacts_dir / "ontology_relations.csv", index=False)
    isolated = [n for n in G.nodes if G.degree(n) == 0]
    summary = pd.concat([
        nodes["node_type"].value_counts().rename_axis("item").reset_index(name="count").assign(kind="nodes"),
        edges.groupby(["relation", "provenance"]).size().reset_index(name="count")
             .assign(item=lambda d: d["relation"] + " | " + d["provenance"], kind="edges")[["item", "count", "kind"]],
    ], ignore_index=True)[["kind", "item", "count"]]
    summary.to_csv(artifacts_dir / "graph_summary.csv", index=False)
    if verbose:
        _print_build(nodes, edges, isolated, notes, artifacts_dir, time.time() - t0)
    return {"nodes": len(nodes), "edges": len(edges), "isolated": isolated, "notes": notes}


def _print_build(nodes, edges, isolated, notes, artifacts_dir, seconds) -> None:
    print("  ── Phase 5: the knowledge graph ────────────────────────────────")
    order = list(NODE_TYPES)
    counts = nodes["node_type"].value_counts()
    print(f"  nodes: {len(nodes):,}   " + " · ".join(f"{t} {counts[t]}" for t in order if t in counts))
    print(f"  edges: {len(edges):,}")
    by_rel = edges.groupby("relation").size()
    for rel in RELATIONS:
        if rel in by_rel:
            sources = sorted(edges.loc[edges["relation"] == rel, "provenance"].unique())
            print(f"    {rel:<16} {by_rel[rel]:>6,}   from: {'; '.join(sources)}")
    print("  checks: every edge allowed by the ontology ✓ · every edge has a source ✓"
          + (f" · {len(isolated)} node(s) with no connections: {', '.join(i.split(':', 1)[1] for i in isolated[:6])}"
             if isolated else " · no isolated nodes ✓"))
    for n in notes:
        print(f"  note: {n}")
    print(f"  graph → {_rel(artifacts_dir)}/nodes.csv, edges.csv, knowledge_layer.graphml   ({seconds:.0f} s)")


# =============================================================================
# 3. LOAD THE SAVED GRAPH (every later step starts here)
# =============================================================================

def load_graph(artifacts_dir: Path = ARTIFACTS):
    """Rebuild the NetworkX graph from nodes.csv and edges.csv."""
    artifacts_dir = Path(artifacts_dir)
    if not (artifacts_dir / "nodes.csv").exists():
        sys.exit("No graph yet. Run:  python src/strainscope/graph.py build")
    nodes = pd.read_csv(artifacts_dir / "nodes.csv")
    edges = pd.read_csv(artifacts_dir / "edges.csv")
    return to_networkx(nodes, edges)


def knowledge_view(G, keep: tuple[str, ...] = ()):
    """An undirected, simple view of the knowledge layer (plus any nodes in
    `keep`), for hubs and shortest paths. Direction matters for reading an
    edge aloud, but a path question ("how are these two linked?") can walk
    either way."""
    import networkx as nx
    sub = G.subgraph([n for n, d in G.nodes(data=True)
                      if d["node_type"] in KNOWLEDGE_TYPES or n in keep])
    return nx.Graph(sub)


# =============================================================================
# 4. ANALYSE: hubs, communities, knowledge vs data
# =============================================================================

def hubs(G) -> pd.DataFrame:
    """For every concept node: how many connections it has, how many strains
    touch it, and how often it sits on the shortest route between two other
    concepts (betweenness, measured on the knowledge layer)."""
    import networkx as nx
    full = nx.Graph(G)
    kv = knowledge_view(G)
    between = nx.betweenness_centrality(kv, normalized=True)
    rows = []
    for n, d in G.nodes(data=True):
        if d["node_type"] in ("Strain", "ReferenceStrain"):
            continue
        neigh = list(full.neighbors(n))
        rows.append({"node_id": n, "label": d["label"], "node_type": d["node_type"],
                     "degree": len(neigh),
                     "strains_connected": sum(G.nodes[m]["node_type"] == "Strain" for m in neigh),
                     "concept_degree": kv.degree(n) if n in kv else 0,
                     "betweenness": round(between.get(n, 0.0), 4),
                     "role": d.get("role", "")})
    out = pd.DataFrame(rows).sort_values(["degree", "betweenness"], ascending=False)
    return out.reset_index(drop=True)


def presence_matrix(G) -> pd.DataFrame:
    """Strains x features (genes carried, compounds produced), 1 or 0."""
    rows = {}
    for s, f, data in G.edges(data=True):
        if data["relation"] in ("carries", "produces"):
            rows.setdefault(s, set()).add(f)
    strains = sorted(rows)
    features = sorted({f for fs in rows.values() for f in fs})
    m = pd.DataFrame(0, index=strains, columns=features, dtype=int)
    for s, fs in rows.items():
        m.loc[s, sorted(fs)] = 1
    return m


def co_occurrence(G, min_phi: float = MIN_PHI):
    """Link two features when they turn up in the same strains more often than
    chance (phi correlation >= min_phi). Housekeeping genes are left out: a
    gene every strain carries co-occurs with everything and says nothing."""
    import networkx as nx
    m = presence_matrix(G)
    keep = [f for f in m.columns if G.nodes[f].get("role") != "housekeeping" and m[f].sum() >= 5]
    m = m[keep]
    phi = np.corrcoef(m.to_numpy().T)
    C = nx.Graph()
    for f in keep:
        C.add_node(f, label=G.nodes[f]["label"], node_type=G.nodes[f]["node_type"],
                   arsenal=G.nodes[f].get("arsenal", ""), role=G.nodes[f].get("role", ""),
                   n_strains=int(m[f].sum()))
    for i in range(len(keep)):
        for j in range(i + 1, len(keep)):
            if phi[i, j] >= min_phi:
                C.add_edge(keep[i], keep[j], weight=round(float(phi[i, j]), 4))
    return C


def communities(C, seed: int = SEED) -> pd.DataFrame:
    """Louvain communities on the co-occurrence graph. A feature with no strong
    ties to anything gets community -1 ('no strong ties')."""
    import networkx as nx
    linked = C.subgraph([n for n in C.nodes if C.degree(n) > 0])
    groups = nx.community.louvain_communities(linked, weight="weight", seed=seed) if len(linked) else []
    # number communities by size (largest first), then by first member, so the
    # numbering doesn't depend on the order the algorithm happened to return
    groups = sorted((sorted(g) for g in groups), key=lambda g: (-len(g), g[0]))
    label = {n: i + 1 for i, g in enumerate(groups) for n in g}
    rows = [{"node_id": n, "label": d["label"], "node_type": d["node_type"],
             "community": label.get(n, -1), "arsenal": d["arsenal"], "role": d["role"],
             "n_strains": d["n_strains"], "ties": C.degree(n)}
            for n, d in C.nodes(data=True)]
    return pd.DataFrame(rows).sort_values(["community", "arsenal", "label"]).reset_index(drop=True)


def grade_communities(comm: pd.DataFrame) -> dict:
    """How well the communities match the planted arsenals (signal features
    only: their arsenal is what the simulation put there). Purity: the share
    of signal features whose community's most common arsenal is their own."""
    from sklearn.metrics import adjusted_rand_score
    sig = comm[(comm["role"] == "signal") & (comm["community"] > 0)]
    if sig.empty:
        return {"purity": float("nan"), "ari": float("nan"), "signal_features": 0}
    majority = sig.groupby("community")["arsenal"].agg(lambda s: s.value_counts().index[0])
    purity = float((sig["arsenal"] == sig["community"].map(majority)).mean())
    ari = float(adjusted_rand_score(sig["arsenal"], sig["community"]))
    return {"purity": round(purity, 3), "ari": round(ari, 3), "signal_features": int(len(sig))}


def agreement(G) -> pd.DataFrame:
    """Knowledge vs data, feature by feature. 'mechanism' = the domain model
    links it to disease suppression; 'model' = Phase 4 found it reliably
    important; 'diablo' = Phase 3's robust signature contains it."""
    target = node_id("Outcome", TARGET)
    rows = []
    for n, d in G.nodes(data=True):
        if d["node_type"] not in ("Gene", "Compound") or d.get("role") == "housekeeping":
            continue
        modes = [m for _, m, e in G.out_edges(n, data=True) if e["relation"] == "acts_by"]
        mech = any(any(e["relation"] == "contributes_to" and o == target
                       for _, o, e in G.out_edges(m, data=True)) for m in modes)
        stats = {e["provenance"] for _, o, e in G.out_edges(n, data=True)
                 if e["relation"] == "associated_with" and o == target}
        model, diablo = P_PHASE4 in stats, P_PHASE3 in stats
        if mech and (model or diablo):
            verdict = "confirmed: mechanism and data agree"
        elif mech:
            verdict = "mechanism only: the data did not need it"
        elif model or diablo:
            verdict = "data only: no known mechanism (treat with care)"
        else:
            verdict = "neither: no link to disease suppression"
        rows.append({"node_id": n, "label": d["label"], "node_type": d["node_type"],
                     "role": d.get("role", ""), "arsenal": d.get("arsenal", ""),
                     "mechanism": mech, "model_reliable": model, "diablo_robust": diablo,
                     "modes": "; ".join(G.nodes[m]["label"] for m in modes),
                     "verdict": verdict})
    order = {"confirmed": 0, "mechanism": 1, "data": 2, "neither": 3}
    out = pd.DataFrame(rows)
    out["_o"] = out["verdict"].str.split(":").str[0].str.split().str[0].map(order)
    return out.sort_values(["_o", "node_type", "label"]).drop(columns="_o").reset_index(drop=True)


def analyse(artifacts_dir: Path = ARTIFACTS, verbose: bool = True) -> dict:
    t0 = time.time()
    artifacts_dir = Path(artifacts_dir)
    G = load_graph(artifacts_dir)
    hub = hubs(G)
    hub.to_csv(artifacts_dir / "hubs.csv", index=False)
    C = co_occurrence(G)
    comm = communities(C)
    comm.to_csv(artifacts_dir / "communities.csv", index=False)
    pd.DataFrame([{"node_a": a, "node_b": b, "phi": d["weight"]} for a, b, d in C.edges(data=True)]
                 ).to_csv(artifacts_dir / "co_occurrence_edges.csv", index=False)
    grade = grade_communities(comm)
    n_comm = int(comm.loc[comm["community"] > 0, "community"].nunique())
    check = pd.DataFrame([{"features": len(comm), "communities": n_comm,
                           "no_strong_ties": int((comm["community"] < 0).sum()),
                           "min_phi": MIN_PHI, "seed": SEED, **grade}])
    check.to_csv(artifacts_dir / "community_check.csv", index=False)
    agree = agreement(G)
    agree.to_csv(artifacts_dir / "knowledge_vs_data.csv", index=False)
    if verbose:
        _print_analyse(hub, comm, check.iloc[0], agree, artifacts_dir, time.time() - t0)
    return {"hubs": hub, "communities": comm, "check": check.iloc[0].to_dict(), "agreement": agree}


def _print_analyse(hub, comm, check, agree, artifacts_dir, seconds) -> None:
    print("  ── Hubs: the most connected nodes ─────────────────────────────────")
    print("  touching the most strains: " + ", ".join(
        f"{r.label} ({r.strains_connected})" for r in hub.head(4).itertuples(index=False)))
    concept = hub.sort_values(["concept_degree", "betweenness"], ascending=False).head(4)
    print("  most links between concepts: " + ", ".join(
        f"{r.label} ({r.concept_degree})" for r in concept.itertuples(index=False)))
    bridge = hub.sort_values("betweenness", ascending=False).head(3)
    print("  the biggest bridges (betweenness): " + ", ".join(
        f"{r.label} ({r.betweenness:.2f})" for r in bridge.itertuples(index=False)))
    print("  ── Communities: what turns up together in the same strains ──────")
    for c, grp in comm[comm["community"] > 0].groupby("community"):
        top = grp["arsenal"].value_counts()
        names = ", ".join(grp["label"].head(7)) + (" …" if len(grp) > 7 else "")
        print(f"  community {c}: {len(grp):>2} features · mostly {top.index[0]} ({top.iloc[0]}/{len(grp)}) · {names}")
    loose = comm[comm["community"] < 0]
    if len(loose):
        print(f"  no strong ties ({len(loose)}): {', '.join(loose['label'])}")
    if int(check["signal_features"]):
        print(f"  graded against the planted arsenals: purity {check['purity']:.2f} · "
              f"adjusted Rand index {check['ari']:.2f} ({int(check['signal_features'])} signal features)")
    else:
        print("  not graded: there's no answer key for this data (no planted arsenals to compare with)")
    print("  ── Knowledge vs data (disease suppression) ─────────────────────────")
    for verdict, grp in agree.groupby("verdict", sort=False):
        print(f"  {verdict:<48} {len(grp):>2}  {', '.join(grp['label'].head(8))}{' …' if len(grp) > 8 else ''}")
    print(f"  results → {_rel(artifacts_dir)}/   ({seconds:.0f} s)")


# =============================================================================
# 5. EXPLAIN: "why does this strain rank where it does?"
# =============================================================================

def _out(G, n, relation):
    return [(m, e) for _, m, e in G.out_edges(n, data=True) if e["relation"] == relation]


def _reaches_target(G, feature) -> list[str]:
    """The modes of action through which a feature reaches disease suppression."""
    target = node_id("Outcome", TARGET)
    return [m for m, _ in _out(G, feature, "acts_by")
            if any(o == target for o, _ in _out(G, m, "contributes_to"))]


def explain_strain(G, strain: str, top: int = TOP_REASONS) -> list[dict]:
    """The reasons behind one strain's rank, each a walk through the graph
    with the source of every step. Three kinds of reason:
      mechanism  carries a weapon gene (and makes its compound) that acts by a
                 known mode of action on disease suppression;
      data only  has a feature the model leans on that no known mechanism
                 explains (a flag, not a reason to trust it);
      missing    lacks a weapon common in its kingdom (carried by at least
                 COMMON_IN_KINGDOM of its strains)."""
    sid = strain if strain.startswith("strain:") else node_id("Strain", strain)
    if sid not in G:
        raise KeyError(f"no strain called {strain!r} in the graph")
    s = G.nodes[sid]
    carried = {g for g, _ in _out(G, sid, "carries")}
    produced = {c: e for c, e in _out(G, sid, "produces")}
    imp = lambda n: G.nodes[n].get("importance", 0.0) or 0.0  # noqa: E731

    def prov(*parts):
        return "; ".join(dict.fromkeys(p for p in parts if p))

    reasons, used = [], set()
    for g in carried:
        modes = _reaches_target(G, g)
        if not modes:
            continue
        made = [c for c, _ in _out(G, g, "makes") if c in produced]
        c = made[0] if made else None
        used.update([g] + ([c] if c else []))
        text = f"carries {G.nodes[g]['label']}"
        if c:
            text += f" and produces {G.nodes[c]['label']} ({produced[c]['weight']:.1f}x the usual level)"
        mode_names = " and ".join(G.nodes[m]["label"] for m in modes)
        path = [sid, g] + ([c] if c else []) + [modes[0], node_id("Outcome", TARGET)]
        reasons.append({"kind": "mechanism", "score": imp(g) + (imp(c) if c else 0.0),
                        "feature": G.nodes[g]["label"], "compound": G.nodes[c]["label"] if c else "",
                        "mode": mode_names,
                        "text": f"{text}: {mode_names}",
                        "path": " > ".join(G.nodes[p]["label"] for p in path),
                        "provenance": prov(P_SYNTH, P_DOMAIN, P_PHASE4 if imp(g) else "")})
    for c, e in produced.items():                       # a compound without its gene
        if c in used:
            continue
        modes = _reaches_target(G, c)
        if not modes:
            continue
        mode_names = " and ".join(G.nodes[m]["label"] for m in modes)
        makers = [g for g, _, rel in G.in_edges(c, data="relation") if rel == "makes"]
        note = ""
        if makers and all(_gene_unknown(G, sid, g) for g in makers):
            note = f" (its {G.nodes[makers[0]]['label']} call is missing)"
        elif makers:
            note = (f" without carrying {G.nodes[makers[0]]['label']}, the gene that makes it"
                    " (background noise just over the line, or a spike?)")
        reasons.append({"kind": "mechanism", "score": imp(c), "feature": "",
                        "compound": G.nodes[c]["label"], "mode": mode_names,
                        "text": f"produces {G.nodes[c]['label']} ({e['weight']:.1f}x the usual level)"
                                f"{note}: {mode_names}",
                        "path": " > ".join(G.nodes[p]["label"] for p in [sid, c, modes[0], node_id("Outcome", TARGET)]),
                        "provenance": prov(P_SYNTH, P_DOMAIN)})
    n_paths = len(reasons)
    reasons = sorted(reasons, key=lambda r: -r["score"])[:top]

    flags = []
    for f in carried | set(produced):
        if _reaches_target(G, f):
            continue
        stats = [e for o, e in _out(G, f, "associated_with") if o == node_id("Outcome", TARGET)]
        if any(e["provenance"] == P_PHASE4 for e in stats):
            verb = "carries" if G.nodes[f]["node_type"] == "Gene" else "produces"
            flags.append({"kind": "data only", "score": imp(f), "feature": G.nodes[f]["label"],
                          "compound": "", "mode": "",
                          "text": f"{verb} {G.nodes[f]['label']}: the model leans on it a little, "
                                  "but no known mechanism links it to disease suppression",
                          "path": f"{s['label']} > {G.nodes[f]['label']} > {TARGET} (statistics only)",
                          "provenance": P_PHASE4})

    missing = []
    expected = G.graph.get("expected", {}).get(s["kingdom"], [])
    for g, share in expected:
        if g not in carried and not _gene_unknown(G, sid, g):
            missing.append({"kind": "missing", "score": imp(g), "feature": G.nodes[g]["label"], "compound": "",
                            "mode": " and ".join(G.nodes[m]["label"] for m in _reaches_target(G, g)),
                            "text": f"lacks {G.nodes[g]['label']}, which {share:.0%} of {KINGDOM_WORD.get(s['kingdom'], s['kingdom'])} strains carry",
                            "path": f"{s['label']} (no edge to {G.nodes[g]['label']})",
                            "provenance": P_SYNTH})
    missing = sorted(missing, key=lambda r: -r["score"])[:2]
    out = []
    for order, r in enumerate(reasons + flags + missing, start=1):
        out.append({"strain_id": s["label"], "rank": s.get("rank"), "probability": s.get("probability"),
                    "is_effective": s.get("is_effective"), "mechanism_paths": n_paths, "order": order,
                    **{k: v for k, v in r.items() if k != "score"}, "weight": round(r["score"], 4)})
    return out


def _gene_unknown(G, sid, g) -> bool:
    """True when the strain's call for this gene was missing (no edge either
    way). The graph only stores known carriers, so 'unknown' calls are kept
    in G.graph['unknown_calls'] by attach_expectations()."""
    return (sid, g) in G.graph.get("unknown_calls", set())


def attach_expectations(G, db_path: Path = DB_PATH) -> None:
    """Store two facts the explanation needs: which weapons are common in each
    kingdom (carried by >= COMMON_IN_KINGDOM of its strains, computed from the
    graph) and which gene calls were missing in the data."""
    strains = [n for n, d in G.nodes(data=True) if d["node_type"] == "Strain"]
    kingdom_of = {s: G.nodes[s]["kingdom"] for s in strains}
    sizes = pd.Series(kingdom_of).value_counts()
    counts: dict[tuple[str, str], int] = {}
    for s, g, e in G.edges(data=True):
        # a weapon: a gene whose known mechanism leads to disease suppression
        # (in the library, exactly the planted drivers; in your own data, any
        # gene the domain model knows that way)
        if e["relation"] == "carries" and _reaches_target(G, g):
            counts[(kingdom_of[s], g)] = counts.get((kingdom_of[s], g), 0) + 1
    expected: dict[str, list] = {}
    for (k, g), n in counts.items():
        share = n / sizes[k]
        if share >= COMMON_IN_KINGDOM:
            expected.setdefault(k, []).append((g, share))
    G.graph["expected"] = {k: sorted(v, key=lambda x: -x[1]) for k, v in expected.items()}
    unknown = set()
    try:
        import duckdb
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            gen = con.execute("SELECT * FROM genomics").fetchdf().set_index("strain_id")
        finally:
            con.close()
        for g in gen.columns:
            for sid in gen.index[gen[g].isna()]:
                unknown.add((node_id("Strain", sid), node_id("Gene", g)))
    except Exception:  # no database: every absent edge is treated as "lacks"
        pass
    G.graph["unknown_calls"] = unknown


def explain(artifacts_dir: Path = ARTIFACTS, db_path: Path = DB_PATH, verbose: bool = True) -> pd.DataFrame:
    t0 = time.time()
    artifacts_dir = Path(artifacts_dir)
    G = load_graph(artifacts_dir)
    attach_expectations(G, db_path)
    strains = sorted((n for n, d in G.nodes(data=True) if d["node_type"] == "Strain"),
                     key=lambda n: (G.nodes[n].get("rank", 10**6), n))
    rows = [r for s in strains for r in explain_strain(G, s)]
    table = pd.DataFrame(rows)
    table.to_csv(artifacts_dir / "explanations.csv", index=False)
    if verbose:
        print("  ── Why strains rank where they do (walks through the graph) ───────")
        top = strains[0]
        _print_strain(G, top, table)
        k = G.nodes[top]["kingdom"]
        low = [s for s in strains if G.nodes[s]["kingdom"] == k][-1]
        _print_strain(G, low, table)
        mech = table[table["kind"] == "mechanism"]
        has = mech.groupby("strain_id").size()
        top50 = [G.nodes[s]["label"] for s in strains[:50]]
        print(f"  of the top 50 strains, {sum(has.get(s, 0) > 0 for s in top50)} have at least one "
              f"mechanism path; {table.loc[table['kind'] == 'data only', 'strain_id'].nunique()} strains "
              "carry a data-only flag")
        print(f"  results → {_rel(artifacts_dir)}/explanations.csv   ({time.time() - t0:.0f} s)")
    return table


def _print_strain(G, sid, table) -> None:
    d = G.nodes[sid]
    rank = f"rank {d['rank']} of {sum(1 for _, x in G.nodes(data=True) if x['node_type'] == 'Strain')}" \
        if "rank" in d else "not ranked (no Phase 4 results)"
    prob = f", predicted {d['probability']:.0%}" if "probability" in d else ""
    truth = "effective" if d.get("is_effective") == 1 else "not effective"
    print(f"  {d['label']} ({d['genus']}, {KINGDOM_WORD.get(d['kingdom'], d['kingdom'])}): {rank}{prob}; in the data: {truth}")
    rows = table[table["strain_id"] == d["label"]]
    if rows.empty:
        print("    no mechanism path, no flags")
    for r in rows.itertuples(index=False):
        mark = {"mechanism": "+", "data only": "?", "missing": "-"}[r.kind]
        print(f"    {mark} {r.text}")
    if not rows.empty:
        shown = int((rows["kind"] == "mechanism").sum())
        extra = int(rows["mechanism_paths"].iloc[0]) - shown
        if extra > 0:
            print(f"    (+ {extra} more mechanism path{'s' if extra > 1 else ''}; "
                  f"`show {d['label']}` lists everything it carries and produces)")


# =============================================================================
# 6. ASK THE GRAPH: find a node, show it, walk a path
# =============================================================================

def find_node(G, text: str) -> str:
    """Accept 'gene:ituA', 'ituA', 'iturin', 'STRAIN_0485' or a pathway id,
    ignoring upper/lower case. Genes win over compounds on an exact tie."""
    if text in G:
        return text
    low = text.lower()
    exact = [n for n, d in G.nodes(data=True) if str(d["label"]).lower() == low]
    if exact:
        rank = {t: i for i, t in enumerate(["Strain", "Gene", "Compound", "ModeOfAction", "Outcome",
                                            "Pathway", "ChemicalClass", "Genus", "Kingdom", "ReferenceStrain"])}
        return sorted(exact, key=lambda n: rank.get(G.nodes[n]["node_type"], 99))[0]
    partial = [n for n, d in G.nodes(data=True) if low in str(d["label"]).lower()]
    if len(partial) == 1:
        return partial[0]
    hint = f" Did you mean one of: {', '.join(G.nodes[n]['label'] for n in partial[:6])}?" if partial else ""
    raise KeyError(f"nothing in the graph is called {text!r}.{hint}")


def _hop_edges(G, x, y) -> list[dict]:
    """All edges between two nodes, whichever way they point."""
    return list((G.get_edge_data(x, y) or {}).values()) + list((G.get_edge_data(y, x) or {}).values())


def path(G, a: str, b: str) -> list[dict]:
    """The best walk between two nodes through the knowledge layer (a strain
    may be an end point, never a stepping stone). Mechanism and fact edges
    cost 1 step; a statistics-only edge (associated_with) costs STATS_COST
    steps, so the search prefers a route that says HOW over a shortcut that
    only says "the data links them". Each hop says which way the edge points
    ("from", "relation", "to", read aloud the way the edge points), what it
    means and where it came from. "step_from" and "step_to" give the same
    two names in the order the walk visits them: a walk can cross an edge
    against its direction (ituA works by lipopeptide membrane attack, and so
    does fenA, so the walk from ituA to fenA crosses the second edge
    backwards), and a picture of the route needs the walking order."""
    import networkx as nx
    na, nb = find_node(G, a), find_node(G, b)
    view = knowledge_view(G, keep=(na, nb))
    for x, y in view.edges:
        stats_only = all(e["relation"] == "associated_with" for e in _hop_edges(G, x, y))
        view[x][y]["cost"] = STATS_COST if stats_only else 1.0
    try:
        nodes = nx.shortest_path(view, na, nb, weight="cost")
    except nx.NetworkXNoPath:
        return []
    hops = []
    for x, y in zip(nodes, nodes[1:]):
        forward = list((G.get_edge_data(x, y) or {}).values())
        data = forward or list((G.get_edge_data(y, x) or {}).values())
        frm, to = (x, y) if forward else (y, x)
        hops.append({"from": G.nodes[frm]["label"], "relation": data[0]["relation"],
                     "to": G.nodes[to]["label"],
                     "step_from": G.nodes[x]["label"], "step_to": G.nodes[y]["label"],
                     "provenance": "; ".join(dict.fromkeys(e["provenance"] for e in data)),
                     "evidence": "; ".join(e["evidence"] for e in data if isinstance(e.get("evidence"), str))})
    return hops


def show(G, text: str) -> dict:
    """A node's attributes and its neighbours, grouped by relation, with the
    sources behind each group."""
    n = find_node(G, text)
    groups: dict[str, dict] = {}
    for _, m, e in G.out_edges(n, data=True):
        g = groups.setdefault(f"{e['relation']} →", {"labels": [], "sources": []})
        g["labels"].append(G.nodes[m]["label"]); g["sources"].append(e["provenance"])
    for m, _, e in G.in_edges(n, data=True):
        g = groups.setdefault(f"← {e['relation']}", {"labels": [], "sources": []})
        g["labels"].append(G.nodes[m]["label"]); g["sources"].append(e["provenance"])
    for g in groups.values():
        g["labels"] = sorted(dict.fromkeys(g["labels"]))
        g["sources"] = list(dict.fromkeys(g["sources"]))
    return {"node": n, "attributes": dict(G.nodes[n]), "neighbours": groups}


# =============================================================================
# 7. PUBLISH
# =============================================================================

def publish(artifacts_dir: Path = ARTIFACTS, db_path: Path = DB_PATH, verbose: bool = True) -> list[str]:
    """Load every artifacts/graph/*.csv into DuckDB as kg_<name>. Idempotent.
    As in Phases 3 and 4: harmonize.py rebuilds the database from scratch, so
    re-run `publish` after it."""
    import duckdb
    if not Path(db_path).exists():
        sys.exit("No database yet. Run:  python src/strainscope/harmonize.py")
    csvs = sorted(Path(artifacts_dir).glob("*.csv"))
    if not csvs:
        sys.exit("No graph results yet. Run:  python src/strainscope/graph.py build")
    con = duckdb.connect(str(db_path))
    created = []
    try:
        for csv in csvs:
            table = f"kg_{csv.stem}"
            con.execute(f"CREATE OR REPLACE TABLE {table} AS "
                        f"SELECT * FROM read_csv_auto('{csv.as_posix()}', header=true)")
            created.append(table)
    finally:
        con.close()
    if verbose:
        print(f"  published {len(created)} tables into {_rel(db_path)}:")
        for t in created:
            print(f"    {t}")
    return created


def _rel(path: Path) -> str:
    path = Path(path)
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="StrainScope Phase 5: the knowledge graph.")
    parser.add_argument("step", choices=["build", "analyse", "explain", "publish", "all",
                                         "why", "path", "show"],
                        help="which step to run, or a question: why / path / show")
    parser.add_argument("names", nargs="*",
                        help="for why: a strain id; for path: two names; for show: one name")
    args = parser.parse_args()
    if args.step in ("build", "all"):
        build()
    if args.step in ("analyse", "all"):
        analyse()
    if args.step in ("explain", "all"):
        explain()
    if args.step in ("publish", "all"):
        publish()
    if args.step in ("why", "path", "show"):
        _ask(args.step, args.names)


def _ask(step: str, names: list[str]) -> None:
    need = {"why": 1, "path": 2, "show": 1}[step]
    if len(names) != need:
        sys.exit(f"`{step}` needs {need} name(s), e.g.  python src/strainscope/graph.py "
                 + {"why": "why STRAIN_0485", "path": 'path ituA "disease suppression"',
                    "show": "show iturin"}[step])
    G = load_graph()
    try:
        if step == "why":
            attach_expectations(G)
            sid = find_node(G, names[0])
            if G.nodes[sid]["node_type"] != "Strain":
                sys.exit(f"{names[0]!r} is a {G.nodes[sid]['node_type']}, not a strain. Try: show {names[0]}")
            _print_strain(G, sid, pd.DataFrame(explain_strain(G, sid)))
        elif step == "path":
            hops = path(G, *names)
            if not hops:
                print(f"  no path between {names[0]!r} and {names[1]!r} in the knowledge layer")
            for i, h in enumerate(hops, start=1):
                note = "   (statistics only, no known mechanism)" if h["relation"] == "associated_with" else ""
                print(f"  {i}. {h['from']} -{h['relation']}-> {h['to']}{note}")
                print(f"       source: {h['provenance']}" + (f" · {h['evidence']}" if h["evidence"] else ""))
        else:
            info = show(G, names[0])
            a = info["attributes"]
            print(f"  {a['label']} ({a['node_type']})")
            for k, v in a.items():
                if k not in ("label", "node_type"):
                    print(f"    {k}: {v}")
            for rel, g in sorted(info["neighbours"].items()):
                labels = g["labels"]
                shown = ", ".join(labels) if len(labels) <= 40 else \
                    ", ".join(labels[:8]) + f" … ({len(labels)} in total)"
                print(f"    {rel} {shown}")
                print(f"        source: {'; '.join(g['sources'])}")
    except KeyError as err:
        sys.exit(str(err.args[0]))


if __name__ == "__main__":
    main()
