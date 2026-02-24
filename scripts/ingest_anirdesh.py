from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.anirdesh.com/vachanamrut/"


def slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return value or "vachanamrut-entry"


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def discover_entry_links(index_html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    links: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        url = urljoin(base_url, href)
        if "vachanamrut" not in url.lower():
            continue
        if any(x in url.lower() for x in ("contact", "about", "search", "privacy", "login")):
            continue
        links.add(url)
    return sorted(links)


def extract_entry(url: str, html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = clean_text(h1.get_text(" ", strip=True))
    if not title and soup.title:
        title = clean_text(soup.title.get_text(" ", strip=True))
    if not title:
        title = urlparse(url).path.strip("/").split("/")[-1] or "Vachanamrut"

    # Prefer long text containers to avoid menus.
    candidates = soup.find_all(["article", "main", "section", "div"])
    best_text = ""
    for c in candidates:
        text = clean_text(c.get_text(" ", strip=True))
        if len(text) > len(best_text):
            best_text = text

    if not best_text:
        best_text = clean_text(soup.get_text(" ", strip=True))

    # Trim duplicate title prefix from body.
    if best_text.lower().startswith(title.lower()):
        best_text = clean_text(best_text[len(title) :])

    content = f"Title: {title}\nSourceURL: {url}\n\n{best_text}\n"
    filename = slugify(title) + ".md"
    return filename, content


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Vachanamrut from anirdesh.com into backend_docs/")
    parser.add_argument("--index-url", default=BASE_URL)
    parser.add_argument("--output-dir", default="backend_docs/anirdesh")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit on number of entry pages")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "VachanamrutRAGIngest/1.0"})

    index_resp = session.get(args.index_url, timeout=30)
    index_resp.raise_for_status()

    links = discover_entry_links(index_resp.text, args.index_url)
    if args.limit and args.limit > 0:
        links = links[: args.limit]

    print(f"Discovered {len(links)} candidate links")

    saved = 0
    for url in links:
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            filename, content = extract_entry(url, resp.text)
            (out_dir / filename).write_text(content, encoding="utf-8")
            saved += 1
            print(f"Saved: {filename}")
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped {url}: {exc}")

    print(f"Completed. Saved {saved} files to {out_dir}")


if __name__ == "__main__":
    main()
