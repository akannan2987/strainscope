# The Query Cookbook — ready-to-run SQL for the StrainScope database

[← README](../README.md) · [Handbook](HANDBOOK.md) · [All docs in order](../README.md#the-tutorial-in-order) · [Glossary](GLOSSARY.md)

Every query below is **tested** and runs against `data/processed/strainscope.duckdb`
(built in [Phase 2](03-harmonization-qc.md)). Run them with the project's own
**SQL console** — read-only, so you can explore fearlessly:

```bash
# one query, straight from the shell:
python src/strainscope/sql.py "SELECT COUNT(*) FROM phenotype"

# or an interactive session - paste recipes one after another:
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
answering one question together. (Section 8 does this systematically with the
integration results; the knowledge-graph phase goes further.)

## 8. Integration results (Phase 3)

These tables exist once you have run `python src/strainscope/integrate.py publish`
(or `integrate.py all`) — see [`docs/04-integration.md` §9](04-integration.md#9-step-5--publish-to-the-database-and-ask-it-questions).
Every Phase 3 table starts with `int_`; `.tables` lists them. *(The data is
simulated: these numbers prove the workflow, not real-world accuracy.)*

> **If a table is missing:** `src/strainscope/harmonize.py` rebuilds the database from scratch,
> which removes the `int_*` tables on purpose. Re-run `integrate.py publish`.

**"How did every Python approach score, best first?"**
```sql
SELECT approach,
       ROUND(ber_mean, 3) AS ber, ROUND(ber_sd, 3) AS sd,
       ROUND(auc_mean, 3) AS auc
FROM int_python_scoreboard
ORDER BY ber_mean;
```
→ late integration on top (BER 0.123), then early integration (0.134) and
PLS-DA (0.137), genomics alone (0.148), and the two controls at the bottom near
0.5 — exactly where a coin sits. *Lower BER is better; higher AUC is better.*

**"DIABLO's headline numbers."** (DIABLO keeps its results as key/value pairs.)
```sql
SELECT key, value
FROM int_diablo_summary
WHERE key IN ('mixomics_version', 'ncomp_fitted', 'keepX_genomics',
              'keepX_metabolomics', 'cv_ber_final', 'cv_ber_final_sd',
              'cv_ber_all_features', 'block_agreement_comp1');
```
→ 2 components, keepX `16;16` and `16;4`, cross-validated BER ≈ 0.155 ± 0.011,
0.145 with every feature, blocks agreeing at r ≈ 0.77. (Expect ±0.01 with other
mixOmics versions.)

**"How much did centring within kingdom help?"** — one row per component, the
two versions side by side. `FILTER (WHERE …)` picks which rows each column
summarises; `MAX` just collects the single value.
```sql
SELECT component,
       ROUND(MAX(ber) FILTER (WHERE version = 'as_measured'), 3) AS as_measured,
       ROUND(MAX(ber) FILTER (WHERE version = 'centred'), 3)     AS centred
FROM int_diablo_error_by_component
GROUP BY component
ORDER BY component;
```
→ the error falls from about 0.22 to about 0.145 from component 2 on. (R prints
the component-1 centred value as 0.154 and DuckDB as 0.155 — the true value is
0.1545, and the two round halves differently.)

**"Grade every signature against the planted truth."**
```sql
SELECT method, n_selected,
       n_signal_selected AS true_drivers,
       ROUND(precision, 2) AS precision, ROUND(recall, 2) AS recall,
       decoys_selected
FROM int_signature_report_card;
```
→ DIABLO's robust list: 29 picks, 29 true drivers, no decoys. The lasso: 17
picks, 17 true drivers — perfect precision, lower recall (it keeps fewer).

**"Which features do R and Python both trust?"** — DIABLO's robust picks that the
lasso also picked in at least 80 % of folds.
```sql
SELECT d.feature, d.block,
       ROUND(d.stability, 2)           AS diablo_stability,
       ROUND(p.selection_frequency, 2) AS lasso_frequency
FROM int_diablo_signature d
JOIN int_python_selection p USING (feature)
WHERE d.component = 1 AND d.stability >= 0.8
  AND p.selection_frequency >= 0.8
ORDER BY d.block, d.feature;
```
→ 17 features — the "in both" number of `int_language_agreement`. Two
languages, two methods, one core answer.

**"Do genes and their own products rise together?"**
```sql
SELECT gene, metabolite, ROUND(spearman_rho, 2) AS rho
FROM int_cross_block_correlation
WHERE is_producer_pair
ORDER BY rho DESC;
```
→ 14 producer pairs, from `prnD`/pyrrolnitrin and `pvdA`/pyoverdine (0.76) down
to `olpA`/oligandrin (0.22, the rarest kingdom, so the noisiest estimate).

**"Per kingdom, how well do the gene score and the chemistry score agree?"** —
a table joined to *itself*: each strain appears twice (one row per block), and
the join lines its two rows up side by side.
```sql
SELECT g.kingdom, COUNT(*) AS strains,
       ROUND(corr(g.comp1, m.comp1), 2) AS agreement
FROM int_diablo_sample_scores g
JOIN int_diablo_sample_scores m USING (strain_id)
WHERE g.block = 'genomics' AND m.block = 'metabolomics'
GROUP BY g.kingdom
ORDER BY agreement DESC;
```
→ Bacteria 0.81, Fungi 0.74, Yeast 0.69, Oomycete 0.50 — agreement is strongest
where there are the most strains and weapons to learn from.

**"What did preparing the blocks change?"** — the Phase 3 ledger.
```sql
SELECT step, block, cells, note FROM int_prepare_ledger;
```
→ 338 gene calls and 714 metabolite readings filled within kingdom; `ef1a`,
`rpb1` and `ssu_rRNA` dropped as near-constant.

**Try it yourself:** per kingdom, how many of its weapons made DIABLO's robust
signature? (Hint: join `int_diablo_signature` with `int_feature_annotations`
and `GROUP BY arsenal`.)

<details>
<summary>One answer</summary>

```sql
SELECT a.arsenal, COUNT(*) AS weapons_in_signature
FROM int_diablo_signature s
JOIN int_feature_annotations a USING (feature)
WHERE s.component = 1 AND s.stability >= 0.8
GROUP BY a.arsenal
ORDER BY weapons_in_signature DESC;
```
→ Bacteria 16, Fungi 6, Yeast 4, Cross-kingdom 2, Oomycete 1 (29 in total).
</details>

---

*Recipes are added as the project grows — the app's SQL console (Phase 6) will
ship with this cookbook built in.*
