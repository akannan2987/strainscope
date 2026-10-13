# The Query Cookbook: ready-to-run SQL for the StrainScope database

[← README](../README.md) · [Handbook](HANDBOOK.md) · [All docs in order](../README.md#the-tutorial-in-order) · [Glossary](GLOSSARY.md)

Every query below is tested and runs against `data/processed/strainscope.duckdb`
(built in [Phase 2](03-harmonization-qc.md)). Run them in the app's **SQL
console**, where every recipe on this page is one click away ([`docs/07-app.md`
§9](07-app.md#9-step-5-the-sql-console)), or with the project's own console in a
terminal. Both are read-only and can't touch files on your computer, so you can
explore without any fear of breaking something:

```bash
# one query, straight from the shell:
python src/strainscope/sql.py "SELECT COUNT(*) FROM phenotype"

# or an interactive session - paste recipes one after another:
python src/strainscope/sql.py
sql> .tables                  -- list every table  (recipes below are multi-line:
sql> .schema phenotype        --  paste them whole; ';' ends a statement)
sql> exit
```

*(Prefer a standalone tool? The official DuckDB CLI speaks the same SQL:
install it with `brew install duckdb`,
then run `duckdb -readonly data/processed/strainscope.duckdb`. The console
above needs no installation and behaves identically.)*

This file grows every phase. SQL reads almost like English, so each recipe
below is headed by the plain-English question it answers. Those questions
matter twice since Phase 7: the app's **Ask the data** page (and
`python src/strainscope/ask_data.py "..."`) answers a question in words by
finding the recipe whose question matches it, and runs that recipe
([`docs/08-deployment-ai.md` §6](08-deployment-ai.md#6-step-2-ask-the-data)).
Since Phase 7b, an AI assistant app can do the same through the MCP server's
`ask_data` tool, or write its own query with `query_database`, which accepts one
`SELECT` and returns at most 200 rows
([`docs/08b-mcp-server.md` §18](08b-mcp-server.md#18-same-task-two-ways-the-sql-console-and-asking-your-assistant-optional-10-min)).

**On a dataset of your own (Phase 9).** Each dataset has its own database with
the same tables, so the recipes run there too: choose the dataset in the app's
sidebar, or name it for the terminal console (macOS and Linux:
`STRAINSCOPE_DATASET=trial python src/strainscope/sql.py`; Windows PowerShell:
`$env:STRAINSCOPE_DATASET = "trial"` before the usual command, and
`Remove-Item Env:STRAINSCOPE_DATASET` afterwards). Three things differ. A
recipe that names a gene or compound column (`ituA`, `iturin`) needs that
column in your tables; the numbers quoted under each recipe are the library's;
and the planted-truth columns of §8 and §9 (`role`, the grades) say
`not graded` (known housekeeping genes keep that label), because your data has no answer key
([`docs/10-workflow-and-your-data.md`](10-workflow-and-your-data.md#no-answer-key-for-your-own-data)).

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
→ `600` (the clean count, with duplicates removed). `AS n_strains` just names the output column.

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
(You'll notice scores capped at exactly 100.00. Those are the "impossible"
readings that cleaning clipped, now stored as valid boundary values.)

## 3. Grouping: one row per category

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
0/1 column *is* the effective rate (a classic trick).

## 4. JOIN: the payoff of a shared key

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
`JOIN … USING (strain_id)` lines tables up on the shared key, which is the whole
reason every table carries `strain_id`. Run it and look: the top strains all show
`ituA = 1` with high iturin, so the biology is already visible in five lines of
SQL.

## 5. NULL: the gaps left in plain sight

**"How many iturin readings are missing?"**
```sql
SELECT COUNT(*) AS missing_iturin
FROM metabolomics
WHERE iturin IS NULL;
```
`NULL` is SQL's "no value here." Note the special grammar: `IS NULL`, never
`= NULL` (a common beginner trap: `= NULL` silently matches nothing).
Cleaning kept these gaps on purpose, and the modelling phases decide what to do
about them in the open.

## 6. The real tables: same database, same SQL

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

## 7. Synthetic meets real: one query across both worlds

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
(or `integrate.py all`); see [`docs/04-integration.md` §9](04-integration.md#9-step-5-publish-to-the-database-and-ask-it-questions).
Every Phase 3 table starts with `int_`; `.tables` lists them. *(The data is
simulated, so these numbers prove the workflow and make no claim about
real-world accuracy.)*

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
0.5, which is exactly where a coin toss sits. *Lower BER is better; higher AUC is better.*

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

**"How much did centring within kingdom help?"** One row per component, with
the two versions side by side. `FILTER (WHERE …)` picks which rows each column
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
the component-1 centred value as 0.154 and DuckDB as 0.155; the true value is
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
picks, 17 true drivers, so perfect precision but lower recall (it keeps fewer).

**"Which features do R and Python both trust?"** These are DIABLO's robust picks
that the lasso also picked in at least 80 % of folds.
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
→ 17 features, the same as the "in both" number of `int_language_agreement`.
R and Python, using different methods, agree on the same core set.

**"Do genes and their own products rise together?"**
```sql
SELECT gene, metabolite, ROUND(spearman_rho, 2) AS rho
FROM int_cross_block_correlation
WHERE is_producer_pair
ORDER BY rho DESC;
```
→ 14 producer pairs, from `prnD`/pyrrolnitrin and `pvdA`/pyoverdine (0.76) down
to `olpA`/oligandrin (0.22, the rarest kingdom, so the noisiest estimate).

**"Per kingdom, how well do the gene score and the chemistry score agree?"**
This one joins a table to *itself*: each strain appears twice (one row per
block), and the join lines its two rows up side by side.
```sql
SELECT g.kingdom, COUNT(*) AS strains,
       ROUND(corr(g.comp1, m.comp1), 2) AS agreement
FROM int_diablo_sample_scores g
JOIN int_diablo_sample_scores m USING (strain_id)
WHERE g.block = 'genomics' AND m.block = 'metabolomics'
GROUP BY g.kingdom
ORDER BY agreement DESC;
```
→ Bacteria 0.81, Fungi 0.74, Yeast 0.69, Oomycete 0.50. Agreement is strongest
where there are the most strains and weapons to learn from.

**"What did preparing the blocks change?"** This reads the Phase 3 ledger.
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

## 9. Machine-learning results (Phase 4)

These tables exist once you have run `python src/strainscope/model.py publish`
(or `model.py all`); see [`docs/05-machine-learning.md` §9](05-machine-learning.md#9-step-5-publish-to-the-database-and-ask-it-questions).
Every Phase 4 table starts with `ml_`. *(Simulated data again: read these
numbers as proof of the workflow, with no claim about real-world accuracy.)*

> **If a table is missing:** `src/strainscope/harmonize.py` rebuilds the database
> from scratch; re-run `python src/strainscope/model.py publish`.

**"Every model, best first, with the scores side by side."**
```sql
SELECT model,
       ROUND(ber_mean, 3) AS ber, ROUND(ber_base_rate_mean, 3) AS ber_at_base,
       ROUND(auc_mean, 3) AS auc, ROUND(accuracy_mean, 3) AS accuracy, is_winner
FROM ml_scoreboard
ORDER BY ber_mean;
```
→ elastic net first (0.128, AUC 0.948); the baseline last with balanced error 0.500,
yet with the *highest* accuracy but one (0.758). Accuracy flatters the lazy model,
which is why the balanced error is the main score.

**"The ranking a screening team would use: the top 10."**
```sql
SELECT rank, strain_id, kingdom, ROUND(probability, 3) AS probability, is_effective
FROM ml_predictions
ORDER BY rank
LIMIT 10;
```
→ ten strains, all truly effective; bacteria lead, but a yeast, an oomycete and a
fungus are already in the top 10. The probabilities are *out-of-fold*: no strain
was ranked by a model that had seen it.

**"Which kingdoms make the top 50, and how many really work?"**
```sql
SELECT kingdom, COUNT(*) AS in_top_50, SUM(is_effective)::INT AS truly_effective
FROM ml_predictions
WHERE rank <= 50
GROUP BY kingdom
ORDER BY in_top_50 DESC;
```
→ Bacteria 34 (32 effective), Fungi 11 (11), Yeast 4 (3), Oomycete 1 (1): 47 of
50, where random picking would find about 12. `::INT` turns the sum into a whole
number.

**"The strains decided by a hair: hard cases within one point of the 65 % line."**
```sql
SELECT strain_id, kingdom, suppression_score, is_effective,
       ROUND(probability, 2) AS probability, missed_by_all_models
FROM ml_hard_strains
WHERE distance_to_cutoff < 1
ORDER BY distance_to_cutoff;
```
→ seven strains. The first, `STRAIN_0082`, shows 65.00 but is labelled *not
effective*: its true score was a hair under 65 and was rounded when stored. All
three models call it effective. The full story is in
[`docs/05-machine-learning.md` §12](05-machine-learning.md#12-notes-from-the-build-kept-on-purpose).

**"Did the winner lean on any decoys?"**
```sql
SELECT feature, arsenal, ROUND(importance_mean, 4) AS auc_drop, reliably_important
FROM ml_feature_importance
WHERE model_key = 'elastic_net' AND role = 'decoy'
ORDER BY importance_mean DESC
LIMIT 5;
```
→ one decoy is reliably important, `accE` (AUC drop 0.0056); the next ones drop
the AUC by less than 0.001, which is too little to matter.

**"Which of DIABLO's robust features does the winner NOT rely on?"** This joins
the results of two phases on the feature name.
```sql
SELECT f.feature,
       ROUND(f.importance_mean, 4) AS model_auc_drop,
       ROUND(d.loading, 3) AS diablo_weight, d.stability AS diablo_stability
FROM ml_feature_importance f
JOIN int_diablo_signature d ON d.feature = f.feature AND d.component = 1
WHERE f.model_key = 'elastic_net' AND NOT f.reliably_important AND d.stability >= 0.8
ORDER BY d.stability DESC, ABS(d.loading) DESC;
```
→ eight features (pyoverdine, destruxin, yeast_siderophore, HCN, beaS,
pyrrolnitrin, surfactin, killer_toxin), mostly the *chemical products* of genes
the elastic net already uses. Gene and product are two witnesses to one story;
DIABLO keeps both, while a penalised model keeps one. (Needs the Phase 3 tables.)

**"The leak check, as a table."**
```sql
SELECT setup, ROUND(auc_mean, 3) AS auc FROM ml_leak_check ORDER BY setup;
```
→ A1 0.948 and A2 0.947 (Phase 3's leak was harmless); B1 0.594 against B2 0.528
on *meaningless* labels, where B1 shows a real leak manufacturing signal. (The command line
prints B2 as 0.527: the true value sits on the rounding edge, and the two round
halves differently.)

**"Does the model mean what it says?"**
```sql
SELECT version, ROUND(mean_predicted_mean, 3) AS says,
       ROUND(observed_rate_mean, 3) AS happens, ROUND(ece_pooled, 3) AS calibration_error
FROM ml_calibration_summary;
```
→ raw: says 0.323, happens 0.242, error 0.081; calibrated: says 0.243, error 0.033.

**Try it yourself:** per kingdom, how many strains are *borderline*, with a
probability between 0.3 and 0.7? (Hint: `ml_predictions`, `WHERE probability
BETWEEN 0.3 AND 0.7`, `GROUP BY kingdom`.)

<details>
<summary>One answer</summary>

```sql
SELECT kingdom, COUNT(*) AS borderline
FROM ml_predictions
WHERE probability BETWEEN 0.3 AND 0.7
GROUP BY kingdom
ORDER BY borderline DESC;
```
</details>

---

## 10. The knowledge graph (Phase 5)

These tables exist once you have run `python src/strainscope/graph.py publish`
(or `graph.py all`); see [`docs/06-knowledge-graph.md` §9](06-knowledge-graph.md#9-step-5-publish-to-the-database-and-ask-it-in-sql).
Every Phase 5 table starts with `kg_`. The graph itself is two tables:
`kg_nodes` (one row per thing) and `kg_edges` (one row per connection, with
`from_id`, `relation`, `to_id`, `weight` and its source in `provenance`). Node
ids carry their type in front, as in `gene:ituA` or `strain:STRAIN_0485`.
*(The numbers below come from a run without the real tables of Phases 1b and
1c; with them you'll also see pathway, chemical-class and reference-strain rows.)*

> **If a table is missing:** `src/strainscope/harmonize.py` rebuilds the database
> from scratch; re-run `python src/strainscope/graph.py publish`.

**"What kinds of things are in the graph, and how many of each?"**
```sql
SELECT node_type, COUNT(*) AS nodes
FROM kg_nodes
GROUP BY node_type
ORDER BY nodes DESC;
```
→ Strain 600, Gene 31, Compound 20, Genus 13, ModeOfAction 9, Kingdom 4,
Outcome 2.

**"Where does every connection come from?"**
```sql
SELECT relation, provenance, COUNT(*) AS edges
FROM kg_edges
GROUP BY relation, provenance
ORDER BY edges DESC;
```
→ nine rows, from `carries` (5,880 edges from the synthetic library) down to
`contributes_to` (9 edges from the domain model). `associated_with` appears
twice: 29 edges from Phase 3's DIABLO signature and 23 from Phase 4's model.
Every edge has a source; this query is how you check.

**"Which compounds does the top strain produce, and how does each one work?"** A
two-hop walk: strain → compound, then compound → mode of action, written as a
join of the edge table with itself.
```sql
SELECT REPLACE(p.to_id, 'compound:', '') AS compound,
       ROUND(p.weight, 1) AS times_usual_level,
       REPLACE(a.to_id, 'mode:', '') AS mode_of_action
FROM kg_edges p
JOIN kg_edges a ON a.from_id = p.to_id AND a.relation = 'acts_by'
WHERE p.from_id = 'strain:STRAIN_0485' AND p.relation = 'produces'
ORDER BY times_usual_level DESC;
```
→ nine rows, phenazine first (51.9 times the usual level, antibiosis).
The last row, oligandrin at 4.1 times, is an oomycete's elicitor in a bacterium
that doesn't carry `olpA`. It turns out to be ordinary background noise just over
the 4x line rather than a planted spike ([the story](06-knowledge-graph.md#12-notes-from-the-build-kept-on-purpose)).

**"Where do the biology and the data agree?"**
```sql
SELECT verdict, COUNT(*) AS features
FROM kg_knowledge_vs_data
GROUP BY verdict
ORDER BY features DESC;
```
→ confirmed 30, no link to disease suppression 15, mechanism only 2 (`ech42`,
`prb1`), data only 1 (`accE`, the decoy Phase 4 already flagged).

**"What turns up together? The communities and their members."**
```sql
SELECT community, COUNT(*) AS features,
       STRING_AGG(label, ', ' ORDER BY label) AS members
FROM kg_communities
WHERE community > 0
GROUP BY community
ORDER BY community;
```
→ four communities: the bacterial weapons (19 features, with three plant-growth
genes that are common in bacteria), the fungal weapons (9), the yeast weapons (4)
and the oomycete pair (2). `community = -1` means "no strong ties"; drop the
`WHERE` line to see those 14 too.

**"The most connected nodes, and what they are."**
```sql
SELECT label, node_type, degree, strains_connected
FROM kg_hubs
ORDER BY degree DESC
LIMIT 5;
```
→ ssu_rRNA, ef1a and rpb1 (the housekeeping genes, 577 to 579 strains), then
accE and accB. The biggest hubs carry no information about performance; sort by
`betweenness` instead to find the concepts that bridge the most routes.

**"Why do the top two strains rank where they do?"**
```sql
SELECT rank, strain_id, kind, text
FROM kg_explanations
WHERE rank <= 2
ORDER BY rank, "order";
```
→ ten rows: for each strain its mechanism paths (`kind = 'mechanism'`), the
`accE` flag (`data only`) and, for STRAIN_0103, two weapons common in bacteria
that it lacks (`missing`). `"order"` sits in double quotes because ORDER is a
SQL keyword.

**"Every route from ituA to an outcome", walked inside the database.** A
*recursive* query keeps joining the edge table to its own results, one step
further each time:
```sql
WITH RECURSIVE walk(node, depth, route) AS (
    SELECT 'gene:ituA', 0, 'ituA'
    UNION ALL
    SELECT e.to_id, w.depth + 1, w.route || ' > ' || SPLIT_PART(e.to_id, ':', 2)
    FROM walk w
    JOIN kg_edges e ON e.from_id = w.node
    WHERE w.depth < 3 AND e.relation IN ('makes', 'acts_by', 'contributes_to')
)
SELECT DISTINCT depth, route
FROM walk
ORDER BY depth, route;
```
→ six rows, ending in the two complete routes: `ituA > lipopeptide membrane
attack > disease suppression` and `ituA > iturin > lipopeptide membrane attack >
disease suppression`. SQL can walk a graph, but each extra step makes it harder
to read, which is why the graph itself lives in NetworkX
([`docs/06-knowledge-graph.md` §15](06-knowledge-graph.md#15-same-question-two-ways-sql-joins-and-a-graph-walk-optional-10-min)).

**Try it yourself:** list the ten strains with the most mechanism paths. (Hint:
`kg_explanations`, column `mechanism_paths`, one row per strain.) Then look at
the one ranked far below the others with `python src/strainscope/graph.py show`
on its id: what do several of its "produces" edges have in common?

<details>
<summary>One answer</summary>

```sql
SELECT strain_id, rank, MAX(mechanism_paths) AS mechanism_paths
FROM kg_explanations
GROUP BY strain_id, rank
ORDER BY mechanism_paths DESC, rank
LIMIT 10;
```

STRAIN_0485 leads with 10. STRAIN_0276 has 8 but ranks 108th: it produces DAPG,
iturin and the fungal toxin destruxin without carrying the genes that make them,
and its pvdA call is missing, so several of its "paths" rest on readings that may
be spikes or background noise. The model gives it 54 % (borderline), and in the data it
isn't effective.
</details>

---

*Recipes are added as the project grows. The app's SQL console reads its menu
from this file, and Ask the data searches it, so a new recipe here (a bold,
quoted question followed by a fenced `sql` code block) shows up in both without
changing any code; a test checks that every recipe is found and runs. Write the
question the way someone would ask it: that's what Ask the data matches.*
