"""app/views/ranking.py: every strain, best first (Phase 4's ranking), with
the question a screening team asks: "if we can test N strains, which ones,
and how many would work?" Below it: how good the model is, in four charts."""
import json

import streamlit as st

import charts
import ui
from strainscope import narrate

uploaded = ui.showing_upload()
st.title("Ranking: your strains" if uploaded else "Ranking")
pred = ui.ranking()
if pred is None:
    ui.needs("The ranking comes from Phase 4, and artifacts/model/predictions.csv is missing.",
             "python src/strainscope/model.py all")
    st.stop()

if uploaded:
    st.markdown(f"The {len(pred)} strains from **{ui.upload()['name']}**, scored by the saved model. "
                "Switch back to the library in the sidebar.")
    with st.container(border=True):
        st.markdown("**In plain words**")
        st.markdown(narrate.shortlist(pred, len(pred), uploaded=True).text)
else:
    st.markdown("All 600 library strains, ranked by their predicted chance of being effective. Each chance "
                "comes from a model that **never saw that strain** while learning (out-of-fold), so the "
                "ranking is a fair test of how the model would do on new strains.")
    ui.simulated_note()

    # -- the screening question ------------------------------------------------
    st.header("If you can test N strains, how many would work?")
    n = st.slider("Strains you can test next season", 5, len(pred), 50, step=5, key="top_n")
    top = pred.nsmallest(n, "rank")
    found, chance = int(top["is_effective"].sum()), n * pred["is_effective"].mean()
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Effective among the top {n}", f"{found}", f"{found / n:.0%} of them", delta_color="off", delta_arrow="off")
    c2.metric("Picking at random would find", f"about {chance:.0f}", delta_color="off", delta_arrow="off")
    c3.metric("Effective strains you'd miss", f"{int(pred['is_effective'].sum()) - found}",
              f"of {int(pred['is_effective'].sum())} in the library", delta_color="off", delta_arrow="off")
    with st.container(border=True):
        st.markdown("**In plain words**")
        st.markdown(narrate.shortlist(pred, n).text)
        st.caption("Written by rules from the ranking. The model's chances are calibrated (Phase 4), so adding "
                   "them up gives the number it expects to work.")
    ui.chart(charts.top_n_figure(pred, n))

# -- the table ----------------------------------------------------------------
st.header("The list")
f1, f2, f3 = st.columns([2, 2, 1])
kingdoms = sorted(pred["kingdom"].dropna().unique())
chosen = f1.multiselect("Kingdoms", kingdoms, default=kingdoms)
search = f2.text_input("Find a strain or genus", placeholder="e.g. STRAIN_0485 or Bacillus")
flagged_only = f3.toggle("Flagged only", help="Strains whose chance is above the model's decision line "
                                              f"({(ui.card() or {}).get('decision_threshold', 0.5):.0%}, "
                                              "the library's share of effective strains).")
view = pred[pred["kingdom"].isin(chosen)]
if search:
    s = search.strip().lower()
    view = view[view["strain_id"].str.lower().str.contains(s, regex=False)
                | view.get("genus", view["strain_id"]).astype(str).str.lower().str.contains(s, regex=False)]
if flagged_only:
    view = view[view["predicted_effective"] == 1]
columns = [c for c in ["rank", "strain_id", "kingdom", "genus", "probability", "band", "predicted_effective",
                       "is_effective", "mechanism_paths", "library_rank", "strongest_reason"] if c in view.columns]
st.caption(f"{len(view)} strain(s). Click a row to open its page.")
event = st.dataframe(
    view[columns], hide_index=True, width="stretch", height=420, on_select="rerun",
    selection_mode="single-row", key="ranking_table",
    column_config={
        "rank": st.column_config.NumberColumn("rank", width="small"),
        "probability": st.column_config.ProgressColumn("chance of being effective", format="percent",
                                                       min_value=0, max_value=1),
        "band": st.column_config.TextColumn("how sure", help="the predicted chance in words: likely above 70 %, "
                                                             "borderline from 30 % to 70 %, unlikely below 30 %"),
        "predicted_effective": st.column_config.CheckboxColumn("flagged", help="above the decision line"),
        "is_effective": st.column_config.CheckboxColumn("effective in the data",
                                                        help="the simulated trial result (the answer key)"),
        "mechanism_paths": st.column_config.NumberColumn("mechanism paths",
                                                         help="routes in the knowledge graph from this strain "
                                                              "to disease suppression"),
        "library_rank": st.column_config.NumberColumn("would rank in the library"),
        "strongest_reason": "strongest reason",
    })
if event.selection.rows:
    ui.pick_strain(view.iloc[event.selection.rows[0]]["strain_id"])
st.download_button("Download this list (CSV)", view[columns].to_csv(index=False),
                   "strainscope_ranking.csv", "text/csv")

# -- how good is the model? -------------------------------------------------------
st.header("How good is the model?")
st.markdown(f"Four views of the model from Phase 4 ({ui.doc('05-machine-learning.md', 'docs/05-machine-learning.md')}). "
            "The numbers were measured on strains each model hadn't seen.")
board, curve, imp, card = (ui.artifact("model/scoreboard.csv"), ui.artifact("model/calibration_curve.csv"),
                           ui.artifact("model/feature_importance.csv"), ui.card())
t1, t2, t3, t4 = st.tabs(["Scoreboard", "Calibration", "What it relies on", "Model card"])
with t1:
    if board is not None:
        ui.chart(charts.model_scoreboard_figure(board))
        ui.numbers_behind(board[["model", "ber_mean", "ber_sd", "auc_mean", "accuracy_mean", "is_winner"]]
                          .sort_values("ber_mean").rename(columns={
                              "ber_mean": "balanced error", "ber_sd": "spread (sd)", "auc_mean": "AUC",
                              "accuracy_mean": "accuracy", "is_winner": "winner"}))
        st.caption("Balanced error rate: the average of the error on effective strains and the error on the "
                   "rest, so a lazy model that always says 'no' scores 0.50 even though it's right 76 % of the "
                   "time. The shuffled-label control should sit near a coin, and does.")
with t2:
    if curve is not None:
        ui.chart(charts.calibration_figure(curve))
        ui.numbers_behind(curve[["version", "bin_low", "bin_high", "n", "mean_predicted", "observed_rate"]].rename(
            columns={"n": "strains", "mean_predicted": "average chance said", "observed_rate": "share effective"}))
        st.caption("When the calibrated model says 70 %, about 70 % of those strains turn out effective. "
                   "That's what makes the chances on this page meaningful as chances.")
with t3:
    if imp is not None and card is not None:
        winner = imp[imp["model_key"] == card["model_key"]]
        ui.chart(charts.importance_figure(winner))
        ui.numbers_behind(winner.sort_values("rank")[["rank", "feature", "importance_mean", "importance_sd",
                                                      "reliably_important", "role", "block"]].rename(
            columns={"importance_mean": "importance", "importance_sd": "spread (sd)",
                     "reliably_important": "reliably important"}))
        st.caption("Green: a planted driver. Red: a decoy (it shouldn't matter). ✓: reliably important across "
                   "folds. `accE` is the one decoy the model leans on; the knowledge graph flags it as "
                   "'statistics only' on every strain page.")
with t4:
    if card is not None:
        st.markdown(f"**{card['model']}**. Intended use: {card['intended_use']}. Not for: {card['not_for']}.")
        st.code(json.dumps(card, indent=2), language="json")
