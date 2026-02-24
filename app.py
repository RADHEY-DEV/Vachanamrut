from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path

import streamlit as st

from rag_engine import PDFRAG, RetrievalResult


# --- Configure here ---
PDF_FOLDER = Path("backend_pdfs")
OPENAI_API_KEY_IN_CODE = ""  # Paste your OpenAI API key here if you want to keep it in code.
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_FALLBACK_MODELS = ["gpt-4o-mini", "gpt-4.1-mini"]
OPENAI_REQUEST_TIMEOUT_SECONDS = 45
# ----------------------

OPENAI_AVAILABLE = importlib.util.find_spec("openai") is not None

st.set_page_config(page_title="Vachanamrut RAG Assistant", page_icon="📖", layout="wide")
st.title("📖 Vachanamrut Chat Assistant")
st.caption("Auto-loads PDFs from backend folder and answers in a chat-like flow.")

if "rag" not in st.session_state:
    st.session_state.rag = PDFRAG()
if "ready" not in st.session_state:
    st.session_state.ready = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "loaded_files" not in st.session_state:
    st.session_state.loaded_files = []
if "last_openai_error" not in st.session_state:
    st.session_state.last_openai_error = ""


def _resolve_api_key() -> str | None:
    if OPENAI_API_KEY_IN_CODE.strip():
        return OPENAI_API_KEY_IN_CODE.strip()
    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    return env_key if env_key else None


def _scan_pdf_folder() -> list[str]:
    if not PDF_FOLDER.exists():
        return []
    return sorted(str(path) for path in PDF_FOLDER.glob("*.pdf") if path.is_file())


def _ingest_from_backend_folder() -> None:
    pdf_paths = _scan_pdf_folder()
    if not pdf_paths:
        st.session_state.ready = False
        st.session_state.loaded_files = []
        return

    chunk_count = st.session_state.rag.ingest_pdfs(pdf_paths)
    st.session_state.ready = True
    st.session_state.loaded_files = [Path(p).name for p in pdf_paths]
    st.session_state.chunk_count = chunk_count


def _build_prompt(question: str, retrieved: list[RetrievalResult]) -> list[dict[str, str]]:
    context = "\n\n".join(f"[Score: {item.score:.3f}] {item.chunk}" for item in retrieved)
    prompt = (
        "You are a helpful assistant that answers questions only from provided Vachanamrut context. "
        "If the context does not contain the answer, clearly say you don't know.\n\n"
        f"Question: {question}\n\n"
        f"Context:\n{context}\n\n"
        "Answer in concise, respectful language."
    )
    return [
        {"role": "system", "content": "Ground every answer in provided context."},
        {"role": "user", "content": prompt},
    ]


def _generate_with_openai(question: str, retrieved: list[RetrievalResult], api_key: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=OPENAI_REQUEST_TIMEOUT_SECONDS)
    messages = _build_prompt(question, retrieved)

    models_to_try: list[str] = [OPENAI_MODEL] + [m for m in OPENAI_FALLBACK_MODELS if m != OPENAI_MODEL]
    errors: list[str] = []

    for model_name in models_to_try:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.2,
            )
            st.session_state.last_openai_error = ""
            content = response.choices[0].message.content or "No response from model."
            return content
        except Exception as error:  # noqa: BLE001
            errors.append(f"{model_name}: {error}")

    full_error = " | ".join(errors)
    st.session_state.last_openai_error = full_error
    raise RuntimeError(full_error)


def _animated_assistant_text(text: str) -> None:
    placeholder = st.empty()
    words = text.split()
    visible = []
    for word in words:
        visible.append(word)
        placeholder.markdown(" ".join(visible))
        time.sleep(0.015)


def _test_openai_connection(api_key: str) -> str:
    try:
        test_retrieved = [RetrievalResult(chunk="This is a small context test.", score=1.0)]
        _ = _generate_with_openai("Reply with word: OK", test_retrieved, api_key)
        return "OpenAI test passed. API key and model access look valid."
    except Exception as error:  # noqa: BLE001
        return f"OpenAI test failed: {error}"


with st.sidebar:
    st.subheader("Backend PDF Source")
    st.write(f"Folder: `{PDF_FOLDER}`")
    st.write("Put your Vachanamrut PDF files in this folder and click refresh.")

    if st.button("Refresh PDF Index", type="primary"):
        with st.spinner("Scanning and indexing backend PDFs..."):
            try:
                _ingest_from_backend_folder()
                if st.session_state.ready:
                    st.success(
                        f"Indexed {st.session_state.chunk_count} chunks from {len(st.session_state.loaded_files)} file(s)."
                    )
                else:
                    st.warning("No PDF files found in backend folder.")
            except Exception as error:  # noqa: BLE001
                st.session_state.ready = False
                st.error(f"Failed to index PDFs: {error}")

    st.markdown("---")
    st.subheader("LLM Setup")
    st.write("OpenAI key is read from code constant first, then `OPENAI_API_KEY` env var.")

    resolved_key = _resolve_api_key()
    if OPENAI_API_KEY_IN_CODE.strip():
        st.success("Using API key from code constant.")
    elif resolved_key:
        st.info("Using API key from environment variable.")
    else:
        st.warning("No API key detected. Extractive mode will be used.")

    if not OPENAI_AVAILABLE:
        st.info("Install `openai` package to enable LLM mode: `pip install openai`.")

    if OPENAI_AVAILABLE and resolved_key:
        if st.button("Test OpenAI Connection"):
            with st.spinner("Testing OpenAI API call..."):
                st.info(_test_openai_connection(resolved_key))

    if st.session_state.last_openai_error:
        st.error(f"Last OpenAI error: {st.session_state.last_openai_error}")

    st.markdown("---")
    st.subheader("Loaded PDFs")
    if st.session_state.loaded_files:
        for file_name in st.session_state.loaded_files:
            st.write(f"• {file_name}")
    else:
        st.write("No PDFs indexed yet.")

if not st.session_state.ready:
    with st.spinner("Auto-indexing backend PDFs..."):
        try:
            _ingest_from_backend_folder()
        except Exception as error:  # noqa: BLE001
            st.session_state.ready = False
            st.error(f"Auto-index failed: {error}")

if not st.session_state.ready:
    st.warning("No indexed PDFs available. Add PDF files to `backend_pdfs/` and click **Refresh PDF Index**.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask about Vachanamrut...")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        if not st.session_state.ready:
            reply = "I cannot answer yet because no backend PDFs are indexed. Add PDFs to backend_pdfs and refresh index."
            _animated_assistant_text(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
        else:
            retrieved = st.session_state.rag.retrieve(question, top_k=5)
            api_key = _resolve_api_key()
            if OPENAI_AVAILABLE and api_key:
                try:
                    answer = _generate_with_openai(question, retrieved, api_key)
                except Exception:
                    answer = (
                        "OpenAI response failed, so I switched to extractive mode. "
                        "Check sidebar for detailed OpenAI error.\n\n"
                        + st.session_state.rag.answer_without_llm(question, retrieved)
                    )
            else:
                answer = st.session_state.rag.answer_without_llm(question, retrieved)

            _animated_assistant_text(answer)

            with st.expander("Retrieved Context"):
                if not retrieved:
                    st.info("No relevant chunks found.")
                for idx, item in enumerate(retrieved, start=1):
                    st.markdown(f"**Chunk {idx} (score {item.score:.3f})**")
                    st.write(item.chunk)

            st.session_state.messages.append({"role": "assistant", "content": answer})
