"""app/views/integration.py: Phase 3, reading genes and chemistry together.
The report card, DIABLO's signature, every method on one scoreboard, how R
and Python agree, and the gene-by-compound correlations."""
import streamlit as st

import charts
import ui

st.title("Integration: genes and chemistry, read together")
card = ui.artifact("integration/signature_report_card.csv")
if card is None:
    ui.needs("These results come from Phase 3, and artifacts/integration/ is empty.",
             "python src/strainscope/integrate.py all")
    st.stop()
st.markdown(
    "Each strain was measured twice: which genes it carries and how much of each compound it makes. "
    "Integration looks for the short list of features that tell **one story across both**. Because the data "
    "is simulated, we know which features really drive the outcome, so every list can be graded. "
    f"Explained step by step in {ui.doc('04-integration.md', 'docs/04-integration.md')}.")
ui.simulated_note()

st.header("The report card")
st.dataframe(card.rename(columns={"n_selected": "picked", "n_signal_selected": "true drivers",
                                  "n_decoys_selected": "decoys", "decoys_selected": "which decoys"}),
             hide_index=True, width="stretch",
             column_config={"precision": st.column_config.NumberColumn(format="%.2f", help="share of picks that are true drivers"),
                            "recall": st.column_config.NumberColumn(format="%.2f", help="share of true drivers that were picked")})
st.caption("Robust = picked in at least 80 % of re-fits on resampled data. DIABLO's robust list has no decoys, "
           "and every feature the Python lasso picks is on it too.")

sig, ann = ui.artifact("integration/diablo_signature.csv"), ui.artifact("integration/feature_annotations.csv")
summary = ui.artifact("integration/diablo_summary.csv")
board = ui.artifact("integration/python_scoreboard.csv")
left, right = st.columns([1, 1])
with left:
    st.header("DIABLO's signature")
    if sig is not None:
        ui.chart(charts.signature_figure(sig, ann))
        ui.numbers_behind(sig.sort_values(["component", "stability"], ascending=[True, False]))
        st.caption("Blue: genes. Gold: compounds. Red: a decoy that slipped in (none of them is robust).")
with right:
    st.header("Every method, same folds")
    if board is not None:
        diablo = None
        if summary is not None:
            values = dict(zip(summary["key"], summary["value"]))
            diablo = float(values["cv_ber_final"]) if "cv_ber_final" in values else None
        ui.chart(charts.integration_scoreboard_figure(board, diablo))
        ui.numbers_behind(board.rename(columns={"ber_mean": "balanced error", "ber_sd": "spread (sd)",
                                                "auc_mean": "AUC", "auc_sd": "AUC spread (sd)",
                                                "n_folds_scored": "folds"}))
        st.caption("Lower is better. The two grey controls (the kingdom label on its own, and shuffled "
                   "labels) must sit near a coin's 0.50 to show the scoring is fair, and they do. DIABLO's "
                   "bar is the number R reported in Phase 3.")
    agreement = ui.artifact("integration/language_agreement.csv")
    if agreement is not None:
        a = agreement.iloc[0]
        st.markdown(f"**R and Python, checking each other:** {int(a['in_both'])} features on both robust lists, "
                    f"{int(a['diablo_only'])} only in DIABLO's, {int(a['python_only'])} only in Python's.")

cross = ui.artifact("integration/cross_block_correlation.csv")
if cross is not None:
    st.header("Do genes and compounds rise together?")
    ui.chart(charts.correlation_heatmap(cross))
    ui.numbers_behind(cross.sort_values("spearman_rho", ascending=False).rename(
        columns={"spearman_rho": "correlation (Spearman)", "is_producer_pair": "the gene makes the compound"}),
        "this chart (strongest first)")
    st.caption("Spearman correlation between carrying each gene and the level of each compound. The bright "
               "red cells are genes and the compounds they make (phlD and DAPG, ituA and iturin, ...).")
