"""
kegg.py — adapter for KEGG, the pathway encyclopedia (Kanehisa Laboratories).
=============================================================================

WHAT KEGG IS
------------
KEGG (Kyoto Encyclopedia of Genes and Genomes) is one of biology's most-cited
references: a hand-curated map of how genes, enzymes, chemical compounds, and
metabolic pathways CONNECT. Where PubChem tells you what a molecule *is*, KEGG
tells you where it *sits* in the web of biology.

⚠ LICENCE, STATED PLAINLY: KEGG's REST API is provided for ACADEMIC USE ONLY,
with a limit of 3 requests/second. This project is personal and educational,
we attribute KEGG wherever its data appears, and we stay far below the limit.
(Non-academic/commercial use requires a licence from Kanehisa Laboratories —
if that ever applies to you, swap this adapter out; the framework makes that a
one-file change.)

WHAT WE TAKE, HONESTLY
----------------------
For each of our real metabolites: its KEGG compound ID and the PATHWAYS it
belongs to. These compound→pathway links are REAL edges — and they become the
seed of the knowledge-graph phase later, so the graph is built on curated
biology rather than invented connections.

HOW THE API WORKS (delightfully simple — plain text, plain URLs)
----------------------------------------------------------------
* find:  https://rest.kegg.jp/find/compound/beauvericin
         -> lines like  "cpd:C11002\tbeauvericin"
* link:  https://rest.kegg.jp/link/pathway/C11002
         -> lines like  "cpd:C11002\tpath:map01110"
* list:  https://rest.kegg.jp/list/pathway
         -> every pathway id + human-readable name (fetched once, reused)
No JSON, no keys — tab-separated text a human can read in a browser.
"""

from __future__ import annotations

import json

from .base import Source

BASE = "https://rest.kegg.jp"

# Metabolites we look up in KEGG (protein/class entries are not compounds).
# Query terms are deliberately COMMA-FREE: KEGG's server rejects commas in the
# URL path with HTTP 400 (caught on the first live run). `find` is a keyword
# search, so "diacetylphloroglucinol" still matches "2,4-diacetylphloroglucinol".
QUERIES = {
    "DAPG":         "diacetylphloroglucinol",
    "pyrrolnitrin": "pyrrolnitrin",
    "phenazine":    "phenazine",
    "HCN":          "hydrogen cyanide",
    "surfactin":    "surfactin",
    "iturin":       "iturin",
    "fengycin":     "fengycin",
    "pyoverdine":   "pyoverdine",
    "six_PP":       "6-pentyl-2H-pyran-2-one",
    "destruxin":    "destruxin",
    "beauvericin":  "beauvericin",
}


def _parse_tsv(text: str) -> list[tuple[str, str]]:
    """KEGG's two-column tab-separated lines -> list of (left, right)."""
    pairs = []
    for line in (text or "").strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            pairs.append((parts[0].strip(), parts[1].strip()))
    return pairs


class KEGG(Source):
    name = "kegg"
    delay_s = 0.4                      # ≤ 3 requests/second required; we do 2.5

    # ------------------------------------------------------------------ probe
    def probe(self) -> None:
        print(f"\n[{self.name}] probe — {len(QUERIES)} compound lookups planned "
              f"(then one pathway-link call per compound found).")
        url = f"{BASE}/info/kegg"
        info = self.get(url, as_json=False)
        first = (info or "").strip().splitlines()[:1]
        print(f"  API reachable: {'yes — ' + first[0] if first else 'NO — see the FAQ'}")
        self.log("probe", "info", url, 1 if info else 0, "ok" if info else "fail")
        print("  Reminder: KEGG is academic-use only; we attribute it and stay "
              "below 3 requests/second.")

    # ------------------------------------------------------------------ fetch
    def fetch(self, limit: int = 25) -> None:      # limit unused; small fixed set
        print(f"\n[{self.name}] fetching compound IDs and pathway links …")
        # One call for ALL pathway names, reused for every compound (politeness).
        list_url = f"{BASE}/list/pathway"
        pathway_names = dict(_parse_tsv(self.get(list_url, as_json=False) or ""))
        self.save_raw("pathway_names.json", pathway_names)
        self.log("fetch", "list/pathway", list_url, len(pathway_names), "ok")

        results: dict = {}
        for our_name, query in QUERIES.items():
            # KEGG's documented convention for spaces in queries is "+".
            find_url = f"{BASE}/find/compound/{query.replace(' ', '+')}"
            hits = _parse_tsv(self.get(find_url, as_json=False) or "")
            if not hits:
                results[our_name] = {"query": query, "kegg_id": None, "pathways": []}
                print(f"  {our_name:<14} -> no KEGG compound (recorded)")
                self.log("fetch", query, find_url, 0, "not_found")
                continue
            kegg_id = hits[0][0].replace("cpd:", "")        # first hit, e.g. C11002
            link_url = f"{BASE}/link/pathway/{kegg_id}"
            links = _parse_tsv(self.get(link_url, as_json=False) or "")
            pathways = [right.replace("path:", "") for _, right in links]
            results[our_name] = {"query": query, "kegg_id": kegg_id,
                                 "matched_name": hits[0][1], "pathways": pathways}
            print(f"  {our_name:<14} -> {kegg_id}  ({len(pathways)} pathway links)")
            self.log("fetch", query, link_url, len(pathways), "ok", kegg_id)
        self.save_raw("compound_pathways.json", results)
        print(f"  Raw files in data/raw/real/{self.name}/ — log updated.")

    # ------------------------------------------------------------------- tidy
    def tidy(self) -> None:
        print(f"\n[{self.name}] tidying into edge + compound tables …")
        rdir = self.raw_dir()
        results_p = rdir / "compound_pathways.json"
        names_p = rdir / "pathway_names.json"
        results = json.loads(results_p.read_text(encoding="utf-8")) if results_p.exists() else {}
        names = json.loads(names_p.read_text(encoding="utf-8")) if names_p.exists() else {}

        compounds, edges = [], []
        for our_name, entry in results.items():
            compounds.append({"metabolite": our_name,
                              "kegg_query": entry.get("query", ""),
                              "kegg_id": entry.get("kegg_id") or "",
                              "matched_name": entry.get("matched_name", ""),
                              "n_pathways": len(entry.get("pathways", [])),
                              "attribution": "KEGG (academic use)"})
            for pid in entry.get("pathways", []):
                edges.append({"metabolite": our_name,
                              "kegg_id": entry.get("kegg_id") or "",
                              "pathway_id": pid,
                              "pathway_name": names.get(pid, names.get(f"path:{pid}", "")),
                              "attribution": "KEGG (academic use)"})
        out1 = self.write_table("real_kegg_compounds.csv", compounds)
        out2 = self.write_table("real_compound_pathways.csv", edges)
        print(f"  wrote {out1.name}  ({len(compounds)} compounds)")
        print(f"  wrote {out2.name}  ({len(edges)} compound→pathway edges — "
              "the knowledge graph's first real edges)")
