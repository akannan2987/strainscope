"""
ncbi_datasets.py — adapter for NCBI Datasets, the genome catalogue (NIH).
=========================================================================

WHAT NCBI DATASETS IS
---------------------
The US National Center for Biotechnology Information runs the world's central
archive of genome assemblies. The Datasets v2 API serves clean JSON metadata
about every assembled genome: who the organism is, how complete the assembly
is, how long the genome is, its GC content, when it was released.

WHY THIS SOURCE MATTERS TO STRAINSCOPE (the multi-kingdom win)
--------------------------------------------------------------
BacDive gave us real strain records — for BACTERIA only, because that's its
scope. NCBI covers *everything*, so this adapter fetches real genome metadata
for ALL FOUR of our kingdoms: bacterial genera (Bacillus, Pseudomonas…), the
biocontrol fungi (Trichoderma, Beauveria, Metarhizium), and the oomycete
(Pythium). Real genomes now back the entire multi-kingdom story — and their
sizes alone teach real biology (a bacterial genome is ~4–8 million letters; a
fungal one is ~10× that).

THE API-KEY LESSON (this phase's big idea)
------------------------------------------
This API works WITHOUT any key at up to 5 requests/second. A free key raises
that to 10 — useful someday, not required. That makes it the perfect low-stakes
vehicle for learning how secrets are handled properly:

  * the key lives in the ENVIRONMENT (variable `NCBI_API_KEY`), loaded from
    the git-ignored `.env` file by `load_env()` — never in code, never in Git;
  * if present, it's sent as the `api-key` request header and we speed up;
  * if absent, everything still works, just politely slower.

HOW THE API WORKS (one endpoint)
--------------------------------
GET https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{genus}/dataset_report?page_size=N
-> {"reports": [{"accession": "GCF_…", "organism": {"organism_name": …},
                 "assembly_info": {"assembly_level": …, "release_date": …},
                 "assembly_stats": {"total_sequence_length": "…", "gc_percent": …}}, …],
    "total_count": 12345}

(A live-caught detail: NCBI's documentation shows camelCase field names, but the
API itself answers in snake_case — and genome lengths arrive as STRINGS. The
code below accepts either casing, because the live response decides.)
"""


from __future__ import annotations

import json
import os

from .base import Source, load_env

def _pick(d: dict, *keys, default=""):
    """Return the first present key — tolerant of snake_case vs camelCase."""
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return default

BASE = "https://api.ncbi.nlm.nih.gov/datasets/v2"

# One entry per genus we model, tagged with its kingdom — so the tidy table
# carries the same multi-kingdom structure as the synthetic library.
GENERA = {
    "Bacillus": "Bacteria", "Pseudomonas": "Bacteria",
    "Streptomyces": "Bacteria", "Paenibacillus": "Bacteria",
    "Trichoderma": "Fungi", "Beauveria": "Fungi", "Metarhizium": "Fungi",
    "Pythium": "Oomycete",
    # Yeasts — real commercial biocontrol agents (Metschnikowia fructicola,
    # Aureobasidium pullulans) plus the best-sequenced yeast of all. Their
    # absence was caught by tidy()'s own "N kingdoms" summary line printing 3.
    "Saccharomyces": "Yeast", "Metschnikowia": "Yeast", "Aureobasidium": "Yeast",
}

# IDs BEAT NAMES — caught live: NCBI's taxonomy holds TWO genera called
# "Bacillus" (the famous bacteria… and a genus of stick insects). Queried by
# bare name, the API resolved to the insects and reported 3 genomes for one of
# the most-sequenced genera on Earth. For ambiguous names we therefore query by
# the permanent taxonomy ID and keep the readable name only for display.
TAXON_OVERRIDES = {"Bacillus": "1386"}     # taxid 1386 = Bacillus <bacteria>


def _taxon_query(genus: str) -> str:
    """The string that goes in the URL: the taxid when the name is ambiguous."""
    return TAXON_OVERRIDES.get(genus, genus)


class NCBIDatasets(Source):
    name = "ncbi_datasets"
    delay_s = 0.25                 # ≤ 5 req/s without a key; we do ≤ 4

    def _headers(self) -> dict:
        """The api-key header — only if a key exists in the environment.
        load_env() pulls the git-ignored .env file in first; the shell wins
        if both define the variable."""
        load_env()
        key = os.environ.get("NCBI_API_KEY", "").strip()
        return {"api-key": key} if key else {}

    def _report_url(self, genus: str, page_size: int) -> str:
        return (f"{BASE}/genome/taxon/{_taxon_query(genus)}/dataset_report"
                f"?page_size={page_size}")

    # ------------------------------------------------------------------ probe
    def probe(self) -> None:
        has_key = bool(self._headers())
        print(f"\n[{self.name}] probing — real genomes per genus "
              f"(API key: {'found, 10 req/s allowed' if has_key else 'none — fine, 5 req/s'})")
        print(f"  {'genus':<14} {'kingdom':<10} genomes available")
        print("  " + "-" * 44)
        total = 0
        for genus, kingdom in GENERA.items():
            url = self._report_url(genus, 1)          # 1 result, just the count
            data = self.get(url, headers=self._headers())
            count = _pick(data or {}, "total_count", "totalCount", default=0)
            total += count
            print(f"  {genus:<14} {kingdom:<10} {count:>10,}")
            self.log("probe", genus, url, count, "ok")
        print("  " + "-" * 44)
        print(f"  {'TOTAL':<25} {total:>10,}")

    # ------------------------------------------------------------------ fetch
    def fetch(self, limit: int = 25) -> None:
        print(f"\n[{self.name}] fetching up to {limit} genome reports per genus …")
        for genus, kingdom in GENERA.items():
            url = self._report_url(genus, limit)
            data = self.get(url, headers=self._headers())
            reports = (data or {}).get("reports", [])
            self.save_raw(f"genomes_{genus}.json", data or {})
            avail = _pick(data or {}, "total_count", "totalCount", default=0)
            print(f"  [{genus}] saved {len(reports)} genome reports "
                  f"(of {avail:,} available)")
            self.log("fetch", genus, url, len(reports), "ok",
                     f"kingdom={kingdom}; first {limit}")
        print(f"  Raw files in data/raw/real/{self.name}/ — log updated.")

    # ------------------------------------------------------------------- tidy
    def tidy(self) -> None:
        print(f"\n[{self.name}] tidying genome reports into a clean table …")
        rows: list[dict] = []
        for path in sorted(self.raw_dir().glob("genomes_*.json")):
            genus = path.stem.replace("genomes_", "")
            data = json.loads(path.read_text(encoding="utf-8"))
            for rep in data.get("reports", []):
                info = _pick(rep, "assembly_info", "assemblyInfo", default={}) or {}
                stats = _pick(rep, "assembly_stats", "assemblyStats", default={}) or {}
                org = rep.get("organism", {}) or {}
                length = _pick(stats, "total_sequence_length", "totalLength")
                try:                       # lengths arrive as strings — cast
                    length = int(length)
                except (TypeError, ValueError):
                    pass
                rows.append({
                    "accession": rep.get("accession", ""),
                    "organism": _pick(org, "organism_name", "sciName"),
                    "genus_query": genus,
                    "kingdom": GENERA.get(genus, ""),
                    "assembly_level": _pick(info, "assembly_level", "assemblyLevel"),
                    "release_date": _pick(info, "release_date", "releaseDate"),
                    "genome_length_bp": length,
                    "gc_percent": _pick(stats, "gc_percent", "gcPercent"),
                })
        out = self.write_table("real_genomes.csv", rows)
        print(f"  wrote {out.name}  ({len(rows)} real genome records, "
              f"{len(set(r['kingdom'] for r in rows))} kingdoms)")
