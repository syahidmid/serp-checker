"""
scraper_with_markdownify.py — Scrape a URL and return clean Markdown + status info.

Flow:
  1. urltomarkdown API (headless browser — handles JS-rendered pages)
  2. Fallback: requests + BeautifulSoup (fast, lightweight — for when urltomarkdown fails)
  3. Normalize headings (setext → ATX)
  4. Return dict with status_code, label, markdown, error
"""

import re
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# Tags to remove before converting
_NOISE_TAGS = [
    "nav", "footer", "header", "aside",
    "script", "style", "noscript",
    "iframe", "form", "button",
]

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Human-friendly status messages
_STATUS_LABELS = {
    200: "✅ 200 OK — Content retrieved successfully",
    301: "↪️ 301 Moved Permanently — Page has been permanently moved",
    302: "↪️ 302 Found — Page is temporarily redirected",
    400: "❌ 400 Bad Request — Invalid URL or malformed request",
    401: "🔒 401 Unauthorized — Page requires authentication",
    403: "🚫 403 Forbidden — Website blocks scraper access",
    404: "❌ 404 Not Found — Page not found",
    410: "❌ 410 Gone — Page has been permanently removed",
    429: "⚠️ 429 Too Many Requests — Too many requests, please try again later",
    500: "❌ 500 Internal Server Error — Website server encountered an error",
    502: "❌ 502 Bad Gateway — Website server gateway error",
    503: "❌ 503 Service Unavailable — Website is down or under maintenance",
    504: "⏱️ 504 Gateway Timeout — Website server did not respond in time",
}


def _status_label(code: int) -> str:
    if code in _STATUS_LABELS:
        return _STATUS_LABELS[code]
    if 200 <= code < 300:
        return f"✅ {code} OK"
    if 300 <= code < 400:
        return f"↪️ {code} Redirect"
    if 400 <= code < 500:
        return f"❌ {code} Client Error"
    if 500 <= code < 600:
        return f"❌ {code} Server Error"
    return f"❓ {code} — Unknown status"


def _normalize_headings(markdown: str) -> str:
    """
    Convert setext-style headings to ATX-style.

    Some scrapers (e.g. urltomarkdown) produce setext format:

        **Some Title**        Some Title
        ==============   or   ----------

    This converts them to:

        # Some Title     or   ## Some Title

    Also strips bold markers (**/__) and backslash escapes from heading text,
    so "**2\\. Extra Life 18+**" becomes "## 2. Extra Life 18+".
    """
    lines = markdown.split("\n")
    result = []
    i = 0
    while i < len(lines):
        current  = lines[i]
        next_line = lines[i + 1] if i + 1 < len(lines) else ""

        # Setext H1: next line is all '=' (at least 1)
        if next_line and re.match(r'^=+\s*$', next_line) and current.strip():
            heading_text = re.sub(r'\*\*|__', '', current).strip()
            heading_text = re.sub(r'\\(.)', r'\1', heading_text)
            result.append(f"# {heading_text}")
            i += 2
            continue

        # Setext H2: next line is all '-' (at least 2, to avoid HR confusion)
        if next_line and re.match(r'^-{2,}\s*$', next_line) and current.strip():
            heading_text = re.sub(r'\*\*|__', '', current).strip()
            heading_text = re.sub(r'\\(.)', r'\1', heading_text)
            result.append(f"## {heading_text}")
            i += 2
            continue

        result.append(current)
        i += 1

    return "\n".join(result)


def _html_to_markdown(html: str) -> str:
    """Parse HTML, strip noise tags, convert to clean ATX Markdown."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    content = (
        soup.find("main")
        or soup.find("article")
        or soup.find("body")
        or soup
    )

    markdown = md(
        str(content),
        heading_style="ATX",
        bullets="-",
        strip=["a", "img"],
    )

    # Normalize any remaining setext headings (e.g. from urltomarkdown fallback)
    markdown = _normalize_headings(markdown)

    # Clean up excessive blank lines
    lines = markdown.splitlines()
    cleaned_lines = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        cleaned_lines.append(line)
        prev_blank = is_blank

    return "\n".join(cleaned_lines).strip()


def _scrape_with_requests(url: str, timeout: int = 10) -> dict:
    """
    Primary scraping method using requests.
    Fast and lightweight — used for most sites.
    """
    try:
        response = requests.get(url, headers=_DEFAULT_HEADERS, timeout=timeout)
        response.encoding = response.apparent_encoding
        response.raise_for_status()

        return {
            "status_code":  response.status_code,
            "status_ok":    True,
            "status_label": _status_label(response.status_code),
            "html":         response.text,
            "error":        None,
        }

    except requests.exceptions.Timeout:
        return {
            "status_code":  None,
            "status_ok":    False,
            "status_label": "⏱️ Timeout — Site took too long to respond",
            "html":         "",
            "error":        "Request timed out",
        }

    except requests.exceptions.ConnectionError as e:
        return {
            "status_code":  None,
            "status_ok":    False,
            "status_label": "🔌 Connection Error — Could not connect to site",
            "html":         "",
            "error":        str(e),
        }

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else None
        return {
            "status_code":  code,
            "status_ok":    False,
            "status_label": _status_label(code) if code else "❌ HTTP Error",
            "html":         "",
            "error":        str(e),
        }

    except requests.exceptions.RequestException as e:
        return {
            "status_code":  None,
            "status_ok":    False,
            "status_label": "❌ Request Error",
            "html":         "",
            "error":        str(e),
        }


_URLTOMARKDOWN_API = "https://urltomarkdown.herokuapp.com/"


def _scrape_with_urltomarkdown(url: str, timeout: int = 15) -> dict:
    """
    Primary scraping via urltomarkdown hosted API (headless browser).
    Handles JS-rendered pages that requests+BS cannot.
    Returns already-converted Markdown — normalized before returning.
    """
    try:
        from urllib.parse import quote
        api_url  = f"{_URLTOMARKDOWN_API}?url={quote(url, safe='')}"
        response = requests.get(api_url, timeout=timeout)
        response.raise_for_status()

        markdown = response.text.strip()
        if not markdown:
            return {
                "status_code":  None,
                "status_ok":    False,
                "status_label": "❌ urltomarkdown returned empty content",
                "markdown":     "",
                "error":        "Empty response from urltomarkdown",
            }

        # Normalize setext headings from urltomarkdown output
        markdown = _normalize_headings(markdown)

        return {
            "status_code":  200,
            "status_ok":    True,
            "source":       "urltomarkdown",
            "status_label": "✅ 200 OK — Content retrieved via urltomarkdown (primary)",
            "markdown":     markdown,
            "error":        None,
        }

    except requests.exceptions.Timeout:
        return {
            "status_code":  None,
            "status_ok":    False,
            "status_label": "⏱️ Timeout — urltomarkdown took too long to respond",
            "markdown":     "",
            "error":        "urltomarkdown request timed out",
        }

    except Exception as e:
        return {
            "status_code":  None,
            "status_ok":    False,
            "status_label": "❌ urltomarkdown failed",
            "markdown":     "",
            "error":        str(e),
        }


def scrape_to_markdown(url: str, timeout: int = 10) -> dict:
    """
    Fetch a URL and return its main content as Markdown plus status info.

    Strategy:
      1. urltomarkdown API (headless browser — handles JS-rendered pages)
      2. Fallback: requests + BeautifulSoup (if urltomarkdown fails or returns empty)

    Headings are always normalized to ATX style (##) before returning,
    regardless of which scraping method was used.

    Args:
        url:     Target URL to scrape.
        timeout: Request timeout in seconds.

    Returns:
        dict with keys:
            status_code  (int | None)
            status_ok    (bool)
            status_label (str)   — human-friendly message
            markdown     (str)   — cleaned Markdown content with ATX headings
            source       (str)   — "urltomarkdown" or "beautifulsoup"
            error        (str | None)
    """
    # ── Step 1: Try urltomarkdown (headless, handles JS-rendered pages) ───────
    result = _scrape_with_urltomarkdown(url, timeout=15)
    if result["status_ok"] and result.get("markdown", "").strip():
        return result

    # ── Step 2: Fallback to requests + BeautifulSoup ──────────────────────────
    fetch = _scrape_with_requests(url, timeout)

    if not fetch["status_ok"]:
        return {
            "status_code":  fetch["status_code"],
            "status_ok":    False,
            "source":       "beautifulsoup",
            "status_label": fetch["status_label"],
            "markdown":     "",
            "error":        fetch["error"],
        }

    # ── Step 3: Convert HTML → Markdown (includes normalization) ─────────────
    clean_markdown = _html_to_markdown(fetch["html"])

    return {
        "status_code":  fetch["status_code"],
        "status_ok":    True,
        "source":       "beautifulsoup",
        "status_label": fetch["status_label"] + " (BeautifulSoup fallback)",
        "markdown":     clean_markdown,
        "error":        None,
    }