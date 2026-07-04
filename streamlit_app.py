from __future__ import annotations

from app.errors import GeminiQueryError, KnowledgeBaseNotReadyError
from app.schemas import AnswerLanguage, AskResponse
from app.services.chat_service import answer_question

LANGUAGE_LABELS = {
    AnswerLanguage.AUTO: "Auto",
    AnswerLanguage.ENGLISH: "English",
    AnswerLanguage.VIETNAMESE: "Vietnamese",
}


def main() -> None:
    import streamlit as st

    st.set_page_config(
        page_title="OptiSigns Docs Assistant",
        page_icon="O",
        layout="centered",
    )

    st.title("OptiSigns Docs Assistant")

    with st.form("ask_form"):
        question = st.text_area(
            "Question",
            height=120,
            placeholder="How do I add a YouTube video to OptiSigns?",
        )
        language = st.selectbox(
            "Language",
            options=list(AnswerLanguage),
            format_func=lambda value: LANGUAGE_LABELS[value],
        )
        submitted = st.form_submit_button("Ask")

    if not submitted:
        return

    cleaned_question = question.strip()
    if not cleaned_question:
        st.warning("Enter a question before asking.")
        return

    with st.spinner("Searching the uploaded documentation..."):
        try:
            response = answer_question(cleaned_question, language)
        except KnowledgeBaseNotReadyError as exc:
            st.error(str(exc))
            return
        except GeminiQueryError as exc:
            st.error(str(exc))
            return

    _render_answer(st, response)


def _render_answer(st: object, response: AskResponse) -> None:
    if response.status == "not_found":
        st.warning(response.answer)
    else:
        st.markdown(response.answer)

    if not response.sources:
        return

    st.markdown("#### Sources")
    for source in response.sources:
        st.markdown(f"- [{source.title}]({source.url})")


if __name__ == "__main__":
    main()
