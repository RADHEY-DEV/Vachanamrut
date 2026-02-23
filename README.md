# Vachanamrut RAG Web App

A Retrieval-Augmented Generation (RAG) chat app that answers questions from Vachanamrut PDFs.

## What changed
- PDFs are auto-read from a backend folder: `backend_pdfs/`
- Chat-style interface with animated assistant response text
- OpenAI key can be set directly in code (`OPENAI_API_KEY_IN_CODE`) or via environment variable

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## How to use
1. Put your PDF files into `backend_pdfs/`.
2. Open the app and click **Refresh PDF Index** in sidebar.
3. Ask questions in the chat box.
4. To enable OpenAI answers, set either:
   - `OPENAI_API_KEY_IN_CODE` in `app.py`, or
   - `OPENAI_API_KEY` environment variable.

## API key location in code
Inside `app.py`:
```python
OPENAI_API_KEY_IN_CODE = ""
```
Paste your API key there if you explicitly want it in code.

## Troubleshooting
- `ModuleNotFoundError: No module named 'pypdf'`
  ```bash
  pip install -r requirements.txt
  ```
- `ModuleNotFoundError: No module named 'openai'`
  ```bash
  pip install openai
  ```
- If dependencies were mixed globally before, recreate clean venv and reinstall.
