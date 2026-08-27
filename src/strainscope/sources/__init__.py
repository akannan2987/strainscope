"""The source registry: every adapter the framework knows about, in one place.

Tier 1 (built): bacdive, pubchem, kegg.
Tier 2 (built): ncbi_datasets, metabolomics_wb.
Tier 3 (roadmap): mgnify, ena — documented for the app/deployment phases.
Adding a source = write one adapter file, add one line here. Nothing else moves.
"""
from .bacdive import BacDive
from .kegg import KEGG
from .metabolomics_wb import MetabolomicsWB
from .ncbi_datasets import NCBIDatasets
from .pubchem import PubChem

SOURCES = {
    "bacdive": BacDive,
    "pubchem": PubChem,
    "kegg": KEGG,
    "ncbi_datasets": NCBIDatasets,
    "metabolomics_wb": MetabolomicsWB,
}
