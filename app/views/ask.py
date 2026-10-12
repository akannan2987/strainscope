"""app/views/ask.py: Ask StrainScope (Phase 6b). A question about the project,
answered from its own documents (the guides, the Handbook, the glossary, the
roadmaps and the code's docstrings), each passage quoted word for word with a
link to where it sits. A question the documents don't cover is refused rather
than guessed. The engine is src/strainscope/ask.py; the guide is
docs/07b-docs-assistant.md."""
import streamlit as st

import ui
from strainscope import ask as docs

BOX = {docs.ANSWERED: st.success, docs.CLOSEST: st.warning, docs.REFUSED: st.info, docs.VAGUE: st.info}
ICON = {docs.ANSWERED: ":material/check_circle:", docs.CLOSEST: ":material/help:",
        docs.REFUSED: ":material/block:", docs.VAGUE: ":material/edit:"}


def show(text: str, file: str) -> None:
    """A passage with its links working and its pictures shown."""
    for kind, value in docs.pieces(docs.display_text(text, pictures=True), file):
        if kind == "picture":
            st.image(value, width=760)
        else:
            st.markdown(docs.absolute_links(value, file))


def _set_question(text: str) -> None:
    """Button callback: put a question in the box. Callbacks run before the
    page reruns, which is when Streamlit allows changing a widget's value."""
    st.session_state["ask_question"] = text


st.title("Ask StrainScope")
st.markdown("Questions about the project, answered from its own documents: the guides, the Handbook, the "
            "glossary, the roadmaps and the code's docstrings. Each answer is a passage **quoted word for "
            "word**, with a link to the place it comes from. A question the documents don't cover is refused "
            "instead of guessed.")

index = docs.get_index()
settings = docs.writer_settings()
question = st.text_input("Your question", key="ask_question", placeholder="e.g. What is a balanced error rate?",
                         help="Press Enter to ask. Plain words work best: what you want to do, or the term "
                              "you want explained.")
write = None
if settings.backend != "none":
    write = None if st.toggle(f"Also write a short answer ({settings.model})", value=True, key="ask_write",
                              help="A language model writes a few sentences from the passages found, and "
                                   "must cite them. Only the question and those passages are sent.") else False

if not question.strip():
    st.markdown("**Try one of these:**")
    cols = st.columns(2)
    for n, q in enumerate(docs.STARTERS):
        cols[n % 2].button(q, key=f"starter_{n}", on_click=_set_question, args=(q,), width="stretch")
else:
    with st.spinner("Searching the documents..."):
        answer = docs.ask(question, index, write=write)
    BOX[answer.verdict](answer.message, icon=ICON[answer.verdict])

    if answer.written:
        with st.container(border=True):
            st.markdown(f"**Written answer** · {answer.written_by}")
            st.markdown(answer.written)
            st.caption("Written by a language model from the numbered passages below, which it had to cite. "
                       "Check it against them.")
    elif answer.note:
        st.caption(f"No written answer: {answer.note}")

    for n, hit in enumerate(answer.hits, start=1):
        s = hit.section
        with st.container(border=True):
            st.markdown(f"**[{n}] [{s.heading}]({s.url})**  \n:gray[{s.where} · match {hit.score:.2f}]")
            show(hit.passage, s.file)
            if s.text.strip() != hit.passage.strip():
                with st.expander("The whole section"):
                    show(s.text, s.file)

    if answer.related:
        st.markdown("**You might also ask about:**")
        cols = st.columns(len(answer.related))
        for col, s in zip(cols, answer.related):
            col.button(s.heading, key=f"related_{s.link}_{s.heading}", on_click=_set_question, args=(s.heading,),
                       help=f"from {s.file}", width="stretch")
    ui.suggest_fix("Ask StrainScope", question, answer.verdict, [f"{h.section.heading} ({h.section.link})"
                                                                for h in answer.hits])

st.divider()
st.caption(f"{len(index.sections):,} sections from {len({s.file for s in index.sections})} files. Written answers: "
           f"{ui.model_note(settings).removeprefix('Language model: ')}. "
           f"How it works: {ui.doc('07b-docs-assistant.md', 'docs/07b-docs-assistant.md')}. "
           "The same from a terminal: `python src/strainscope/ask.py \"your question\"`.")
