# Vachanamrut RAG Web App

A Retrieval-Augmented Generation (RAG) chat app that answers questions from Vachanamrut source files.

## What changed
- Sources are auto-read from a backend folder: `backend_docs/`
- Supports `.txt`, `.md`, and `.pdf` sources (text files are recommended for best reliability)
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
1. Put your source files into `backend_docs/`.
2. Preferred: add plain `.txt` or `.md` text files.
3. PDF is also supported if `pypdf` is installed.
4. Open the app and click **Refresh Source Index** in sidebar.
5. Ask questions in the chat box.
6. To enable OpenAI answers, set either:
   - `OPENAI_API_KEY_IN_CODE` in `app.py`, or
   - `OPENAI_API_KEY` environment variable.
7. Use sidebar **Test OpenAI Connection** to verify key/model access.

## API key location in code
Inside `app.py`:
```python
OPENAI_API_KEY_IN_CODE = ""
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_FALLBACK_MODELS = ["gpt-4o-mini", "gpt-4.1-mini"]
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
- If you get `Client.__init__() got an unexpected keyword argument 'proxies'`, fix HTTP client mismatch:
  ```bash
  pip install "httpx<0.28" --upgrade
  ```
  or reinstall all dependencies:
  ```bash
  pip install -r requirements.txt --upgrade
  ```

- If OpenAI fails, check sidebar for **Last OpenAI error** details and use **Test OpenAI Connection**.
