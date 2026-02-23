# Vachanamrut RAG Web App

A simple Retrieval-Augmented Generation (RAG) web app that answers questions from uploaded **Vachanamrut PDF** files.

## Features
- Upload one or more PDF files.
- Build a local TF-IDF index over text chunks.
- Retrieve the most relevant chunks for each question.
- Generate answers in two modes:
  - **LLM mode** (if `OPENAI_API_KEY` is set) using `gpt-4o-mini`.
  - **Extractive mode** (no API key needed), selecting the most relevant sentences from retrieved chunks.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Usage
1. Upload Vachanamrut PDFs from the sidebar.
2. Click **Process PDFs**.
3. Ask a question and click **Get Answer**.
4. Optionally enable OpenAI mode if `OPENAI_API_KEY` is configured.

## Notes
- The quality depends on PDF text extraction quality.
- For scanned PDFs, run OCR first for best results.


## Troubleshooting
- If you get `ModuleNotFoundError: No module named 'pypdf'` (or `numpy` / `scikit-learn`), install dependencies in your active environment:
  ```bash
  pip install -r requirements.txt
  ```
- If you get `ModuleNotFoundError: No module named 'openai'`, install dependencies in your active environment:
  ```bash
  pip install -r requirements.txt
  ```
  Or install only OpenAI package:
  ```bash
  pip install openai
  ```
- If traceback still points to `from openai import OpenAI` at top of `app.py`, you are likely running an older file. Pull latest changes and restart Streamlit.
- The app works in extractive mode even without the OpenAI package/API key.
