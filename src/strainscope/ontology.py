"""
src/strainscope/ontology.py (StrainScope Phase 5): the domain model, written down.
=================================================================================

WHAT THIS FILE IS
-----------------
An ONTOLOGY is an agreed list of the kinds of things a project talks about and
the ways they may be connected. Think of it as a family tree for concepts: it
says "a strain belongs to a genus", "a gene can make a compound", "a compound
can sit in a pathway", and, just as important, it rules out connections that
make no sense (a pathway cannot "carry" a strain).

The knowledge graph (src/strainscope/graph.py) is built from this file:
  * every NODE in the graph has one of the NODE_TYPES below;
  * every EDGE has one of the RELATIONS below, and must join the node types
    that relation allows. graph.py refuses to save a graph that breaks a rule,
    and tests/test_graph.py checks it too.

Nothing here is computed. It's plain English turned into Python dictionaries,
so a reader can check every rule without running anything. The guide that
walks through it is docs/06-knowledge-graph.md (sections 1 and 3).

WHERE THE BIOLOGY COMES FROM
----------------------------
The "acts by" links (gene or compound -> mode of action) come from the
descriptions that define the simulated library in
src/strainscope/generate_data.py (for example "pyoverdine siderophore (iron
competition)"). In a project on real strains these links would come from the
literature or from published ontologies (see docs/PRODUCT_ROADMAP.md, item C5).
Each one is stored with its source, so the graph never hides where a claim
came from.
"""
from __future__ import annotations

# =============================================================================
# 1. NODE TYPES: the kinds of things in the graph
# =============================================================================
# For each type: a one-line description, an example, the colour figures use,
# and whether it comes from the synthetic library ("core") or only appears
# when the real tables from Phases 1b and 1c are present ("real").

NODE_TYPES: dict[str, dict] = {
    "Kingdom": {
        "description": "one of the four groups of microbes we model",
        "example": "Bacteria", "colour": "#374151", "origin": "core"},
    "Genus": {
        "description": "a group of closely related species, one level above species",
        "example": "Bacillus", "colour": "#6B7280", "origin": "core"},
    "Strain": {
        "description": "one microbe in the simulated library, with its measurements and prediction",
        "example": "STRAIN_0485", "colour": "#9CA3AF", "origin": "core"},
    "Gene": {
        "description": "a gene a strain may carry (a weapon, a growth helper, a housekeeper or noise)",
        "example": "ituA", "colour": "#4C78A8", "origin": "core"},
    "Compound": {
        "description": "a small molecule a strain may produce, as measured by the lab",
        "example": "iturin", "colour": "#D4A72C", "origin": "core"},
    "ModeOfAction": {
        "description": "how a weapon works against a disease (the mechanism)",
        "example": "iron competition", "colour": "#B279A2", "origin": "core"},
    "Outcome": {
        "description": "something we care about in the field",
        "example": "disease suppression", "colour": "#2E7D5B", "origin": "core"},
    "Pathway": {
        "description": "a curated KEGG pathway map a compound takes part in",
        "example": "map01110", "colour": "#E45756",
        "origin": "real"},
    "ChemicalClass": {
        "description": "a RefMet chemical class (main class or super class)",
        "example": "Fatty acyls", "colour": "#F58518", "origin": "real"},
    "ReferenceStrain": {
        "description": "a real, catalogued strain from BacDive (for context; it has no measurements here)",
        "example": "a BacDive strain record", "colour": "#72B7B2", "origin": "real"},
}

# The types that make up the "knowledge layer": everything except individual
# strains. Analyses of concepts (hubs between ideas, path queries) run on this
# layer so 600 strain nodes don't drown out a few dozen concept nodes.
KNOWLEDGE_TYPES = ("Kingdom", "Genus", "Gene", "Compound", "ModeOfAction",
                   "Outcome", "Pathway", "ChemicalClass")


# =============================================================================
# 2. RELATIONS: the allowed kinds of connection
# =============================================================================
# relation -> (allowed FROM types, allowed TO types, plain-English meaning).
# Edges point in the direction you would read them aloud:
# "STRAIN_0485 carries ituA", "ituA makes iturin", "iturin acts by ...".

RELATIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] = {
    "belongs_to":      (("Strain", "ReferenceStrain"), ("Genus",),
                        "the strain is a member of this genus"),
    "in_kingdom":      (("Genus",), ("Kingdom",),
                        "the genus is part of this kingdom"),
    "carries":         (("Strain",), ("Gene",),
                        "the strain's genome contains this gene"),
    "produces":        (("Strain",), ("Compound",),
                        "the lab measured this compound well above its usual background level"),
    "makes":           (("Gene",), ("Compound",),
                        "the gene holds the recipe for this compound"),
    "acts_by":         (("Gene", "Compound"), ("ModeOfAction",),
                        "the weapon works through this mechanism"),
    "contributes_to":  (("ModeOfAction",), ("Outcome",),
                        "the mechanism helps bring about this outcome"),
    "associated_with": (("Gene", "Compound"), ("Outcome",),
                        "the data says this feature goes with the outcome (statistics, no mechanism implied)"),
    "in_pathway":      (("Compound",), ("Pathway",),
                        "KEGG places the compound in this pathway map"),
    "classified_as":   (("Compound",), ("ChemicalClass",),
                        "RefMet files the compound under this chemical class"),
    "subclass_of":     (("ChemicalClass",), ("ChemicalClass",),
                        "the class sits inside a broader class"),
}


# =============================================================================
# 3. MODES OF ACTION AND OUTCOMES (the domain model's biology)
# =============================================================================

OUTCOMES: dict[str, str] = {
    "disease suppression": "the strain protects plants against a fungal disease (the score the models predict)",
    "plant growth": "the strain helps plants grow (a second trait in the data, not the one we predict)",
}

# mode of action -> (description, the outcome it contributes to)
MODES_OF_ACTION: dict[str, tuple[str, str]] = {
    "antibiosis": (
        "the microbe releases antimicrobial chemicals or volatiles that stop the pathogen",
        "disease suppression"),
    "lipopeptide membrane attack": (
        "lipopeptides punch holes in the pathogen's cell membrane",
        "disease suppression"),
    "iron competition": (
        "siderophores grab the iron the pathogen needs, starving it",
        "disease suppression"),
    "cell-wall degradation": (
        "enzymes digest the chitin and glucan walls of fungal pathogens",
        "disease suppression"),
    "mycoparasitism": (
        "the microbe attacks and feeds on the pathogen itself",
        "disease suppression"),
    "toxin production": (
        "the microbe makes toxins that harm pests and competing microbes",
        "disease suppression"),
    "induced plant resistance": (
        "the microbe primes the plant's own immune defences",
        "disease suppression"),
    "killer-toxin antagonism": (
        "the yeast secretes a protein toxin that kills competing yeasts and fungi",
        "disease suppression"),
    "plant growth promotion": (
        "the microbe feeds or stimulates the plant (nitrogen, phosphate, hormones)",
        "plant growth"),
}

# feature (gene or compound name, as in the data) -> its modes of action.
# Taken from the descriptions in src/strainscope/generate_data.py. Housekeeping
# genes, accessory genes and background compounds have NO entry on purpose:
# nothing is known about them that links them to an outcome.
FEATURE_MODES: dict[str, tuple[str, ...]] = {
    # bacterial antibiotics and the volatile HCN
    "phlD": ("antibiosis",), "DAPG": ("antibiosis",),
    "prnD": ("antibiosis",), "pyrrolnitrin": ("antibiosis",),
    "phzE": ("antibiosis",), "phenazine": ("antibiosis",),
    "hcnA": ("antibiosis",), "HCN": ("antibiosis",),
    # bacterial lipopeptides
    "srfAA": ("lipopeptide membrane attack",), "surfactin": ("lipopeptide membrane attack",),
    "ituA": ("lipopeptide membrane attack",), "iturin": ("lipopeptide membrane attack",),
    "fenA": ("lipopeptide membrane attack",), "fengycin": ("lipopeptide membrane attack",),
    # siderophores
    "pvdA": ("iron competition",), "pyoverdine": ("iron competition",),
    "sidA": ("iron competition",), "yeast_siderophore": ("iron competition",),
    # cell-wall-degrading enzymes and mycoparasitism
    "chiA": ("cell-wall degradation",),
    "glcA": ("cell-wall degradation",),
    "ech42": ("cell-wall degradation", "mycoparasitism"),
    "prb1": ("mycoparasitism",),
    # fungal antifungal volatile and toxins
    "sixPP": ("antibiosis",), "six_PP": ("antibiosis",),
    "dtxS": ("toxin production",), "destruxin": ("toxin production",),
    "beaS": ("toxin production",), "beauvericin": ("toxin production",),
    # oomycete elicitor
    "olpA": ("induced plant resistance",), "oligandrin": ("induced plant resistance",),
    # yeast killer toxin
    "kilT": ("killer-toxin antagonism",), "killer_toxin": ("killer-toxin antagonism",),
    # plant-growth-promotion genes: real biology, but a different outcome
    "acdS": ("plant growth promotion",), "nifH": ("plant growth promotion",),
    "gcd": ("plant growth promotion",), "iaaM": ("plant growth promotion",),
}

# Where the domain-model edges say they came from (stored on every such edge).
DOMAIN_SOURCE = "domain model (gene descriptions in src/strainscope/generate_data.py)"


# =============================================================================
# 4. A SMALL CHECKER (used by graph.py before saving, and by the tests)
# =============================================================================

def check_edge(relation: str, from_type: str, to_type: str) -> str | None:
    """Return None when the edge is allowed, otherwise a sentence saying why not."""
    if relation not in RELATIONS:
        return f"unknown relation '{relation}'"
    allowed_from, allowed_to, _ = RELATIONS[relation]
    if from_type not in allowed_from:
        return f"'{relation}' cannot start at a {from_type} (allowed: {', '.join(allowed_from)})"
    if to_type not in allowed_to:
        return f"'{relation}' cannot end at a {to_type} (allowed: {', '.join(allowed_to)})"
    return None


def ontology_tables():
    """The ontology as two small tables (for the database and the docs)."""
    import pandas as pd
    nodes = pd.DataFrame([{"node_type": t, "description": d["description"],
                           "example": d["example"], "origin": d["origin"]}
                          for t, d in NODE_TYPES.items()])
    rels = pd.DataFrame([{"relation": r, "from_types": " or ".join(f),
                          "to_types": " or ".join(t), "meaning": m}
                         for r, (f, t, m) in RELATIONS.items()])
    return nodes, rels
