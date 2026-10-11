"""
tests/test_graph.py: offline tests for the Phase 5 knowledge graph.
===================================================================
What they protect, in plain words:
  * the ontology is consistent: every relation joins known node types, every
    weapon in the simulated library has a mode of action, and nothing without
    a known mechanism is wired to disease suppression;
  * the graph is built only from allowed edges, and every edge says where it
    came from, with or without the real tables of Phases 1b and 1c;
  * "produces" means clearly above background, and a missing gene call is
    never reported as "lacks";
  * explanations walk real edges: weapons with a mechanism, data-only flags,
    and missing weapons;
  * path questions prefer a route that explains HOW over a statistics-only
    shortcut, and a wrong name gets a helpful message;
  * communities are reproducible, publish can run twice, and the figure
    script only reads files graph.py writes.

None of them needs the network or the real database. Each builds a small
hand-made database (40 strains) in a temporary folder.

Run:  pytest -q tests/test_graph.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strainscope import graph as kg  # noqa: E402
from strainscope import ontology as onto  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GENES = ["ituA", "fenA", "kilT", "acdS", "accA", "ssu_rRNA"]
COMPOUNDS = ["iturin", "fengycin", "killer_toxin", "bg_metabolite_1"]


def _small_project(tmp: Path, with_real: bool = False) -> dict:
    """40 hand-made strains (20 bacterial, 20 yeast) plus the Phase 3 and 4
    result files graph.py reads. Returns the paths to pass to build()."""
    import duckdb
    rng = np.random.default_rng(3)
    n = 40
    ids = [f"S{i:03d}" for i in range(n)]
    kingdom = np.array(["Bacteria"] * 20 + ["Yeast"] * 20)
    bact = kingdom == "Bacteria"
    gen = pd.DataFrame({"strain_id": ids,
                        "ituA": np.where(bact, rng.random(n) < 0.6, 0).astype(float),
                        "fenA": np.where(bact, rng.random(n) < 0.6, 0).astype(float),
                        "kilT": np.where(~bact, rng.random(n) < 0.6, 0).astype(float),
                        "acdS": (rng.random(n) < 0.4).astype(float),
                        "accA": (rng.random(n) < 0.5).astype(float),
                        "ssu_rRNA": 1.0})
    gen.loc[0, "ituA"] = 1.0                       # S000 carries ituA ...
    gen.loc[1, ["ituA", "fenA"]] = [0.0, 0.0]      # S001 lacks both lipopeptide genes
    gen.loc[2, "fenA"] = np.nan                    # S002's fenA call is missing
    gen.loc[2, "ituA"] = 0.0
    gen.loc[0, "accA"] = 1.0                       # ... and the decoy accA
    met = pd.DataFrame({"strain_id": ids})
    for c, g in (("iturin", "ituA"), ("fengycin", "fenA"), ("killer_toxin", "kilT")):
        high, low = rng.lognormal(3, 0.3, n), rng.lognormal(0.5, 0.3, n)
        met[c] = np.where(gen[g].fillna(0) == 1, high, low)
    met["bg_metabolite_1"] = rng.lognormal(2, 0.3, n)
    score = 40 + 15 * gen[["ituA", "fenA", "kilT"]].fillna(0).sum(axis=1) + rng.normal(0, 3, n)
    phe = pd.DataFrame({"strain_id": ids, "kingdom": kingdom,
                        "genus": np.where(bact, "Bacillus", "Metschnikowia"),
                        "suppression_score": score.round(2), "is_effective": (score >= 65).astype(int)})
    db = tmp / "small.duckdb"
    con = duckdb.connect(str(db))
    tables = {"genomics": gen, "metabolomics": met, "phenotype": phe}
    if with_real:
        tables.update(_real_tables())
    for name, df in tables.items():
        con.register("t", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM t")
        con.unregister("t")
    con.close()

    integ, model = tmp / "integration", tmp / "model"
    integ.mkdir(); model.mkdir()
    pd.DataFrame({"gene": ["ituA", "fenA", "kilT", "ituA"],
                  "metabolite": ["iturin", "fengycin", "killer_toxin", "fengycin"],
                  "spearman_rho": [0.8, 0.7, 0.75, 0.05],
                  "is_producer_pair": [True, True, True, False]}).to_csv(
        integ / "cross_block_correlation.csv", index=False)
    pd.DataFrame({"block": ["genomics", "metabolomics"], "component": [1, 1],
                  "feature": ["fenA", "iturin"], "loading": [0.4, 0.3],
                  "stability": [1.0, 0.9]}).to_csv(integ / "diablo_signature.csv", index=False)
    feats = ["ituA", "fenA", "kilT", "iturin", "accA", "acdS"]
    pd.DataFrame({"model_key": "elastic_net", "feature": feats,
                  "importance_mean": [0.03, 0.02, 0.025, 0.01, 0.006, 0.0005],
                  "reliably_important": [True, True, True, True, True, False]}).to_csv(
        model / "feature_importance.csv", index=False)
    prob = (score - score.min()) / (score.max() - score.min())
    order = np.argsort(-prob.to_numpy())
    pd.DataFrame({"rank": np.arange(1, n + 1), "strain_id": np.array(ids)[order],
                  "probability": prob.to_numpy()[order].round(4)}).to_csv(model / "predictions.csv", index=False)
    (model / "model_card.json").write_text(json.dumps(
        {"model": "Elastic net logistic regression", "model_key": "elastic_net"}), encoding="utf-8")
    return {"db_path": db, "integration_dir": integ, "model_dir": model, "artifacts_dir": tmp / "graph"}


def _real_tables() -> dict:
    """Small stand-ins for the Phase 1b/1c tables, same columns as the real
    adapters write (the values are made up for the test)."""
    return {
        "real_compounds": pd.DataFrame({"metabolite": ["iturin", "killer_toxin"],
                                        "status": ["found", "not_a_small_molecule"],
                                        "cid": ["102287549", ""], "molecular_formula": ["C48H74N12O14", ""],
                                        "molecular_weight": ["1043.2", ""], "note": ["", "a protein"]}),
        "real_compound_pathways": pd.DataFrame({"metabolite": ["iturin", "fengycin"],
                                                "kegg_id": ["C99991", "C99992"],
                                                "pathway_id": ["map01054", "map01054"],
                                                "pathway_name": ["Nonribosomal peptide structures"] * 2}),
        "real_refmet": pd.DataFrame({"metabolite": ["iturin"], "status": ["found"],
                                     "refmet_name": ["Iturin A"], "main_class": ["Cyclic peptides"],
                                     "super_class": ["Organic acids"], "sub_class": [""]}),
        "real_strains": pd.DataFrame({"bacdive_id": [1, 2], "genus": ["Bacillus", "Bacillus"],
                                      "full_name": ["Bacillus subtilis test 1", ""],
                                      "isolation_source": ["soil", ""], "country": ["DE", ""]}),
        "real_genomes": pd.DataFrame({"genus_query": ["Bacillus", "Bacillus"],
                                      "genome_length_bp": [4_200_000, 4_000_000]}),
    }


@pytest.fixture()
def small(tmp_path):
    paths = _small_project(tmp_path)
    kg.build(**paths, verbose=False)
    G = kg.load_graph(paths["artifacts_dir"])
    kg.attach_expectations(G, paths["db_path"])
    return paths, G


def test_ontology_is_consistent():
    from strainscope.generate_data import (HOUSEKEEPING_GENES, NOISE_GENES, NOISE_METABOLITES,
                                           SIGNAL_GENES, SIGNAL_METABOLITES)
    for rel, (frm, to, _) in onto.RELATIONS.items():
        assert set(frm) <= set(onto.NODE_TYPES) and set(to) <= set(onto.NODE_TYPES), rel
    assert set(onto.KNOWLEDGE_TYPES) <= set(onto.NODE_TYPES)
    for feature, modes in onto.FEATURE_MODES.items():
        assert set(modes) <= set(onto.MODES_OF_ACTION), feature
    assert {o for _, o in onto.MODES_OF_ACTION.values()} <= set(onto.OUTCOMES)
    for weapon in list(SIGNAL_GENES) + list(SIGNAL_METABOLITES):     # every weapon has a mechanism
        assert weapon in onto.FEATURE_MODES, weapon
    for nothing in list(HOUSEKEEPING_GENES) + list(NOISE_GENES) + NOISE_METABOLITES:
        assert nothing not in onto.FEATURE_MODES, nothing             # and nothing else does


def test_check_edge_allows_sense_and_refuses_nonsense():
    assert onto.check_edge("carries", "Strain", "Gene") is None
    assert "cannot start" in onto.check_edge("carries", "Pathway", "Gene")
    assert "cannot end" in onto.check_edge("makes", "Gene", "Strain")
    assert "unknown relation" in onto.check_edge("likes", "Strain", "Gene")


def test_produces_means_clearly_above_background():
    level = pd.Series([1.0, 1.0, 1.0, 0.9, 1.1, 4.0, 3.9, np.nan])
    hit, median = kg._detected(level)
    assert median == pytest.approx(1.0)                        # the missing reading is ignored
    assert hit.tolist() == [False] * 5 + [True, False, False]  # 4x the median counts, 3.9x doesn't


def test_build_without_real_tables(small):
    paths, G = small
    out = paths["artifacts_dir"]
    nodes, edges = pd.read_csv(out / "nodes.csv"), pd.read_csv(out / "edges.csv")
    assert kg.validate(nodes, edges) == []
    assert edges["provenance"].notna().all() and (edges["provenance"] != "").all()
    carries = edges[edges["relation"] == "carries"]
    assert len(carries[carries["to_id"] == "gene:ssu_rRNA"]) == 40
    assert not set(nodes["node_type"]) & {"Pathway", "ChemicalClass", "ReferenceStrain"}
    assert ("gene:ituA", "compound:iturin") in set(zip(edges["from_id"], edges["to_id"]))
    makes = edges[(edges["relation"] == "makes") & (edges["from_id"] == "gene:ituA")]
    assert makes["weight"].iloc[0] == pytest.approx(0.8)            # Phase 3's rho rides along
    assert (out / "knowledge_layer.graphml").exists()


def test_build_with_real_tables_adds_sourced_context(tmp_path):
    paths = _small_project(tmp_path, with_real=True)
    kg.build(**paths, verbose=False)
    nodes = pd.read_csv(paths["artifacts_dir"] / "nodes.csv")
    edges = pd.read_csv(paths["artifacts_dir"] / "edges.csv")
    assert kg.validate(nodes, edges) == []
    by_rel = edges.groupby("relation")["provenance"].agg(set)
    assert by_rel["in_pathway"] == {kg.P_KEGG}
    assert by_rel["classified_as"] == {kg.P_REFMET} and "subclass_of" in by_rel
    assert len(nodes[nodes["node_type"] == "ReferenceStrain"]) == 2
    genus = nodes.set_index("node_id").loc["genus:Bacillus"]
    assert genus["n_real_genomes"] == 2 and genus["median_genome_mb"] == pytest.approx(4.1)
    assert nodes.set_index("node_id").loc["compound:killer_toxin", "chemistry_note"] == "a protein"


def test_validate_catches_a_nonsense_edge(small):
    paths, _ = small
    nodes = pd.read_csv(paths["artifacts_dir"] / "nodes.csv")
    edges = pd.read_csv(paths["artifacts_dir"] / "edges.csv")
    bad = pd.concat([edges, pd.DataFrame([{"from_id": "outcome:disease suppression",
                                           "relation": "carries", "to_id": "gene:ituA",
                                           "provenance": "test"}])], ignore_index=True)
    assert any("cannot start" in p for p in kg.validate(nodes, bad))


def test_explanations_walk_mechanisms_flag_decoys_and_spot_gaps(small):
    _, G = small
    first = pd.DataFrame(kg.explain_strain(G, "S000"))
    mech = first[first["kind"] == "mechanism"]
    assert mech["text"].str.contains("carries ituA and produces iturin").any()
    assert "lipopeptide membrane attack" in mech["mode"].tolist()
    flag = first[first["kind"] == "data only"]
    assert flag["feature"].tolist() == ["accA"]                      # the decoy is flagged, not credited
    gap = pd.DataFrame(kg.explain_strain(G, "S001"))
    assert set(gap.loc[gap["kind"] == "missing", "feature"]) == {"ituA", "fenA"}
    unknown = pd.DataFrame(kg.explain_strain(G, "S002"))
    assert "fenA" not in set(unknown.loc[unknown["kind"] == "missing", "feature"])   # unknown is not "lacks"
    with pytest.raises(KeyError):
        kg.explain_strain(G, "S999")


def test_path_prefers_how_over_statistics(small):
    _, G = small
    how = kg.path(G, "ituA", "disease suppression")
    assert [h["relation"] for h in how] == ["acts_by", "contributes_to"]
    assert all(h["provenance"] for h in how)
    stats = kg.path(G, "accA", "disease suppression")
    assert [h["relation"] for h in stats] == ["associated_with"]


def test_find_node_is_forgiving_and_helpful(small):
    _, G = small
    assert kg.find_node(G, "ITURIN") == "compound:iturin"
    assert kg.find_node(G, "s000") == "strain:S000"
    with pytest.raises(KeyError, match="Did you mean"):
        kg.find_node(G, "itu")                                       # ituA and iturin both match


def test_communities_are_reproducible_and_graded(small):
    paths, _ = small
    a = kg.analyse(paths["artifacts_dir"], verbose=False)["communities"]
    b = kg.analyse(paths["artifacts_dir"], verbose=False)["communities"]
    pd.testing.assert_frame_equal(a, b)
    toy = pd.DataFrame({"role": ["signal"] * 4, "community": [1, 1, 2, 2],
                        "arsenal": ["Bacteria", "Bacteria", "Yeast", "Bacteria"]})
    grade = kg.grade_communities(toy)
    assert grade["purity"] == pytest.approx(0.75) and grade["signal_features"] == 4


def test_publish_is_idempotent(small):
    import duckdb
    paths, _ = small
    kg.analyse(paths["artifacts_dir"], verbose=False)
    kg.explain(paths["artifacts_dir"], paths["db_path"], verbose=False)
    first = kg.publish(paths["artifacts_dir"], paths["db_path"], verbose=False)
    again = kg.publish(paths["artifacts_dir"], paths["db_path"], verbose=False)
    assert first == again and {"kg_nodes", "kg_edges", "kg_explanations"} <= set(first)
    con = duckdb.connect(str(paths["db_path"]), read_only=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM kg_edges").fetchone()[0]
    finally:
        con.close()
    assert n == len(pd.read_csv(paths["artifacts_dir"] / "edges.csv"))


def test_figure_script_reads_only_files_that_graph_py_writes():
    """The contract between the two scripts: every artifacts/graph file the
    figure script reads must be one that graph.py writes."""
    import re
    fig_code = (ROOT / "figures" / "make_phase5_figures.py").read_text(encoding="utf-8")
    graph_code = (ROOT / "src" / "strainscope" / "graph.py").read_text(encoding="utf-8")
    read = set(re.findall(r'_read\("([a-z_]+\.(?:csv|graphml))"\)', fig_code))
    assert read, "the figure script should read result files"
    missing = sorted(name for name in read if name not in graph_code)
    assert not missing, f"figure script reads files graph.py never writes: {missing}"
