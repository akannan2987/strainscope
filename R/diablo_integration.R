# =============================================================================
# R/diablo_integration.R — StrainScope Phase 3: DIABLO multi-omics integration
# =============================================================================
#
# WHAT THIS SCRIPT DOES (in one sentence)
#   It reads the two prepared blocks (genes, chemistry) plus the outcome, asks
#   DIABLO — the supervised integration method from the mixOmics package — to
#   find the small set of genes AND metabolites that, together, best separate
#   effective strains from the rest, measures how well that works with honest
#   cross-validation, and saves small result tables and figures.
#
# HOW TO RUN IT (from the project root, so renv switches on automatically)
#   Rscript R/diablo_integration.R
#   (Windows, if Rscript is not on your PATH:
#    & "C:\Program Files\R\R-4.x.x\bin\Rscript.exe" R/diablo_integration.R)
#
# BEFORE YOU RUN IT
#   python src/strainscope/integrate.py prepare     # writes the blocks it reads
#
# WHAT IT WRITES
#   artifacts/integration/diablo_error_by_component.csv  error per component, both versions
#   artifacts/integration/diablo_tuning.csv              error for every keepX tried
#   artifacts/integration/diablo_signature.csv           the selected features (+ stability)
#   artifacts/integration/diablo_sample_scores.csv       every strain's position on the components
#   artifacts/integration/diablo_summary.csv             the decisions and headline numbers
#   figures/diablo_mixomics_*.png                        mixOmics' own standard plots
#
# THE KEY IDEA IN ONE PARAGRAPH
#   A plain classifier looks at one big table. DIABLO keeps each block separate
#   and looks for a "summary score" per block (a weighted sum of a FEW of its
#   features) such that (a) the scores of different blocks agree with each
#   other and (b) they separate effective from not-effective strains. The few
#   features with non-zero weight are the "signature". `keepX` says how many
#   features each block may use; `design` says how strongly the blocks must
#   agree. Everything below is choosing those two things honestly.
# =============================================================================

started <- Sys.time()
set.seed(42)                       # the same seed as the rest of the project

# --- 0. Packages -------------------------------------------------------------
# mixOmics is installed into this project's renv library (docs/04-integration.md,
# Step 2). If this line fails, that step was skipped.
if (!requireNamespace("mixOmics", quietly = TRUE)) {
  stop("mixOmics is not installed in this project's R library.\n",
       "  Inside the project folder run:  Rscript -e 'renv::install(c(\"BiocManager\", \"bioc::mixOmics\"))'\n",
       "  then:                            Rscript -e 'renv::snapshot()'\n",
       "  (details: docs/04-integration.md, section 6)", call. = FALSE)
}
suppressPackageStartupMessages(library(mixOmics))

# --- 1. Paths (relative to the project root: identical on every OS) ----------
blocks_dir   <- file.path("data", "processed", "integration")
out_dir      <- file.path("artifacts", "integration")
fig_dir      <- "figures"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(fig_dir, showWarnings = FALSE)

needed <- file.path(blocks_dir, c("block_genomics.csv", "block_metabolomics.csv",
                                  "block_genomics_centred.csv",
                                  "block_metabolomics_centred.csv", "outcome.csv"))
if (!all(file.exists(needed))) {
  stop("The prepared blocks are missing. Run this first, from the project root:\n",
       "  python src/strainscope/integrate.py prepare", call. = FALSE)
}

read_block <- function(name) as.matrix(read.csv(file.path(blocks_dir, name),
                                                row.names = 1, check.names = FALSE))
outcome <- read.csv(file.path(blocks_dir, "outcome.csv"), row.names = 1)

# The outcome as a two-level factor. The levels are deliberately in
# ALPHABETICAL order: mixOmics' heatmap legend sorts class names alphabetically
# but colours them in factor order, so any other order makes the legend swap
# the colours (see "Notes from the build" in docs/04-integration.md).
Y <- factor(ifelse(outcome$is_effective == 1, "effective", "not_effective"),
            levels = c("effective", "not_effective"))

versions <- list(
  as_measured = list(genomics     = read_block("block_genomics.csv"),
                     metabolomics = read_block("block_metabolomics.csv")),
  centred     = list(genomics     = read_block("block_genomics_centred.csv"),
                     metabolomics = read_block("block_metabolomics_centred.csv")))

# Safety check: every block lists the same strains in the same order.
for (v in versions) stopifnot(identical(rownames(v$genomics), rownames(outcome)),
                              identical(rownames(v$metabolomics), rownames(outcome)))

cat("\n  ── DIABLO integration ─────────────────────────────────────────\n")
cat(sprintf("  mixOmics %s · %d strains (%d effective) · %d genes · %d metabolites\n",
            as.character(packageVersion("mixOmics")), nrow(outcome),
            sum(outcome$is_effective), ncol(versions$centred$genomics),
            ncol(versions$centred$metabolomics)))

# --- 2. The design matrix: how strongly must the blocks agree? ---------------
# 0 = "ignore each other", 1 = "agree as much as possible". 0.1 is mixOmics'
# recommended starting point when the goal is PREDICTION: the blocks are nudged
# to tell a common story, but each keeps its own voice.
design <- matrix(0.1, nrow = 2, ncol = 2,
                 dimnames = list(c("genomics", "metabolomics"),
                                 c("genomics", "metabolomics")))
diag(design) <- 0

# Honest yardstick shared by every step below:
#   5-fold cross-validation, repeated 10 times, seeded.
#   Error = BER (balanced error rate) of the weighted vote across blocks,
#   classifying each strain by the nearest class centre ("centroids.dist").
FOLDS <- 5; NREPEAT <- 10; DIST <- "centroids.dist"

ber_table <- function(perf_obj) {
  m <- perf_obj$WeightedVote.error.rate[[DIST]]
  s <- perf_obj$WeightedVote.error.rate.sd[[DIST]]
  data.frame(component = seq_len(ncol(m)),
             ber = round(as.numeric(m["Overall.BER", ]), 4),
             ber_sd = round(as.numeric(s["Overall.BER", ]), 4))
}

# --- 3. Which version, and how many components? ------------------------------
# A "component" is one summary score per block. More components can capture
# more structure, but each must EARN its place by lowering the error.
cat("  step 1/4  comparing as-measured vs centred-within-kingdom (all features, 4 components) …\n")
# (mixOmics prints a note about the design matrix on every fit; suppressMessages
#  keeps the console readable — it hides notes, never errors.)
error_by_comp <- do.call(rbind, lapply(names(versions), function(vname) {
  full <- suppressMessages(block.plsda(versions[[vname]], Y, ncomp = 4, design = design))
  pf <- suppressMessages(perf(full, validation = "Mfold", folds = FOLDS, nrepeat = NREPEAT,
                              dist = DIST, seed = 42))
  cbind(version = vname, ber_table(pf))
}))
write.csv(error_by_comp, file.path(out_dir, "diablo_error_by_component.csv"), row.names = FALSE)

best_version <- error_by_comp$version[which.min(error_by_comp$ber)]
chosen <- error_by_comp[error_by_comp$version == best_version, ]
# The "one standard deviation" rule: the FEWEST components whose error is
# within one standard deviation of the very best. Simpler models that are
# statistically as good are preferred — they generalise and explain better.
best_row <- which.min(chosen$ber)
ncomp_rule <- min(which(chosen$ber <= chosen$ber[best_row] + chosen$ber_sd[best_row]))
ncomp <- max(2, ncomp_rule)   # at least 2, so the strains can be drawn on a 2-D map
for (v in unique(error_by_comp$version)) {
  e <- error_by_comp[error_by_comp$version == v, ]
  cat(sprintf("            %-12s BER by component: %s\n", v,
              paste(sprintf("%.3f", e$ber), collapse = "  ")))
}
cat(sprintf("            → using '%s' blocks; one-SD rule says %d component(s); keeping %d\n",
            best_version, ncomp_rule, ncomp))
X <- versions[[best_version]]

# --- 4. Tune keepX: how many features may each block use? --------------------
# Sparse = most weights are exactly zero, so the signature is a short list a
# scientist can read. We try a grid of list lengths per block and keep the
# combination with the lowest cross-validated error.
cat("  step 2/4  tuning keepX (how many features per block) …\n")
# The list lengths tried. The cap at 16 is a deliberate READABILITY choice: a
# signature a scientist can read beats a slightly better one nobody can. Step 3
# measures exactly what the cap costs (see "cost of sparsity" in the summary).
grid <- list(genomics = c(4, 8, 12, 16), metabolomics = c(4, 8, 12, 16))
tune <- suppressMessages(tune.block.splsda(X, Y, ncomp = ncomp, test.keepX = grid,
                                           design = design, validation = "Mfold",
                                           folds = FOLDS, nrepeat = 5, dist = DIST,
                                           measure = "BER", seed = 42))
keepX <- tune$choice.keepX
tune_err <- as.data.frame(as.table(tune$error.rate))
names(tune_err) <- c("keepX_combination", "component", "ber")
write.csv(tune_err, file.path(out_dir, "diablo_tuning.csv"), row.names = FALSE)
cat(sprintf("            → genomics keepX = %s · metabolomics keepX = %s (per component)\n",
            paste(keepX$genomics, collapse = ", "), paste(keepX$metabolomics, collapse = ", ")))

# --- 5. The final model, and its honest score --------------------------------
cat("  step 3/4  fitting the final model and cross-validating it …\n")
final <- suppressMessages(block.splsda(X, Y, ncomp = ncomp, keepX = keepX, design = design))
pf_final <- suppressMessages(perf(final, validation = "Mfold", folds = FOLDS,
                                  nrepeat = NREPEAT, dist = DIST, seed = 42))
final_ber <- ber_table(pf_final)
per_class <- pf_final$WeightedVote.error.rate[[DIST]]
# The cost of sparsity: the same number of components, but every feature used
# (from step 1) versus the short lists. Within one SD = "statistically free".
all_features_ber <- chosen$ber[ncomp]
sparsity_cost <- round(final_ber$ber[ncomp] - all_features_ber, 4)

# AUC per block (area under the ROC curve on the training data — an
# optimistic, descriptive number; the cross-validated BER above is the honest one).
auc <- auroc(final, roc.comp = ncomp, print = FALSE, plot = FALSE)
auc_of <- function(block) round(as.numeric(auc[[block]][[paste0("comp", ncomp)]][1, 1]), 4)

# --- 6. The signature, with stability ----------------------------------------
# Stability = in what fraction of the 50 cross-validation fits was this
# feature selected? A feature picked in 100 % of re-fits is a robust finding;
# one picked in 20 % is a coin-toss and should be read with caution.
# mixOmics versions differ in how they store this: newer ones keep one table per
# repeat ("nrep1", "nrep2", …), older ones a single table. This helper averages
# over repeats when needed, counting "not selected in that repeat" as 0.
stability_of <- function(block, comp) {
  st <- pf_final$features$stable
  per_rep <- if (any(grepl("^nrep", names(st)))) {
    lapply(st, function(r) r[[block]][[paste0("comp", comp)]])
  } else list(st[[block]][[paste0("comp", comp)]])
  feats <- unique(unlist(lapply(per_rep, names)))
  vapply(feats, function(f) mean(vapply(per_rep, function(tab)
    if (f %in% names(tab)) as.numeric(tab[[f]]) else 0, numeric(1))), numeric(1))
}
signature <- do.call(rbind, lapply(seq_len(ncomp), function(comp) {
  sv <- selectVar(final, comp = comp)
  do.call(rbind, lapply(c("genomics", "metabolomics"), function(block) {
    vals <- sv[[block]]$value
    stab <- stability_of(block, comp)
    stab_of <- function(f) if (f %in% names(stab)) as.numeric(stab[[f]]) else NA
    data.frame(block = block, component = comp, feature = rownames(vals),
               loading = round(vals$value.var, 4),
               stability = round(vapply(rownames(vals), stab_of, numeric(1)), 3),
               row.names = NULL)
  }))
}))
write.csv(signature, file.path(out_dir, "diablo_signature.csv"), row.names = FALSE)

# --- 7. Every strain's position on the components (for maps and the app) -----
scores <- do.call(rbind, lapply(c("genomics", "metabolomics"), function(block) {
  v <- final$variates[[block]]
  data.frame(strain_id = rownames(v), block = block,
             comp1 = round(v[, 1], 5), comp2 = round(v[, 2], 5), row.names = NULL)
}))
scores$kingdom <- outcome[scores$strain_id, "kingdom"]
scores$is_effective <- outcome[scores$strain_id, "is_effective"]
write.csv(scores, file.path(out_dir, "diablo_sample_scores.csv"), row.names = FALSE)

# How strongly do the two blocks' summary scores agree? (the "consensus")
block_agreement <- round(cor(final$variates$genomics[, 1],
                             final$variates$metabolomics[, 1]), 4)

summary_tbl <- data.frame(key = c(
  "mixomics_version", "r_version", "seed", "folds", "nrepeat", "distance",
  "design_off_diagonal", "version_used", "ncomp_one_sd_rule", "ncomp_fitted",
  "keepX_genomics", "keepX_metabolomics", "cv_ber_final", "cv_ber_final_sd",
  "cv_ber_all_features", "sparsity_cost",
  "cv_error_effective", "cv_error_not_effective", "auc_genomics_train",
  "auc_metabolomics_train", "block_agreement_comp1", "n_signature_features",
  "runtime_seconds"),
  value = c(as.character(packageVersion("mixOmics")),
            paste(R.version$major, R.version$minor, sep = "."), 42, FOLDS, NREPEAT,
            DIST, 0.1, best_version, ncomp_rule, ncomp,
            paste(keepX$genomics, collapse = ";"), paste(keepX$metabolomics, collapse = ";"),
            final_ber$ber[ncomp], final_ber$ber_sd[ncomp],
            all_features_ber, sparsity_cost,
            round(per_class["effective", ncomp], 4),
            round(per_class["not_effective", ncomp], 4),
            auc_of("genomics"), auc_of("metabolomics"), block_agreement,
            length(unique(signature$feature)),
            round(as.numeric(difftime(Sys.time(), started, units = "secs")))))
write.csv(summary_tbl, file.path(out_dir, "diablo_summary.csv"), row.names = FALSE)

# --- 8. mixOmics' own standard figures ---------------------------------------
# These are the plots specialists expect to see; the project's own teaching
# versions are drawn in Python by figures/make_phase3_figures.py.
cat("  step 4/4  drawing mixOmics' standard figures …\n")
save_png <- function(file, width, height, expr) {
  grDevices::png(file.path(fig_dir, file), width = width, height = height, res = 120)
  on.exit(grDevices::dev.off())
  invisible(force(expr))   # invisible: don't echo the plot's data to the console
}
cols <- c(effective = "#4CAF7D", not_effective = "#8A94A6")   # same order as levels(Y)
save_png("diablo_mixomics_samples.png", 1300, 650,
         plotIndiv(final, ind.names = FALSE, legend = TRUE, ellipse = TRUE,
                   title = "DIABLO: strains on components 1-2", style = "ggplot2"))
save_png("diablo_mixomics_loadings.png", 1300, 800,
         plotLoadings(final, comp = 1, contrib = "max", method = "mean",
                      legend.color = cols, title = "Component 1 loadings"))
# The circos plot draws a link between a gene and a metabolite when their
# similarity on the components passes a cutoff. A fixed cutoff can draw nothing
# (or everything); we take 80 % of the strongest cross-block link instead.
sim <- local({ grDevices::pdf(NULL); on.exit(grDevices::dev.off()); circosPlot(final, cutoff = 0) })
cross <- sim[intersect(rownames(sim), colnames(X$genomics)),
             intersect(colnames(sim), colnames(X$metabolomics)), drop = FALSE]
circos_cutoff <- floor(0.8 * max(abs(cross)) * 100) / 100
save_png("diablo_mixomics_circos.png", 1100, 1100,
         circosPlot(final, cutoff = circos_cutoff, line = TRUE, color.blocks = c("#5B8DEF", "#C9A227"),
                    color.cor = c("#D9634C", "#4CAF7D"), size.labels = 1.2))
save_png("diablo_mixomics_cim.png", 1300, 1000,
         utils::capture.output(cimDiablo(final, color.blocks = c("#5B8DEF", "#C9A227"),
                   color.Y = unname(cols), comp = seq_len(ncomp),
                   margin = c(8, 18), legend.position = "topright", size.legend = 0.8)))

elapsed <- round(as.numeric(difftime(Sys.time(), started, units = "secs")))
cat("  ───────────────────────────────────────────────────────────────\n")
cat(sprintf("  final model: %d components · cross-validated BER %.3f ± %.3f\n",
            ncomp, final_ber$ber[ncomp], final_ber$ber_sd[ncomp]))
n_sd <- abs(sparsity_cost) / final_ber$ber_sd[ncomp]
cat(sprintf("  cost of sparsity: %+.3f BER vs using every feature (%.3f) = %.1f SD — %s\n",
            sparsity_cost, all_features_ber, n_sd,
            ifelse(n_sd < 0.9, "statistically free",
                   ifelse(n_sd <= 2, "a small, measurable price for a readable list",
                          "a real price: consider longer lists"))))
cat(sprintf("  error on effective strains %.3f · on the rest %.3f\n",
            per_class["effective", ncomp], per_class["not_effective", ncomp]))
cat(sprintf("  signature: %d distinct features · blocks agree at r = %.2f on component 1\n",
            length(unique(signature$feature)), block_agreement))
cat(sprintf("  results → %s/   figures → %s/diablo_mixomics_*.png   (%d s)\n",
            out_dir, fig_dir, elapsed))
cat("  Reminder: the data is SIMULATED — this proves the workflow, not real-world accuracy.\n")
