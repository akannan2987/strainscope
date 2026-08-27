# The Query Cookbook — ready-to-run SQL for the StrainScope database

[← README](../README.md) · [All docs in order](../README.md#the-tutorial-in-order) · [Glossary](GLOSSARY.md)

Every query below is **tested** and runs against `data/processed/strainscope.duckdb`
(built in [Phase 2](03-harmonization-qc.md)). Run them with the project's own
**SQL console** — read-only, so you can explore fearlessly:

```bash
# one query, straight from the shell:
python src/strainscope/sql.py "SELECT COUNT(*) FROM phenotype"

# or an interactive session — paste recipes one after another:
python src/strainscope/sql.py
sql> .tables                  -- list every table  (recipes below are multi-line:
sql> .schema phenotype        --  paste them whole; ';' ends a statement)
sql> exit
```

*(Prefer a standalone tool? The official DuckDB CLI — `brew install duckdb`,
then `duckdb -readonly data/processed/strainscope.duckdb` — speaks the same
SQL. The console above needs no installation and behaves identically.)*

This file grows every phase. SQL reads almost like English — each recipe below
tells you the sentence it's saying.

---

## 1. First contact

**"Show me three rows of the phenotype table."**
```sql
SELECT * FROM phenotype LIMIT 3;
```
`SELECT *` = every column · `FROM phenotype` = of this table · `LIMIT 3` = just three rows.

**"How many strains do we have?"**
```sql
SELECT COUNT(*) AS n_strains FROM phenotype;
```
→ `600` (the clean count — duplicates are gone). `AS n_strains` just names the output column.

## 2. Filtering and sorting

**"The strongest suppressors, best first."**
```sql
SELECT strain_id, kingdom, suppression_score
FROM phenotype
WHERE suppression_score >= 80
ORDER BY suppression_score DESC
LIMIT 5;
```
`WHERE` keeps only matching rows · `ORDER BY … DESC` sorts high-to-low.
(You'll notice scores capped at exactly 100.00 — those are the clipped
"impossible" readings from cleaning, now honest boundary values.)

## 3. Grouping — one row per category

**"How many strains per kingdom, and what share are effective?"**
```sql
SELECT kingdom,
       COUNT(*)                              AS n,
       ROUND(100.0 * AVG(is_effective), 1)   AS pct_effective
FROM phenotype
GROUP BY kingdom
ORDER BY n DESC;
```
→ Bacteria 267 (28.1 %), Fungi 183 (21.3 %), Yeast 95 (18.9 %), Oomycete 55 (23.6 %).
`GROUP BY` folds the table into one row per kingdom; `AVG(is_effective)` on a
0/1 column *is* the effective rate — a classic trick.

## 4. JOIN — the payoff of a shared key

**"For the top effective strains: do they carry the iturin gene, and how much iturin do they make?"**
```sql
SELECT p.strain_id, p.kingdom, p.suppression_score, g.ituA, m.iturin
FROM phenotype     p
JOIN genomics      g USING (strain_id)
JOIN metabolomics  m USING (strain_id)
WHERE p.is_effective = 1
ORDER BY p.suppression_score DESC
LIMIT 5;
```
`JOIN … USING (strain_id)` lines tables up on the shared key — the whole reason
every table carries `strain_id`. Run it and look: the top strains all show
`ituA = 1` with high iturin. **The biology is visible in five lines of SQL.**

## 5. NULL — the honest gaps

**"How many iturin readings are missing?"**
```sql
SELECT COUNT(*) AS missing_iturin
FROM metabolomics
WHERE iturin IS NULL;
```
`NULL` is SQL's "no value here." Note the special grammar: `IS NULL`, never
`= NULL` (a classic beginner trap — `= NULL` silently matches nothing).
Cleaning kept these gaps deliberately; the modelling phases decide what to do
about them, openly.

## 6. The real tables — same database, same SQL

**"Which real BacDive strains did we fetch, per genus?"**
```sql
SELECT genus, COUNT(*) AS n
FROM real_strains
GROUP BY genus
ORDER BY n DESC;
```
→ with the default Phase 1b fetch: 25 each of Bacillus, Pseudomonas,
Streptomyces, Paenibacillus (100 total).

**"The verified chemistry for our metabolites."**
```sql
SELECT metabolite, molecular_formula, molecular_weight, cid
FROM real_compounds
WHERE status = 'found'
ORDER BY molecular_weight DESC;
```

**"The knowledge graph's first real edges."**
```sql
SELECT metabolite, pathway_name
FROM real_compound_pathways;
```
→ e.g. pyrrolnitrin ↔ *Biosynthesis of secondary metabolites* (KEGG, attributed).

## 7. Synthetic meets real — one query across both worlds

**"For each metabolite our strains produce: its real formula, and how many of our clean strains produce it strongly."**
```sql
SELECT rc.metabolite,
       rc.molecular_formula,
       COUNT(*) FILTER (WHERE m.iturin > 10)     AS strong_producers_iturin
FROM real_compounds rc, metabolomics m
WHERE rc.metabolite = 'iturin' AND rc.status = 'found'
GROUP BY rc.metabolite, rc.molecular_formula;
```
A taste of what's coming: synthetic measurements and real reference data,
answering one question together. (The integration and knowledge-graph phases
make this systematic.)

---

*Recipes are added as the project grows — the app's SQL console (Phase 6) will
ship with this cookbook built in.*
