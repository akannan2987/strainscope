"""The source registry: every adapter the framework knows about, in one place.

Tier 1 (built): bacdive, pubchem, kegg.
Tier 2 (planned): ncbi_datasets, metabolomics_workbench.
Tier 3 (roadmap): mgnify, ena.
Adding a source = write one adapter file, add one line here. Nothing else moves.
"""
from .bacdive import BacDive
from .kegg import KEGG
from .pubchem import PubChem

SOURCES = {
    "bacdive": BacDive,
    "pubchem": PubChem,
    "kegg": KEGG,
}
