"""
pubchem.py — adapter for PubChem, the world's chemistry reference (NCBI/NIH).
=============================================================================

WHAT PUBCHEM IS
---------------
PubChem (https://pubchem.ncbi.nlm.nih.gov) is the US National Institutes of
Health's open database of chemical molecules — over 100 million compounds with
structures, formulas, and masses. Its "PUG REST" API is free, needs no key, and
works with plain URLs.

WHAT WE TAKE, HONESTLY
----------------------
Real chemistry for the metabolites StrainScope models: for each one, its
PubChem ID (CID), molecular formula, molecular weight, and structure (SMILES —
a text notation for a molecule's shape). This *grounds* the synthetic data:
anyone can verify that surfactin, iturin, DAPG, destruxin & co. are real
molecules with real properties, and later the knowledge graph gets real
chemical nodes.

An honest wrinkle we keep on purpose: THREE of our "metabolite" columns are not
small molecules at all — oligandrin and killer toxins are PROTEINS, and
"yeast_siderophore" is a *class* of molecules, not one compound. PubChem
(a small-molecule database) rightly has no single entry for them. The adapter
marks them clearly instead of pretending — because knowing what a database
CANNOT answer is as important as what it can.

HOW THE API WORKS (one step)
----------------------------
GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/
    MolecularFormula,MolecularWeight,CanonicalSMILES,IUPACName/JSON
-> {"PropertyTable": {"Properties": [{"CID": 443592, ...}]}}
A name PubChem doesn't know returns 404 — a result to record, not an error.
Politeness: PubChem asks for at most ~5 requests/second; we stay well under.
"""

from __future__ import annotations

import json

from .base import Source

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPS = "MolecularFormula,MolecularWeight,CanonicalSMILES,IUPACName"

# Our dataset's metabolite names -> the exact name PubChem knows them by.
# (Real biology detail: "iturin"/"destruxin" are families; the "A" member is
#  the canonical representative chemists look up.)
NAME_MAP = {
    "DAPG":         "2,4-diacetylphloroglucinol",
    "pyrrolnitrin": "pyrrolnitrin",
    "phenazine":    "phenazine",
    "HCN":          "hydrogen cyanide",
    "surfactin":    "surfactin",
    "iturin":       "iturin A",
    "fengycin":     "fengycin",
    "pyoverdine":   "pyoverdine",
    "six_PP":       "6-pentyl-alpha-pyrone",
    "destruxin":    "destruxin A",
    "beauvericin":  "beauvericin",
}
# Not small molecules — no PubChem entry exists, and that's the honest answer.
NOT_SMALL_MOLECULES = {
    "oligandrin":        "a protein elicitor, not a small molecule",
    "killer_toxin":      "a protein toxin, not a small molecule",
    "yeast_siderophore": "a class of molecules, not one compound",
}


class PubChem(Source):
    name = "pubchem"
    delay_s = 0.25                     # ≤ 5 requests/second asked; we do ≤ 4

    # ------------------------------------------------------------------ probe
    def probe(self) -> None:
        n = len(NAME_MAP)
        print(f"\n[{self.name}] probe — {n} small-molecule lookups planned "
              f"(+{len(NOT_SMALL_MOLECULES)} entries marked 'not a small molecule').")
        print("  One quick live check (aspirin) to confirm the API is reachable:")
        url = f"{BASE}/compound/name/aspirin/property/MolecularFormula/JSON"
        data = self.get(url)
        ok = bool(data and data.get("PropertyTable"))
        print(f"  API reachable: {'yes' if ok else 'NO — see the FAQ'}")
        self.log("probe", "aspirin", url, 1 if ok else 0, "ok" if ok else "fail")

    # ------------------------------------------------------------------ fetch
    def fetch(self, limit: int = 25) -> None:      # limit unused; small fixed set
        print(f"\n[{self.name}] fetching real chemistry for our metabolites …")
        results: dict = {}
        for our_name, query in NAME_MAP.items():
            url = f"{BASE}/compound/name/{query.replace(' ', '%20')}/property/{PROPS}/JSON"
            data = self.get(url)
            if data and data.get("PropertyTable", {}).get("Properties"):
                results[our_name] = {"query": query,
                                     "properties": data["PropertyTable"]["Properties"][0]}
                cid = results[our_name]["properties"].get("CID", "?")
                print(f"  {our_name:<14} -> CID {cid}")
                self.log("fetch", query, url, 1, "ok")
            else:
                results[our_name] = {"query": query, "properties": None}
                print(f"  {our_name:<14} -> no entry under that name (recorded)")
                self.log("fetch", query, url, 0, "not_found")
        self.save_raw("compounds.json", results)
        print(f"  Raw file in data/raw/real/{self.name}/ — log updated.")

    # ------------------------------------------------------------------- tidy
    def tidy(self) -> None:
        print(f"\n[{self.name}] tidying into a clean compound table …")
        raw_path = self.raw_dir() / "compounds.json"
        results = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else {}
        rows: list[dict] = []
        for our_name, entry in results.items():
            props = entry.get("properties") or {}
            rows.append({
                "metabolite": our_name,
                "pubchem_query": entry.get("query", ""),
                "status": "found" if props else "no_entry",
                "cid": props.get("CID", ""),
                "molecular_formula": props.get("MolecularFormula", ""),
                "molecular_weight": props.get("MolecularWeight", ""),
                "smiles": props.get("CanonicalSMILES", props.get("SMILES", "")),
                "iupac_name": props.get("IUPACName", ""),
                "note": "",
            })
        for our_name, why in NOT_SMALL_MOLECULES.items():
            rows.append({"metabolite": our_name, "pubchem_query": "",
                         "status": "not_a_small_molecule", "cid": "",
                         "molecular_formula": "", "molecular_weight": "",
                         "smiles": "", "iupac_name": "", "note": why})
        out = self.write_table("real_compounds.csv", rows)
        found = sum(1 for r in rows if r["status"] == "found")
        print(f"  wrote {out.name}  ({found} found, "
              f"{len(NOT_SMALL_MOLECULES)} honestly marked not-a-small-molecule)")
