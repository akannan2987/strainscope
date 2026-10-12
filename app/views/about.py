"""app/views/about.py: About this copy (Phase 7), the health page. Which
version this is, whether it runs on someone's own computer or as a shared
copy, what each part of the app can read, whether the AI features use a
language model (and how much of today's cap is used), what may leave this
copy, and the versions of the main packages. Useful to a visitor of the
online copy, and to its owner when something looks wrong."""
import platform
import sys
from importlib import metadata

import streamlit as st

import ui
from strainscope import llm
from strainscope import service as sv

st.title("About this copy")
info = sv.release_info()
version = f"v{info['version']}" + (" with the changes listed under [Unreleased]" if info["unreleased"] else "")
mode = ("a **shared copy**: other people can use it, so the real-data buttons are hidden, the database was built "
        "on its first start and can't be rebuilt from here, and the AI features have a daily cap"
        if ui.PUBLIC else "a **local copy** on your own computer, with every button available")
st.markdown(f"StrainScope **{version}** (released {info['date']}: *{info['title']}*). This is {mode}. "
            f"Source, guides and every step: [{ui.REPO.removeprefix('https://')}]({ui.REPO}).")
ui.simulated_note()

# -- health ------------------------------------------------------------------
st.subheader("What the app can read")
mark = {True: ":green[✓]", False: ":red[✗]", None: ":gray[·]"}
checks = ui.status()
for c in checks:
    st.markdown(f"{mark[c.ok]} **{c.name}**: {c.detail}")
    if c.fix and c.ok is not True:
        st.caption(("For the owner: " if ui.PUBLIC else "To add: " if c.ok is None else "To fix: ") + f"`{c.fix}`")
if all(c.ok is not False for c in checks):
    st.success("Everything the pages need is here.", icon=":material/check_circle:")
st.caption("The same check from a terminal: `python src/strainscope/service.py status`")

# -- the AI features -------------------------------------------------------------
st.subheader("The AI features")
cfg = llm.settings()
on = "on" if cfg.on else "off"
st.markdown(
    f"| Feature | Without a model | With a model ({on} here) |\n|---|---|---|\n"
    "| Ask StrainScope | the passages that answer, word for word, with links | a short answer citing them |\n"
    "| Ask the data | a tested recipe from the Query Cookbook, run read-only | a new query when no recipe fits, "
    "checked by five guards |\n"
    "| Ask the graph | numbered facts from walks through the graph, with sources | a short answer citing them |\n"
    "| In plain words (Strain and Ranking pages) | written by rules from the results | the same: no model is used |")
st.markdown(f"**Language model:** {cfg.describe()}.")
if cfg.on:
    st.caption(llm.daily_cap().describe() + ". The count starts again at midnight (UTC) and after a restart.")

with st.expander("How to switch a language model on or off"):
    st.markdown(
        "Everything in StrainScope works without one. With one, Ask StrainScope and Ask the graph also write a "
        "short answer that cites what they found, and Ask the data writes a new query when no recipe fits.\n\n"
        "- **On your own computer, with Ollama (free, nothing leaves the computer):** install Ollama, run "
        "`ollama pull llama3.2:3b`, add the line `STRAINSCOPE_ASK_BACKEND=local` to `.env`, and restart the app.\n"
        "- **With a hosted provider (at home, or for an online copy):** set `STRAINSCOPE_ASK_BACKEND=hosted` "
        "and the provider's address, model name and key (`STRAINSCOPE_ASK_URL`, `STRAINSCOPE_ASK_MODEL`, "
        "`STRAINSCOPE_ASK_KEY`) in `.env`, or for an online copy in the host's Secrets box; then restart or "
        "reboot the app.\n"
        "- **To check that it cites its sources:** `python src/strainscope/service.py check-model` asks it four "
        "questions the way the app does and says how many written answers would be shown.\n"
        "- **To switch it off:** set `STRAINSCOPE_ASK_BACKEND=none` (or remove the lines) and restart.\n\n"
        f"Every step, with what you should see and what to do when something goes wrong: "
        f"{ui.doc('LANGUAGE_MODEL.md', 'docs/LANGUAGE_MODEL.md')}.")

with st.expander("What may leave this copy, and what never does"):
    st.markdown(
        "Only when a language model is switched on, and only to that model:\n\n"
        "- **Ask StrainScope:** your question and up to three documentation passages.\n"
        "- **Ask the data:** your question, the database's table and column names, a few notes on what the "
        "columns hold and three tested recipes as examples. **Never a row of data.**\n"
        "- **Ask the graph:** your question and the numbered facts, which come from the domain model, public "
        "references and the published findings of Phases 3 and 4. Questions about a strain never reach a model.\n\n"
        "A request for a written answer (Ask StrainScope, Ask the graph) also carries StrainScope's fixed rules "
        "for the model, with one made-up example of a cited answer (about a pump), so the model sees what a "
        "citation looks like.\n\n"
        "Never sent: the database's rows, your uploaded strains (this copy keeps them in memory for your "
        "browser tab only and never writes them to disk) and usage statistics (switched off in "
        "`.streamlit/config.toml`). A hosted key goes only in each request's header, where the provider "
        "expects it, never in the text the model reads. "
        f"The full rules: {ui.doc('08-deployment-ai.md', 'docs/08-deployment-ai.md')}, section 1.")

# -- versions -----------------------------------------------------------------------
with st.expander("Versions of the main packages"):
    rows = [{"package": "Python", "version": platform.python_version()}]
    for name in ("streamlit", "pandas", "numpy", "scikit-learn", "duckdb", "networkx", "plotly"):
        try:
            rows.append({"package": name, "version": metadata.version(name)})
        except metadata.PackageNotFoundError:
            rows.append({"package": name, "version": "not installed"})
    st.dataframe(rows, hide_index=True, width="content")
    card = ui.card()
    if card:
        built = card.get("versions", {}).get("scikit-learn")
        st.caption(f"The saved model was built with scikit-learn {built}. The online copy installs "
                   "app/requirements.txt, which pins the same version.")
    st.caption(f"Running on {platform.system()} with {sys.implementation.name}.")
