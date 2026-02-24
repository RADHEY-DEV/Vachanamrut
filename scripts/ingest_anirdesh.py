from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.anirdesh.com/vachanamrut/"
SUPPORTED_FORMATS = ["gu", "en"]
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

BOILERPLATE_FRAGMENTS = [
    "menu text_decrease text_increase",
    "show side by side",
    "show shravan audio",
    "share ॥ શ્રી સ્વામિનારાયણો વિજયતે ॥",
    "ગુ | en",
    "en | tr",
    "ગુ | tr",
    "પ્રસંગ / prasangs",
    "નિરૂપણ / nirupan",
]


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
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        # Prefer true entry links.
        if "vachno" not in query and "vachanamrut/index.php" not in parsed.path:
            continue
        if any(x in url.lower() for x in ("contact", "about", "search", "privacy", "login")):
            continue
        links.add(url)
    return sorted(links)


def _build_variant_urls(url: str, preferred_formats: list[str] | None = None) -> list[str]:
    """Return URL variants to bypass format-specific 403 pages."""
    parsed = urlparse(url)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    variants: list[str] = []

    def build(query_dict: dict[str, str]) -> str:
        return urlunparse(parsed._replace(query=urlencode(query_dict)))

    variants.append(url)
    formats = preferred_formats or SUPPORTED_FORMATS
    if "format" in query_items:
        for fmt in formats + ["eg", "hg"]:
            q = dict(query_items)
            q["format"] = fmt
            variants.append(build(q))
        q = dict(query_items)
        q.pop("format", None)
        variants.append(build(q))

    deduped: list[str] = []
    seen: set[str] = set()
    for item in variants:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _fetch_with_fallback(session: requests.Session, url: str, timeout: int, delay_s: float, preferred_formats: list[str] | None = None) -> tuple[str, str]:
    last_error: Exception | None = None
    for candidate in _build_variant_urls(url, preferred_formats=preferred_formats):
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




def _detect_language_from_url(url: str) -> str:
    query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
    fmt = query.get("format", "").strip().lower()
    return fmt if fmt in SUPPORTED_FORMATS else "unknown"

def _extract_vachno_id(url: str) -> str:
    query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
    raw = query.get("vachno", "").strip()
    return raw if raw.isdigit() else ""


def _extract_title(soup: BeautifulSoup, fallback_url: str) -> str:
    selectors = [
        "h1",
        ".page-title",
        ".entry-title",
        "title",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            title = clean_text(node.get_text(" ", strip=True))
            if title:
                return title

    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        return clean_text(str(og["content"]))

    parsed = urlparse(fallback_url)
    return parsed.path.strip("/").split("/")[-1] or "Vachanamrut"


def _clean_body_text(text: str, title: str) -> str:
    cleaned = clean_text(text)
    lower = cleaned.lower()
    for fragment in BOILERPLATE_FRAGMENTS:
        pattern = re.compile(re.escape(fragment), re.IGNORECASE)
        cleaned = pattern.sub(" ", cleaned)
    cleaned = clean_text(cleaned)

    if cleaned.lower().startswith(title.lower()):
        cleaned = clean_text(cleaned[len(title) :])

    # Remove excessive UI separator artifacts.
    cleaned = re.sub(r"\b(ગુ|en|हिं|tr)\s*\|\s*(ગુ|en|हिं|tr)\b", " ", cleaned, flags=re.IGNORECASE)
    return clean_text(cleaned)


def extract_entry(url: str, html: str, language: str = "unknown") -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "form"]):
        tag.decompose()

    title = _extract_title(soup, url)

    # Prefer known content containers first.
    candidates = []
    for selector in ("article", "main", "#content", ".content", ".post-content", ".entry-content"):
        candidates.extend(soup.select(selector))
    if not candidates:
        candidates = soup.find_all(["article", "main", "section", "div"])

    best_text = ""
    for c in candidates:
        text = _clean_body_text(c.get_text(" ", strip=True), title)
        if len(text) > len(best_text):
            best_text = text

    if not best_text:
        best_text = _clean_body_text(soup.get_text(" ", strip=True), title)

    vachno_id = _extract_vachno_id(url)
    meta_id = f"{int(vachno_id):03d}" if vachno_id else ""
    if meta_id and meta_id not in title:
        title = f"{title} (Vachno {meta_id})"

    content = f"Title: {title}\nLanguage: {language}\nVachnoID: {meta_id or 'N/A'}\nSourceURL: {url}\n\n{best_text}\n"

    lang_prefix = language if language in SUPPORTED_FORMATS else "xx"
    if meta_id:
        filename = f"{lang_prefix}-vachno-{meta_id}-{slugify(title)}.md"
    else:
        filename = f"{lang_prefix}-{slugify(title)}.md"
    return filename, content


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Vachanamrut from anirdesh.com into backend_docs/")
    parser.add_argument("--index-url", default=BASE_URL)
    parser.add_argument("--output-dir", default="backend_docs/anirdesh")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit on number of entry pages")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    parser.add_argument("--delay", type=float, default=0.15, help="Delay between page requests in seconds")
    parser.add_argument("--cookie", default="", help="Optional cookie header value copied from browser session")
    parser.add_argument("--formats", default="gu,en", help="Comma-separated format priority, e.g. gu,en or en")
    parser.add_argument("--by-language-folder", action="store_true", help="Store files under output_dir/<language>/")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    format_priority = [x.strip().lower() for x in args.formats.split(",") if x.strip()]
    format_priority = [x for x in format_priority if x in SUPPORTED_FORMATS]
    if not format_priority:
        format_priority = SUPPORTED_FORMATS.copy()

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
            final_url, html = _fetch_with_fallback(
                session, url, timeout=args.timeout, delay_s=args.delay, preferred_formats=format_priority
            )
            language = _detect_language_from_url(final_url)
            filename, content = extract_entry(final_url, html, language=language)
            target_dir = out_dir / language if args.by_language_folder else out_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / filename).write_text(content, encoding="utf-8")
            saved += 1
            print(f"Saved: {filename}")
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped {url}: {exc}")

    print(f"Completed. Saved {saved} files to {out_dir}")


if __name__ == "__main__":
    main()
