"""
bacdive.py — adapter for BacDive, the Bacterial Diversity Metadatabase.
=======================================================================

WHAT BACDIVE IS
---------------
BacDive (https://bacdive.dsmz.de) is run by the DSMZ, Germany's national
collection of microorganisms, and is the world's largest database of
standardised, strain-level bacterial information: ~82,000 real strains with
taxonomy, where each was isolated, growth conditions, and more. Since February
2026 its API is freely accessible — no account, no key.

WHAT WE TAKE, HONESTLY
----------------------
Real strain records for the bacterial genera StrainScope models (Bacillus,
Pseudomonas, Streptomyces, Paenibacillus). That gives the project a table of
REAL strains — names, isolation sources, countries — to browse next to the
synthetic library. Note the honest boundary: BacDive covers bacteria (and
archaea) only, and it does NOT contain a standardised "disease suppression"
outcome — no public database does. So these records complement the synthetic
data; they don't replace it.

HOW THE API WORKS (two steps)
-----------------------------
1. LIST:  GET https://api.bacdive.dsmz.de/taxon/{genus}
          -> a paginated list: {"count": N, "next": <url or null>,
             "results": [{"id": 1234, ...}, ...]}
2. FETCH: GET https://api.bacdive.dsmz.de/fetch/{id};{id};{id}
          -> full records, keyed by id.
Responses are JSON. If the API's shape ever changes, the raw responses are all
saved to disk, so nothing is lost — only tidy() would need a tweak.
"""

from __future__ import annotations

import json

from .base import Source

BASE = "https://api.bacdive.dsmz.de"
GENERA = ["Bacillus", "Pseudomonas", "Streptomyces", "Paenibacillus"]


def _dig(record: dict, *path, default=""):
    """Walk a nested dict safely: _dig(r, 'a', 'b') == r['a']['b'] or default.
    BacDive records are deeply nested; this keeps tidy() readable and robust.
    Lists along the way -> take the first element (records sometimes wrap
    single values in lists)."""
    cur = record
    for key in path:
        if isinstance(cur, list):
            cur = cur[0] if cur else {}
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    if isinstance(cur, list):
        cur = cur[0] if cur else default
    return cur if cur is not None else default


def _extract_ids(results, limit: int) -> list[str]:
    """Pull strain IDs out of a /taxon results list, whatever its shape.

    The live API returns a plain list of integer IDs ([171624, 171625, ...]);
    earlier documentation showed dict entries ([{"id": 171624}, ...]). Live
    services evolve, so we accept BOTH — the first real fetch is exactly where
    such differences surface, and tolerant parsing is the cure."""
    ids: list[str] = []
    for r in results[:limit]:
        rid = r.get("id") if isinstance(r, dict) else r
        if rid is not None:
            ids.append(str(rid))
    return ids


class BacDive(Source):
    name = "bacdive"
    delay_s = 0.5                      # gentle; no published limit, so be kind

    # ------------------------------------------------------------------ probe
    def probe(self) -> None:
        print(f"\n[{self.name}] probing — how many real strains per genus?")
        print(f"  {'genus':<14} strains available")
        print("  " + "-" * 32)
        total = 0
        for genus in GENERA:
            url = f"{BASE}/taxon/{genus}"
            data = self.get(url)
            count = (data or {}).get("count", 0)
            total += count
            print(f"  {genus:<14} {count:>10,}")
            self.log("probe", genus, url, count, "ok")
        print("  " + "-" * 32)
        print(f"  {'TOTAL':<14} {total:>10,}")
        print("  (a fetch downloads only the first --limit per genus; "
              "the log records exactly what was taken)")

    # ------------------------------------------------------------------ fetch
    def fetch(self, limit: int = 25) -> None:
        print(f"\n[{self.name}] fetching up to {limit} strains per genus …")
        for genus in GENERA:
            list_url = f"{BASE}/taxon/{genus}"
            listing = self.get(list_url)
            if not listing or not listing.get("results"):
                print(f"  [{genus}] nothing returned — logged and skipped")
                self.log("fetch", genus, list_url, 0, "empty")
                continue
            ids = _extract_ids(listing["results"], limit)
            self.save_raw(f"list_{genus}.json", listing)

            # Fetch details in small batches (the API accepts id;id;id).
            batch_size = 10
            records: dict = {}
            for i in range(0, len(ids), batch_size):
                chunk = ids[i:i + batch_size]
                fetch_url = f"{BASE}/fetch/{';'.join(chunk)}"
                data = self.get(fetch_url)
                got = (data or {}).get("results", {})
                if isinstance(got, dict):
                    records.update(got)
                elif isinstance(got, list):          # tolerate either shape
                    for rec in got:
                        rid = str(_dig(rec, "General", "BacDive-ID",
                                       default=len(records)))
                        records[rid] = rec
            self.save_raw(f"records_{genus}.json", records)
            print(f"  [{genus}] saved {len(records)} strain records "
                  f"(of {listing.get('count', '?'):,} available)")
            self.log("fetch", genus, list_url, len(records), "ok",
                     f"first {limit} of {listing.get('count', '?')}")
        print(f"  Raw files in data/raw/real/{self.name}/ — log updated.")

    # ------------------------------------------------------------------- tidy
    def tidy(self) -> None:
        print(f"\n[{self.name}] tidying raw records into a clean table …")
        rows: list[dict] = []
        for path in sorted(self.raw_dir().glob("records_*.json")):
            records = json.loads(path.read_text(encoding="utf-8"))
            for bacdive_id, rec in records.items():
                rows.append({
                    "bacdive_id": bacdive_id,
                    "genus": _dig(rec, "Name and taxonomic classification", "genus"),
                    "species": _dig(rec, "Name and taxonomic classification", "species"),
                    "full_name": _dig(rec, "Name and taxonomic classification",
                                      "full scientific name"),
                    "isolation_source": _dig(rec, "Isolation, sampling and environmental information",
                                             "isolation", "sample type"),
                    "country": _dig(rec, "Isolation, sampling and environmental information",
                                    "isolation", "country"),
                    "is_type_strain": _dig(rec, "Name and taxonomic classification",
                                           "type strain"),
                })
        out = self.write_table("real_strains.csv", rows)
        print(f"  wrote {out.relative_to(out.parents[3])}  ({len(rows)} strains)")
        if rows and not any(r["genus"] for r in rows):
            print("  ⚠ genus came back empty for every record — the API's field"
                  " names may have shifted; the raw JSON is saved, so open one"
                  " record and adjust the paths in tidy().")
