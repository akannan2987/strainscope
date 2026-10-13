"""app/views/workflow.py: the whole workflow on data of your choice (Phase 9).
Choose a dataset or start a new one (your own three tables, or a fresh
simulated library), run every phase on it with a live log, see what each step
found, and explore the results on every other page of the app. The engine is
src/strainscope/datasets.py with the plans in src/strainscope/service.py; the
guide is docs/10-workflow-and-your-data.md."""
import io
import zipfile

import streamlit as st

import ui
from strainscope import datasets as ds
from strainscope import paths
from strainscope import service as sv

LIMITS = ds.LIMITS["shared" if ui.PUBLIC else "local"]
BADGE = {"done": ":green-badge[done]", "stale": ":orange-badge[run again: what it reads has changed]",
         "to do": ":gray-badge[to do]"}

st.title("Workflow")
st.markdown(
    "Run every phase of StrainScope on data of your choice: your own genes, compounds and trial results, or a "
    "fresh simulated library. Each dataset gets a folder of its own, so the built-in library is never changed. "
    "When the steps are done, every page of the app shows the new results (choose the dataset in the sidebar). "
    f"Explained step by step in {ui.doc('10-workflow-and-your-data.md', 'docs/10-workflow-and-your-data.md')}.")
picture = ui.ROOT / "docs" / "img" / "workflow_steps.png"
if picture.exists():
    ui.picture(str(picture), "The workflow in five steps: your three tables are checked, cleaned into a "
                             "database, read together, used to train and test a model, and linked in a "
                             "knowledge graph, which every page of the app then shows.", width=900)
if ui.PUBLIC:
    st.caption(f"On this shared copy a dataset holds up to {LIMITS['strains']:,} strains, {LIMITS['genes']} genes "
               f"and {LIMITS['compounds']} compounds, uses quick settings, and is deleted an hour after you last "
               "use it. Only this browser tab can see it, and nothing in it is sent anywhere.")


def _switch() -> None:
    ui.choose_dataset(st.session_state["workflow_dataset"])


def _run_from(step: int) -> None:
    """A run button was pressed (a callback, so the run can start at the top
    of section 2, under the buttons, whichever button it was)."""
    st.session_state["run_from"] = step


def _saved(name: str) -> None:
    """After saving: choose the new dataset and empty the upload form."""
    for key in ("check", "check_fingerprint"):
        st.session_state.pop(key, None)
    st.session_state["form_round"] = st.session_state.get("form_round", 0) + 1   # new keys = empty boxes
    ui.choose_dataset(name)
    st.session_state["workflow_note"] = f"Saved as dataset {name}. Run its steps below."


def _show_checks(check: ds.DatasetCheck) -> None:
    """Errors one by one (each needs fixing), warnings and notes as two lists."""
    for message in check.errors:
        st.error(message, icon=":material/error:")
    for level, show, icon in (("warning", st.warning, ":material/warning:"), ("note", st.info, ":material/info:")):
        found = [m for lv, m in check.problems if lv == level]
        if found:
            show("\n".join(f"- {m}" for m in found), icon=icon)


# =============================================================================
st.header("1. Choose the data")
names = ui.dataset_names()
st.session_state["workflow_dataset"] = ui.dataset() or ui.LIBRARY
st.selectbox("Dataset", [ui.LIBRARY, *names], key="workflow_dataset", on_change=_switch, format_func=ui.label,
             help="The same choice as the box in the sidebar: every page shows this dataset.")

with st.expander("Start a new dataset", expanded=not names, icon=":material/add_circle:"):
    n = st.session_state.get("form_round", 0)      # goes up after each save, which empties the form
    own, sim = st.tabs(["Your own data (three CSV files)", "A fresh simulated library"])

    with own:
        st.markdown(
            "Three tables, one row per strain, the same layout as the library's raw files:\n"
            "- **Genes** (`genomics.csv`): `strain_id`, then a column per gene with 1 (carries it), 0 (doesn't) "
            "or empty (not known).\n"
            "- **Compounds** (`metabolomics.csv`): `strain_id`, then a column per compound with the level the lab "
            "measured (empty = not measured).\n"
            "- **Trial results** (`phenotype.csv`): `strain_id`, `kingdom` (Bacteria, Fungi, Yeast or Oomycete), "
            "`suppression_score` (% of disease suppressed), and if you have them `is_effective`, `genus`, "
            "`batch_id`, `collection_site`, `isolation_date`.\n\n"
            "Any gene and compound names work. Names StrainScope knows (ituA, iturin, ...) bring their mechanism "
            "into the knowledge graph.")
        st.markdown("**Get the layout.** Empty templates to fill in, or an example of 120 simulated strains "
                    "(messy on purpose, like real tables) to try it with:")
        for kind, tables, word in (("template", ds.templates(), "Empty template"),
                                   ("example", ds.example(), "Example")):
            cols = st.columns([1, 2, 2, 2], vertical_alignment="center")
            cols[0].markdown(word)
            for j, t in enumerate(ds.TABLES):
                cols[j + 1].download_button(f"{t}.csv", tables[t].to_csv(index=False),
                                            f"{t}.csv" if kind == "template" else f"example_{t}.csv",
                                            "text/csv", key=f"get_{kind}_{t}", width="stretch",
                                            icon=":material/download:")
        st.markdown("**Upload the three files.** They're checked before anything is saved.")
        u1, u2, u3 = st.columns(3)
        files = {"genomics": u1.file_uploader("Genes (genomics.csv)", type=["csv"], key=f"up_genomics_{n}"),
                 "metabolomics": u2.file_uploader("Compounds (metabolomics.csv)", type=["csv"],
                                                  key=f"up_metabolomics_{n}"),
                 "phenotype": u3.file_uploader("Trial results (phenotype.csv)", type=["csv"], key=f"up_phenotype_{n}")}
        s1, s2, s3 = st.columns(3)
        effective_at = s1.number_input("Effective from (% suppressed)", 1.0, 100.0, ds.EFFECTIVE_AT, 1.0,
                                       format="%.0f", key="up_effective",
                                       help="Used when the trial results have no is_effective column: a strain "
                                            "counts as effective when its suppression_score reaches this line. "
                                            "The library uses 65.")
        if ui.PUBLIC:
            name = None
            quick = s3.toggle("Quick settings", value=True, disabled=True, key="up_quick",
                              help=f"{ds.QUICK_REPEATS} cross-validation repeats instead of 10: always on here.")
        else:
            name = s2.text_input("Name for the dataset", key=f"up_name_{n}", placeholder="e.g. trial_2026",
                                 help="Letters, digits and _, starting with a letter.")
            quick = s3.toggle("Quick settings", value=False, key="up_quick",
                              help=f"{ds.QUICK_REPEATS} cross-validation repeats instead of 10: the model step runs two to "
                                   "three times faster, with rougher error bars.")
        if all(files.values()):
            fingerprint = tuple((f.name, f.size, hash(f.getvalue())) for f in files.values()) + (effective_at,)
            too_big = [f.name for f in files.values() if f.size > LIMITS["megabytes"] * 1024 * 1024]
            if too_big:
                st.error(f"{', '.join(too_big)}: larger than {LIMITS['megabytes']} MB.")
            elif st.session_state.get("check_fingerprint") != fingerprint:
                tables, problems = {}, []
                for t, f in files.items():
                    table, problem = ds.read_table(f.getvalue(), f.name)
                    tables[t] = table
                    if problem:
                        problems.append(problem)
                if problems:
                    st.session_state["check"] = ds.DatasetCheck(False, [("error", p) for p in problems])
                else:
                    with st.spinner("Checking every cell..."):
                        st.session_state["check"] = ds.check_tables(
                            tables["genomics"], tables["metabolomics"], tables["phenotype"],
                            effective_at=effective_at, shared=ui.PUBLIC)
                st.session_state["check_fingerprint"] = fingerprint
            check = st.session_state.get("check") if st.session_state.get("check_fingerprint") == fingerprint else None
            if check is not None:
                st.markdown("**The checks.**")
                _show_checks(check)
                if check.ok:
                    s = check.summary
                    st.success(f"Ready: {s['strains']:,} strains ({s['effective']} effective), {s['genes']} genes, "
                               f"{s['compounds']} compounds. StrainScope knows "
                               f"{len(s['known_genes']) + len(s['known_compounds'])} of these names.")
                    problem = None if ui.PUBLIC else ds.check_name(name or "")
                    if problem and name:
                        st.caption(problem)
                    if st.button("Save it as a dataset and choose it", type="primary", key="save_own",
                                 disabled=bool(problem)):
                        new = ds.temporary_name() if ui.PUBLIC else name
                        ds.create(new, check.tables, "yours", "three CSV files: " + ", ".join(
                            f.name for f in files.values()), effective_at, quick,
                            notes=[m for level, m in check.problems if level != "error"],
                            temporary=ui.PUBLIC, owner=ui.owner())
                        _saved(new)
                        st.rerun()
        else:
            st.caption("Waiting for all three files.")

    with sim:
        st.markdown(
            "A new library from the same generator as the built-in one (Phase 1), with your seed and size. The "
            "answer key comes with it, so every result can be graded, as for the library. Seed 42 with 600 "
            "strains gives the library's own data, and the same results.")
        c1, c2, c3 = st.columns(3)
        seed = c1.number_input("Seed", 0, 1_000_000, 7, 1, key="sim_seed",
                               help="The number that fixes every random draw: same seed, same data.")
        strains = c2.slider("Strains", 100, LIMITS["strains"], min(300, LIMITS["strains"]), 50, key="sim_strains")
        sim_quick = c3.toggle("Quick settings", value=ui.PUBLIC, disabled=ui.PUBLIC, key="sim_quick",
                              help=f"{ds.QUICK_REPEATS} cross-validation repeats instead of 10.")
        sim_name = None if ui.PUBLIC else st.text_input("Name for the dataset", key=f"sim_name_{n}",
                                                         placeholder="e.g. seed7_300")
        problem = None if ui.PUBLIC else ds.check_name(sim_name or "")
        if problem and sim_name:
            st.caption(problem)
        if st.button("Save it as a dataset and choose it", type="primary", key="save_sim", disabled=bool(problem)):
            new = ds.temporary_name() if ui.PUBLIC else sim_name
            ds.create(new, kind="simulated", seed=int(seed), strains=int(strains), quick=sim_quick or ui.PUBLIC,
                      temporary=ui.PUBLIC, owner=ui.owner())
            _saved(new)
            st.rerun()

# =============================================================================
st.header("2. Run the phases")
if "workflow_note" in st.session_state:
    st.success(st.session_state.pop("workflow_note"))
current = ui.dataset()
if current is None:
    st.info("The built-in library's results are committed to the repository, and every page already reads them. "
            "To run the phases yourself, start a dataset above: a simulated library with seed 42 and 600 strains "
            "reproduces the library."
            + ("" if ui.PUBLIC else " On your own computer you can also rebuild the library itself on the "
                                    "**Data** page."))
    st.stop()

info = ui.info()
plan = sv.plan_for(current)
spec = sv.PIPELINES[plan]
steps = ds.progress(current)
done = sum(s.state == "done" for s in steps)
st.markdown(f"**{ui.label(current)}** · {info.get('source', '')}"
            + (" · quick settings" if info.get("quick") else ""))
st.progress(done / len(steps), text=f"{done} of {len(steps)} steps done")
from strainscope.integrate import find_rscript  # noqa: E402  (only this page needs it)
if find_rscript() is None:
    st.caption("R isn't installed here, so step 'Read genes and chemistry together' runs the Python methods "
               "and leaves out DIABLO (docs/04-integration.md explains both).")

first_open = next((s.number for s in steps if s.state != "done"), None)
b1, b2 = st.columns(2)
b1.button("Run every step", type="primary", key="run_all", width="stretch", icon=":material/play_arrow:",
          on_click=_run_from, args=(1,))
b2.button(f"Run the steps still to do (from step {first_open})" if first_open else "Every step is done",
          key="run_rest", disabled=first_open is None, width="stretch", on_click=_run_from, args=(first_open,))
st.caption(f"A full run takes {spec['takes']} (on a laptop; a shared copy can be slower). The log shows each "
           "step as it works, and the page updates when it ends.")
start = st.session_state.pop("run_from", None)
if start is not None:                    # the run and its live log, right under the buttons
    if ui.run_pipeline(plan, dataset=current, start=start):
        st.session_state["workflow_note"] = "Every step finished. The results are below and on every page."
        st.rerun()
for s in steps:
    with st.container(border=True):
        top = st.columns([4, 1])
        took = f" · last run took {s.seconds:.0f} s" if s.seconds else ""
        top[0].markdown(f"**{s.number}. {s.name}** {BADGE[s.state]}")
        top[0].caption(f"`{s.command}`{took}")
        top[1].button("Run from here", key=f"run_from_{s.number}", width="stretch", on_click=_run_from,
                      args=(s.number,))
        if s.facts:
            st.markdown("\n".join(f"- {line}" for line in s.facts))

# =============================================================================
st.header("3. Explore the results")
if done < len(steps):
    st.caption("The pages fill in as the steps finish. Run every step to see them all.")
else:
    st.markdown("Every page of the app now shows this dataset:")
    links = [("ranking", "Ranking", ":material/format_list_numbered:"),
             ("strain", "Strain page", ":material/coronavirus:"), ("graph", "Knowledge graph", ":material/hub:"),
             ("integration", "Integration", ":material/join_inner:"), ("sql", "SQL console", ":material/terminal:"),
             ("ask_data", "Ask the data", ":material/table_chart:"),
             ("ask_graph", "Ask the graph", ":material/account_tree:")]
    cols = st.columns(4)
    for i, (key, title, icon) in enumerate(links):
        cols[i % 4].page_link(ui.PAGES[key], label=title, icon=icon)

f = paths.folders(current)
files = [p for p in sorted(f.artifacts.rglob("*")) if p.is_file() and p.suffix in (".csv", ".json")]
files += [p for p in sorted(f.processed.glob("*.csv"))] + [p for p in sorted(f.raw.glob("*.csv"))]
if files:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.relative_to(f.home).as_posix())
        z.writestr("dataset.json", (f.home / paths.INFO_FILE).read_text(encoding="utf-8"))
    st.download_button(f"Download every table of {current} (zip, {len(files)} files)", buffer.getvalue(),
                       f"strainscope_{current}.zip", "application/zip", key="download_all",
                       help="The raw and clean tables, the cleaning ledger and every result table. The saved model "
                            "is left out: a model file can run code when loaded, so share models you built yourself.")

with st.expander("Delete this dataset"):
    st.markdown(f"Deletes `{paths.rel(f.home)}/` with everything in it. The library and other datasets stay.")
    sure = st.checkbox(f"Yes, delete {current}", key="delete_sure")
    if st.button("Delete it", disabled=not sure, key="delete_dataset"):
        ds.remove(f.home)
        ui.choose_dataset(None)
        st.session_state.pop("delete_sure", None)
        st.session_state["workflow_note"] = f"Deleted {current}."
        st.rerun()

with st.expander("The same from a terminal"):
    st.code(f"python src/strainscope/datasets.py show {current}        # every step and what it found\n"
            f"python src/strainscope/pipeline.py --dataset {current}    # run every step\n"
            f"python src/strainscope/datasets.py remove {current}      # delete it", language="bash")
    st.caption("A new dataset from three files in a folder: `python src/strainscope/datasets.py new NAME --from "
               "FOLDER`; a simulated one: `python src/strainscope/datasets.py new NAME --simulate --seed 7`.")
