"""
metabolomics_wb.py — adapter for Metabolomics Workbench (NIH).
==============================================================

WHAT METABOLOMICS WORKBENCH IS
------------------------------
The US NIH's open home for metabolomics: thousands of real studies with their
measured data, plus **RefMet** — the curated "official names register" for
metabolites. Where PubChem answers "what *is* this molecule?" (structure,
mass), RefMet answers "what *kind* of molecule is it, under its standard
name?" — every entry carries a classification ladder (super-class → main class
→ sub-class), like a library's shelving system for chemistry.

WHAT WE TAKE, HONESTLY
----------------------
1. RefMet entries for our metabolites: the standardised name, formula, exact
   mass, and the three-level classification. That classification becomes real
   structure for the knowledge graph ("beauvericin and destruxin sit on the
   same shelf" is an edge worth having).
2. A taste of the *studies* side: for a few search words tied to our project
   (our genera and habitats), the real studies whose titles mention them —
   proof that actual laboratories measure this exact kind of chemistry.

The honest boundary, as ever: these complement the synthetic library. RefMet
classifies molecules; it does not hand us matched multi-omics with outcomes.

HOW THE API WORKS (plain URL patterns, no key)
----------------------------------------------
Base:  https://www.metabolomicsworkbench.org/rest/{context}/{input}/{value}/{output}
  * refmet:  /rest/refmet/name/beauvericin/all            -> JSON entry
  * studies: /rest/study/study_title/Bacillus/summary     -> JSON of studies
A name RefMet doesn't know returns an empty/blank body — an answer, not an
outage (the same lesson KEGG taught with pathway links).
"""

from __future__ import annotations

import json

from .base import Source

BASE = "https://www.metabolomicsworkbench.org/rest"

# Our metabolites -> the name RefMet is most likely to know them by.
REFMET_QUERIES = {
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

# Search words for the studies side — our genera and the habitat theme.
STUDY_KEYWORDS = ["Bacillus", "Pseudomonas", "Trichoderma", "soil"]


class MetabolomicsWB(Source):
    name = "metabolomics_wb"
    delay_s = 0.5                      # no published limit; be gentle

    # ------------------------------------------------------------------ probe
    def probe(self) -> None:
        print(f"\n[{self.name}] probe — {len(REFMET_QUERIES)} RefMet lookups + "
              f"{len(STUDY_KEYWORDS)} study searches planned.")
        url = f"{BASE}/refmet/name/alanine/all"      # a molecule RefMet surely knows
        data = self.get(url)
        ok = bool(data)
        print(f"  API reachable: {'yes' if ok else 'NO — see the FAQ'}")
        self.log("probe", "alanine", url, 1 if ok else 0, "ok" if ok else "fail")

    # ------------------------------------------------------------------ fetch
    def fetch(self, limit: int = 25) -> None:
        print(f"\n[{self.name}] fetching RefMet entries and study summaries …")
        refmet: dict = {}
        for our_name, query in REFMET_QUERIES.items():
            url = f"{BASE}/refmet/name/{query.replace(' ', '%20')}/all"
            data = self.get(url)
            # RefMet answers a dict for one hit; an empty body/list for none.
            entry = data if isinstance(data, dict) and data else None
            refmet[our_name] = {"query": query, "entry": entry}
            label = (entry.get("name") or entry.get("refmet_name") or "?") if entry else None
            print(f"  {our_name:<14} -> "
                  f"{label if entry else 'no RefMet entry (recorded)'}")
            self.log("fetch", query, url, 1 if entry else 0,
                     "ok" if entry else "not_found")
        self.save_raw("refmet.json", refmet)

        studies: dict = {}
        for kw in STUDY_KEYWORDS:
            url = f"{BASE}/study/study_title/{kw}/summary"
            data = self.get(url)
            # One hit arrives as a flat dict; many hits as {"1": {...}, ...}.
            if isinstance(data, dict) and "study_id" in data:
                hits = [data]
            elif isinstance(data, dict):
                hits = [v for v in data.values() if isinstance(v, dict)]
            else:
                hits = []
            studies[kw] = hits[:limit]
            print(f"  studies titled '{kw}': {len(hits)} found"
                  f"{f' (keeping first {limit})' if len(hits) > limit else ''}")
            self.log("fetch", f"study_title:{kw}", url, len(hits), "ok")
        self.save_raw("studies.json", studies)
        print(f"  Raw files in data/raw/real/{self.name}/ — log updated.")

    # ------------------------------------------------------------------- tidy
    def tidy(self) -> None:
        print(f"\n[{self.name}] tidying into RefMet + studies tables …")
        rdir = self.raw_dir()
        refmet_p, studies_p = rdir / "refmet.json", rdir / "studies.json"
        refmet = json.loads(refmet_p.read_text()) if refmet_p.exists() else {}
        studies = json.loads(studies_p.read_text()) if studies_p.exists() else {}

        rrows: list[dict] = []
        for our_name, item in refmet.items():
            e = item.get("entry") or {}
            rrows.append({
                "metabolite": our_name,
                "refmet_query": item.get("query", ""),
                "status": "found" if e else "no_entry",
                # Live-caught: RefMet's field is "name" (docs elsewhere say
                # refmet_name) — accept either; the live response decides.
                "refmet_name": e.get("name", e.get("refmet_name", "")),
                "refmet_id": e.get("refmet_id", ""),
                "formula": e.get("formula", ""),
                "exact_mass": e.get("exactmass", ""),
                "super_class": e.get("super_class", ""),
                "main_class": e.get("main_class", ""),
                "sub_class": e.get("sub_class", ""),
            })
        out1 = self.write_table("real_refmet.csv", rrows)

        srows: list[dict] = []
        for kw, hits in studies.items():
            for h in hits:
                srows.append({
                    "keyword": kw,
                    "study_id": h.get("study_id", ""),
                    "study_title": h.get("study_title", ""),
                    "species": h.get("latest_version", h.get("species", "")) or h.get("species", ""),
                    "institute": h.get("institute", ""),
                })
        out2 = self.write_table("real_mw_studies.csv", srows)
        found = sum(1 for r in rrows if r["status"] == "found")
        print(f"  wrote {out1.name}  ({found} RefMet entries found, "
              f"{len(rrows) - found} honest no-entries)")
        print(f"  wrote {out2.name}  ({len(srows)} real study records)")
