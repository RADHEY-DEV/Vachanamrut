from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.anirdesh.com/vachanamrut/"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,gu;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


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


def _build_variant_urls(url: str) -> list[str]:
    """Return URL variants to bypass format-specific 403 pages."""
    parsed = urlparse(url)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    variants: list[str] = []

    def build(query_dict: dict[str, str]) -> str:
        return urlunparse(parsed._replace(query=urlencode(query_dict)))

    variants.append(url)
    if "format" in query_items:
        # Try alternate formats and no format.
        for fmt in ("gu", "en", "eg", "hg"):
            q = dict(query_items)
            q["format"] = fmt
            variants.append(build(q))
        q = dict(query_items)
        q.pop("format", None)
        variants.append(build(q))

    # Keep unique order.
    deduped: list[str] = []
    seen: set[str] = set()
    for item in variants:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _fetch_with_fallback(session: requests.Session, url: str, timeout: int, delay_s: float) -> tuple[str, str]:
    last_error: Exception | None = None
    for candidate in _build_variant_urls(url):
        try:
            resp = session.get(candidate, timeout=timeout)
            resp.raise_for_status()
            if delay_s > 0:
                time.sleep(delay_s)
            return candidate, resp.text
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    assert last_error is not None
    raise last_error


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

    candidates = soup.find_all(["article", "main", "section", "div"])
    best_text = ""
    for c in candidates:
        text = clean_text(c.get_text(" ", strip=True))
        if len(text) > len(best_text):
            best_text = text

    if not best_text:
        best_text = clean_text(soup.get_text(" ", strip=True))

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
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    parser.add_argument("--delay", type=float, default=0.15, help="Delay between page requests in seconds")
    parser.add_argument("--cookie", default="", help="Optional cookie header value copied from browser session")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if args.cookie.strip():
        session.headers["Cookie"] = args.cookie.strip()

    index_resp = session.get(args.index_url, timeout=args.timeout)
    index_resp.raise_for_status()

    links = discover_entry_links(index_resp.text, args.index_url)
    if args.limit and args.limit > 0:
        links = links[: args.limit]

    print(f"Discovered {len(links)} candidate links")

    saved = 0
    for url in links:
        try:
            final_url, html = _fetch_with_fallback(session, url, timeout=args.timeout, delay_s=args.delay)
            filename, content = extract_entry(final_url, html)
            (out_dir / filename).write_text(content, encoding="utf-8")
            saved += 1
            print(f"Saved: {filename}")
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped {url}: {exc}")

    print(f"Completed. Saved {saved} files to {out_dir}")


if __name__ == "__main__":
    main()
