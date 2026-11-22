"""Bounded public-web search and page retrieval for Aria."""

from __future__ import annotations

import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, urlsplit

import httpx

TOOL_NAME = "web_search"
TOOL_DESCRIPTION = (
    "Search the public web with DuckDuckGo or retrieve a public HTTP(S) page. "
    "Use for current external information; cite returned URLs. Never send secrets in queries."
)
TOOL_ENABLED = True
TOOL_APPROVAL_REQUIRED = False
TOOL_TIMEOUT_SECONDS = 12
MAX_BYTES = 1_000_000
MAX_TEXT = 8_000


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden += 1
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


class _Results(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs)
        if tag == "a" and "result__a" in (attrs.get("class") or "").split():
            href = attrs.get("href") or ""
            target = parse_qs(urlsplit(href).query).get("uddg", [href])[0]
            self.current = {"url": target, "title": ""}

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current["title"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current is not None:
            self.items.append(self.current)
            self.current = None


def _validate_public_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTP(S) URLs without credentials are allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Local and private network URLs are not allowed.")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(
                    host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM
                )
            ]
        except OSError:
            raise ValueError("Could not resolve public host.") from None
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Local and private network URLs are not allowed.")
    return url


def _get(url: str) -> tuple[str, str, bytes]:
    url = _validate_public_url(url)
    with httpx.Client(timeout=8, follow_redirects=False, trust_env=False, headers={"User-Agent": "AriaAssistant/1.0"}) as client:
        with client.stream("GET", url) as response:
            if response.is_redirect:
                raise ValueError("Redirects are not followed; inspect the returned URL before retrying.")
            response.raise_for_status()
            if int(response.headers.get("content-length", "0") or 0) > MAX_BYTES:
                raise ValueError("Page exceeds the 1 MB limit.")
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise ValueError("Page exceeds the 1 MB limit.")
            return str(response.url), response.headers.get("content-type", ""), bytes(body)


def run(query: str = "", url: str = "", limit: int = 5) -> str:
    """Search DuckDuckGo with query, or fetch a public page by URL."""
    if url:
        final_url, content_type, body = _get(url)
        if not any(kind in content_type.lower() for kind in ("text/html", "text/plain", "application/xhtml")):
            raise ValueError("Only HTML and plain-text pages can be read.")
        parser = _Text()
        parser.feed(body.decode("utf-8", errors="replace"))
        text = " ".join(" ".join(parser.parts).split())[:MAX_TEXT]
        return f"URL: {final_url}\n{text}"
    if not query.strip():
        return "Provide a search query or a URL."
    _, _, body = _get("https://html.duckduckgo.com/html/?q=" + quote_plus(query[:400]))
    parser = _Results()
    parser.feed(body.decode("utf-8", errors="replace"))
    matches = parser.items[:max(1, min(limit, 8))]
    return "\n".join(f"{item['title'].strip()} — {item['url']}" for item in matches) or "No results found."
