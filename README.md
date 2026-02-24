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

## Best way to feed Vachanamrut (RAG-friendly)
For better retrieval, store each discourse/chapter as one markdown file with metadata headers:

```md
Title: Gadhada I-01
Section: Gadhada Pratham
Number: 01
Keywords: atma, bhakti, upasana
SourceURL: https://www.anirdesh.com/vachanamrut/...

<main discourse text>
```

Recommended file naming:
- `backend_docs/gadhada-1-01.md`
- `backend_docs/gadhada-1-02.md`
- `backend_docs/loya-07.md`

## Ingest from anirdesh.com automatically
Use helper script to download and convert pages into markdown files under `backend_docs/anirdesh/`:

```bash
python scripts/ingest_anirdesh.py
```

Useful options:
```bash
# test with first 20 links
python scripts/ingest_anirdesh.py --limit 20

# custom output folder
python scripts/ingest_anirdesh.py --output-dir backend_docs/vachanamrut_site

# if site blocks some links (403), try slower requests
python scripts/ingest_anirdesh.py --delay 0.5

# if needed, pass browser cookie header for authenticated/session access
python scripts/ingest_anirdesh.py --cookie "your_cookie_string"
```

After running the script, open app and click **Refresh Source Index**.
If you still see many `format=gu` 403 skips, rerun with `--delay 0.5` and optionally `--cookie`.

The script now also:
- writes one file per Vachanamrut link
- prefixes filenames with `<lang>-vachno-XXX-...` when `vachno` query id exists
- stores `VachnoID` and `SourceURL` in file metadata
- removes common repeated site-menu boilerplate text during extraction


## Best layout for Gujarati + English together
Recommended structure:

```text
backend_docs/
  anirdesh/
    gu/
      gu-vachno-001-....md
      gu-vachno-002-....md
    en/
      en-vachno-001-....md
      en-vachno-002-....md
```

Use this command to ingest both languages into separate folders:

```bash
python scripts/ingest_anirdesh.py --formats gu,en --by-language-folder --output-dir backend_docs/anirdesh
```

For English-first run:

```bash
python scripts/ingest_anirdesh.py --formats en --by-language-folder --output-dir backend_docs/anirdesh
```

For strict one-file-per-vachno English links (`index.php?format=en&vachno=1...`):

```bash
python scripts/ingest_anirdesh.py --formats en --by-language-folder --output-dir backend_docs/anirdesh --explicit-vachno-links --vachno-start 1 --vachno-end 273
```

The app now scans `backend_docs/` recursively, so subfolders like `gu/` and `en/` are indexed automatically.

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
