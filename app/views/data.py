"""app/views/data.py: choose the data. Three tabs: the simulated library
(and rebuilding its database), your own strains (upload a CSV, get them
checked, scored and explained), and real data from public databases."""
import io

import pandas as pd
import streamlit as st

import ui
from strainscope import service as sv

st.title("Data")
st.markdown("Three sources of strains and facts. The library is always there; the other two are optional.")

synthetic, uploaded, real = st.tabs(["Synthetic library", "Upload your strains", "Real data"])

# =============================================================================
with synthetic:
    st.header("The simulated library: 600 strains, four kingdoms")
    st.markdown(
        "Made by `src/strainscope/generate_data.py` with a fixed seed (42), so it's the same on every computer. "
        "Each strain has 31 gene calls, 20 compound levels and a trial score. Mess was added on purpose "
        "(gaps, duplicates, drift between lab batches, a few impossible scores) and cleaned away in Phase 2. "
        f"Details: {ui.doc('02-data-generation.md', 'docs/02-data-generation.md')}.")
    tables = ui.tables()
    if len(tables):
        by_group = tables.groupby("group").agg(tables=("table", "count"), rows=("rows", "sum")).reset_index()
        st.dataframe(by_group, hide_index=True, width="content",
                     column_config={"group": "where the tables come from", "rows": st.column_config.NumberColumn(format="localized")})
    else:
        st.info("No database yet.")
    spec = sv.PIPELINES["database"]
    st.markdown(f"**{spec['title']}.** It {spec['what']}. It takes {spec['takes']}. These are the commands it runs, "
                "in order, exactly as you'd type them:")
    st.code("\n".join("python " + " ".join(["src/strainscope/" + s[0], *s[1:]]) for s in spec["steps"]),
            language="bash")
    allowed = not ui.PUBLIC or not ui.has_database()
    if st.button("Build the database", type="primary", disabled=not allowed, key="build_db",
                 help=None if allowed else "Switched off on the shared version of the app."):
        ui.run_pipeline("database")

    full = sv.PIPELINES["everything"]
    st.markdown(f"**{full['title']}.** It {full['what']}. It takes {full['takes']}. It rewrites the result "
                "files in `artifacts/`, so Git will list them as changed, and afterwards the app compares every "
                "rebuilt number with the committed one. The same from a terminal: "
                "`python src/strainscope/pipeline.py`, then `python src/strainscope/pipeline.py compare` "
                f"({ui.doc('09-packaging.md', 'docs/09-packaging.md')}).")
    if st.button(full["title"], key="build_everything", disabled=ui.PUBLIC,
                 help="Switched off on the shared version of the app." if ui.PUBLIC else None):
        if ui.run_pipeline("everything"):
            ui.show_comparison()

# =============================================================================
with uploaded:
    st.header("Score and explain your own strains")
    st.markdown(
        "Give the app a table of your strains in the same layout as the library: one row per strain, a "
        "`strain_id`, a `kingdom` (Bacteria, Fungi, Yeast or Oomycete), gene calls (1 = carries it, 0 = doesn't, "
        "blank = not known) and compound levels (numbers, blank = not measured). The app checks the file, "
        "scores every strain with the saved model of Phase 4 and explains it with the knowledge graph of Phase 5.")
    st.markdown("**1. Get a file in the right layout.**")
    c1, c2 = st.columns(2)
    template = sv.upload_template(ui.ARTIFACTS)
    c1.download_button("Download the empty template", template.to_csv(index=False), "strainscope_template.csv",
                       "text/csv", help=f"{len(template.columns)} columns, header only.")
    if ui.has_database():
        example = sv.example_upload(ui.DB_PATH, ui.ARTIFACTS)
        c2.download_button("Download an example (12 strains)", example.to_csv(index=False),
                           "strainscope_example.csv", "text/csv",
                           help="Twelve library strains renamed EXAMPLE_01 to EXAMPLE_12. "
                                "The column copied_from says which strain each one is.")
    else:
        c2.caption("The example is copied from the library, so it needs the database (first tab).")
    st.markdown("**2. Upload it.** The app keeps your file in memory for this browser tab only. It is never "
                "written to disk, and it's gone when you close the tab.")
    file = st.file_uploader("A CSV file (comma-separated, UTF-8, up to 5 MB)", type=["csv"], key="upload_file")
    if file is not None:
        # Score a file once, not on every click: remember the result with a
        # fingerprint of the file, and only redo the work for a new file.
        fingerprint = (file.name, file.size, hash(file.getvalue()))
        if st.session_state.get("upload_fingerprint") != fingerprint:
            try:
                raw = pd.read_csv(io.BytesIO(file.getvalue()), dtype=str, keep_default_na=False,
                                  na_values=[""], encoding="utf-8-sig")
            except Exception as err:                                    # noqa: BLE001
                raw = None
                st.error(f"The file couldn't be read as CSV: {err}")
            if raw is not None:
                with st.spinner("Checking, scoring and explaining..."):
                    st.session_state["upload_result"] = sv.score_and_explain(
                        raw, G=ui.graph(), db_path=ui.DB_PATH, artifacts_dir=ui.ARTIFACTS)
                st.session_state["upload_fingerprint"] = fingerprint
        result = st.session_state.get("upload_result") if \
            st.session_state.get("upload_fingerprint") == fingerprint else None
        if result is not None:
            check = result["check"]
            st.markdown("**3. The checks.**")
            if not check.problems:
                st.success("Everything looks right.")
            for level, message in check.problems:
                {"error": st.error, "warning": st.warning, "note": st.info}[level](message)
            if check.ok:
                for note in result.get("notes", []):
                    st.caption(f"Note: {note}")
                scores = result["scores"]
                st.session_state["upload"] = {"name": file.name, **{k: result[k] for k in
                                                                    ("scores", "explanations", "graph")}}
                st.markdown(f"**4. The result.** {len(scores)} strain(s) scored, best first. "
                            "`library_rank` is where each would sit among the library's 600 "
                            "(601 means below all of them).")
                st.dataframe(scores, hide_index=True, width="stretch",
                             column_config={"probability": st.column_config.ProgressColumn(
                                 "chance of being effective", format="percent", min_value=0, max_value=1),
                                 "predicted_effective": st.column_config.CheckboxColumn("flagged"),
                                 "band": "how sure",
                                 "library_rank": "would rank in the library",
                                 "mechanism_paths": "mechanism paths", "strongest_reason": "strongest reason"})
                extra = [c for c in check.table.columns if c not in scores.columns]
                out = scores.merge(check.table[["strain_id", *extra]], on="strain_id")
                d1, d2 = st.columns(2)
                d1.download_button("Download the scores", out.to_csv(index=False), "strainscope_scores.csv", "text/csv")
                if result.get("explanations") is not None:
                    d2.download_button("Download the reasons", result["explanations"].to_csv(index=False),
                                       "strainscope_reasons.csv", "text/csv")
                if st.button("Show my strains on the Ranking and Strain pages", type="primary",
                             on_click=ui.show_source, args=("upload",)):
                    st.switch_page(ui.PAGES["ranking"])
                st.caption("A copy of a library strain gets a slightly different score from its library entry: "
                           "the library's ranking comes from models that never saw that strain (out-of-fold), "
                           "while uploads are scored by the final model, which learned from all 600.")
    if ui.upload() is not None:
        st.button(f"Forget my upload ({ui.upload()['name']})", on_click=ui.forget_upload)
    with st.expander("The same thing from a terminal"):
        st.code("python src/strainscope/service.py template my_strains.csv --example\n"
                "python src/strainscope/service.py score my_strains.csv", language="bash")
        st.caption("Writes my_strains_scored.csv and my_strains_scored_reasons.csv next to your file.")
    st.caption("The model learned from simulated strains. Treat its scores on your strains as a demonstration "
               "of the workflow, not as a prediction about real microbes. Your levels should be on the same "
               "scale as the cleaned library (Phase 2): compound levels after batch correction.")

# =============================================================================
with real:
    st.header("Real data from five public databases")
    st.markdown(
        "Real strains (BacDive), real chemistry (PubChem), pathway links (KEGG, academic use only), genome "
        "records for all four kingdoms (NCBI Datasets) and chemical classes (Metabolomics Workbench). They "
        "sit alongside the simulated library and give the knowledge graph its pathway, chemical-class and "
        f"reference-strain nodes. Details: {ui.doc('02b-real-data-ingestion.md', 'docs/02b-real-data-ingestion.md')} "
        f"and {ui.doc('02c-more-real-sources.md', 'docs/02c-more-real-sources.md')}.")
    found = ui.tables()
    found = found[found["table"].str.startswith("real_")] if len(found) else found
    if len(found):
        st.success(f"{len(found)} real tables are in the database.")
        st.dataframe(found[["table", "rows"]], hide_index=True, width="content")
    else:
        st.info("No real tables in the database yet. The app works without them.")
    if ui.PUBLIC:
        st.caption("Fetching is switched off on the shared version of the app. Run it on your own computer.")
    else:
        for name in ("probe", "real"):
            spec = sv.PIPELINES[name]
            st.markdown(f"**{spec['title']}** ({spec['takes']}): it {spec['what']}.")
            if st.button(spec["title"], key=f"run_{name}"):
                ui.run_pipeline(name)
        st.caption("An optional NCBI key goes in a `.env` file, never in the code "
                   f"({ui.doc('02c-more-real-sources.md', 'docs/02c-more-real-sources.md')}). "
                   "Fetching rewrites `artifacts/graph/` so the graph uses the real tables; commit it afterwards.")
