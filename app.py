from __future__ import annotations

import os
import tempfile
from typing import List

import streamlit as st

try:
    from openai import OpenAI
except ModuleNotFoundError:
    OpenAI = None

from rag_engine import PDFRAG, RetrievalResult


st.set_page_config(page_title="Vachanamrut RAG Assistant", page_icon="📖", layout="wide")

st.title("📖 Vachanamrut RAG Web App")
st.caption("Upload Vachanamrut PDF files and ask questions grounded in the uploaded text.")

if "rag" not in st.session_state:
    st.session_state.rag = PDFRAG()
if "ready" not in st.session_state:
    st.session_state.ready = False


def _save_uploads_temp(uploaded_files) -> List[str]:
    paths: list[str] = []
    for file in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file.read())
            paths.append(tmp.name)
    return paths


def _generate_with_openai(question: str, retrieved: List[RetrievalResult]) -> str:
    if OpenAI is None:
        raise ModuleNotFoundError(
            "The 'openai' package is not installed. Install it with `pip install openai` to enable LLM mode."
        )

    context = "\n\n".join(f"[Score: {item.score:.3f}] {item.chunk}" for item in retrieved)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = (
        "You are a helpful assistant that answers questions only from provided Vachanamrut context. "
        "If the context does not contain the answer, clearly say you don't know.\n\n"
        f"Question: {question}\n\n"
        f"Context:\n{context}\n\n"
        "Answer in concise, respectful language."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ground every answer in provided context."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or "No response from model."


with st.sidebar:
    st.subheader("1) Upload PDFs")
    uploads = st.file_uploader(
        "Upload one or more Vachanamrut PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if st.button("Process PDFs", type="primary"):
        if not uploads:
            st.warning("Please upload at least one PDF first.")
        else:
            with st.spinner("Reading and indexing PDFs..."):
                paths = _save_uploads_temp(uploads)
                try:
                    chunk_count = st.session_state.rag.ingest_pdfs(paths)
                    st.session_state.ready = True
                    st.success(f"Ready! Indexed {chunk_count} chunks.")
                except Exception as error:  # noqa: BLE001
                    st.session_state.ready = False
                    st.error(f"Failed to process PDFs: {error}")
                finally:
                    for path in paths:
                        try:
                            os.unlink(path)
                        except OSError:
                            pass

    st.markdown("---")
    st.subheader("2) Optional LLM")
    st.write("Set `OPENAI_API_KEY` to generate fluent answers with an LLM.")
    st.write("Without API key, the app returns extractive answers from retrieved chunks.")
    if OpenAI is None:
        st.info("Install `openai` package to enable LLM mode: `pip install openai`.")

question = st.text_input("Ask a question about Vachanamrut", placeholder="What does Vachanamrut say about true satsang?")

col1, col2 = st.columns([1, 1])
with col1:
    top_k = st.slider("Retrieved chunks", min_value=2, max_value=10, value=5)
with col2:
    use_llm = st.checkbox("Use OpenAI (if API key set)", value=True)

if st.button("Get Answer"):
    if not st.session_state.ready:
        st.error("Please upload and process PDFs first.")
    elif not question.strip():
        st.warning("Please enter a question.")
    else:
        retrieved = st.session_state.rag.retrieve(question, top_k=top_k)

        st.subheader("Answer")
        if use_llm and os.getenv("OPENAI_API_KEY") and OpenAI is not None:
            try:
                answer = _generate_with_openai(question, retrieved)
            except Exception as error:  # noqa: BLE001
                st.warning(f"LLM call failed, using extractive answer instead: {error}")
                answer = st.session_state.rag.answer_without_llm(question, retrieved)
        elif use_llm and OpenAI is None:
            st.warning("OpenAI mode requested, but `openai` package is not installed. Using extractive answer.")
            answer = st.session_state.rag.answer_without_llm(question, retrieved)
        else:
            answer = st.session_state.rag.answer_without_llm(question, retrieved)

        st.write(answer)

        st.subheader("Retrieved Context")
        if not retrieved:
            st.info("No relevant chunks found.")
        for idx, item in enumerate(retrieved, start=1):
            with st.expander(f"Chunk {idx} (score {item.score:.3f})"):
                st.write(item.chunk)
