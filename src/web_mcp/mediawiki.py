from __future__ import annotations

from typing import Any
from urllib.parse import ParseResult, parse_qs, unquote, urlencode, urlparse

from .errors import ClientFacingError

_WIKIMEDIA_DOMAINS = frozenset(
    {
        "mediawiki.org",
        "wikibooks.org",
        "wikidata.org",
        "wikifunctions.org",
        "wikimedia.org",
        "wikinews.org",
        "wikipedia.org",
        "wikiquote.org",
        "wikisource.org",
        "wikispecies.org",
        "wikiversity.org",
        "wikivoyage.org",
        "wiktionary.org",
    }
)
_FANDOM_DOMAIN = "fandom.com"


def resolve_mediawiki_api_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if _is_wikimedia_host(host):
        selector = _wikimedia_selector(parsed)
        api_path = "/w/api.php"
    elif _is_fandom_host(host):
        resolved = _fandom_selector_and_api_path(parsed)
        if resolved is None:
            return None
        selector, api_path = resolved
    else:
        return None
    if selector is None:
        return None
    return f"https://{host}{api_path}?{urlencode(_api_parameters(selector))}"


def extract_mediawiki_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ClientFacingError("MediaWiki API returned an invalid response object.")
    api_error = payload.get("error")
    if api_error is not None:
        raise ClientFacingError(_mediawiki_api_error_message(api_error))
    query = payload.get("query")
    if not isinstance(query, dict):
        raise ClientFacingError("MediaWiki API response is missing query results.")
    if query.get("badrevids"):
        raise ClientFacingError("MediaWiki revision was not found.")
    pages = query.get("pages")
    if not isinstance(pages, list) or len(pages) != 1:
        raise ClientFacingError("MediaWiki API did not return exactly one page.")
    page = pages[0]
    if not isinstance(page, dict):
        raise ClientFacingError("MediaWiki API returned an invalid page object.")
    if "missing" in page:
        raise ClientFacingError("MediaWiki page was not found.")
    revisions = page.get("revisions")
    if not isinstance(revisions, list) or len(revisions) != 1:
        raise ClientFacingError("MediaWiki API response is missing page revisions.")
    revision = revisions[0]
    slots = revision.get("slots") if isinstance(revision, dict) else None
    main = slots.get("main") if isinstance(slots, dict) else None
    content = main.get("content") if isinstance(main, dict) else None
    if not isinstance(content, str):
        raise ClientFacingError("MediaWiki API response is missing page content.")
    return content


def _wikimedia_selector(parsed: ParseResult) -> tuple[str, str] | None:
    query = parse_qs(parsed.query)
    if parsed.path.startswith("/wiki/"):
        title = unquote(parsed.path.removeprefix("/wiki/"))
    elif parsed.path == "/w/index.php":
        title = _first_query_value(query, "title")
    else:
        return None
    return _page_selector(query, title)


def _fandom_selector_and_api_path(
    parsed: ParseResult,
) -> tuple[tuple[str, str] | None, str] | None:
    article = _fandom_article_path(parsed.path)
    query = parse_qs(parsed.query)
    if article is not None:
        prefix, title = article
    else:
        prefix = _fandom_index_prefix(parsed.path)
        if prefix is None:
            return None
        title = _first_query_value(query, "title")
    return _page_selector(query, title), f"{prefix}/api.php"


def _fandom_article_path(path: str) -> tuple[str, str] | None:
    parts = path.split("/")
    if len(parts) >= 3 and parts[1] == "wiki":
        return "", unquote("/".join(parts[2:]))
    if len(parts) >= 4 and parts[2] == "wiki":
        return f"/{parts[1]}", unquote("/".join(parts[3:]))
    return None


def _fandom_index_prefix(path: str) -> str | None:
    parts = path.split("/")
    if parts in [["", "index.php"], ["", "w", "index.php"]]:
        return ""
    if len(parts) == 3 and parts[2] == "index.php":
        return f"/{parts[1]}"
    return None


def _page_selector(
    query: dict[str, list[str]], title: str | None
) -> tuple[str, str] | None:
    oldid = _first_query_value(query, "oldid")
    if oldid:
        return "revids", oldid
    curid = _first_query_value(query, "curid")
    if curid:
        return "pageids", curid
    if title:
        return "titles", title
    return None


def _api_parameters(selector: tuple[str, str]) -> list[tuple[str, str]]:
    parameters = [
        ("action", "query"),
        ("prop", "revisions"),
        ("rvprop", "content"),
        ("rvslots", "main"),
        selector,
    ]
    if selector[0] == "titles":
        parameters.append(("redirects", "1"))
    parameters.extend([("format", "json"), ("formatversion", "2")])
    return parameters


def _is_wikimedia_host(host: str) -> bool:
    return any(_is_domain_or_subdomain(host, domain) for domain in _WIKIMEDIA_DOMAINS)


def _is_fandom_host(host: str) -> bool:
    return host != f"www.{_FANDOM_DOMAIN}" and host.endswith(f".{_FANDOM_DOMAIN}")


def _is_domain_or_subdomain(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _first_query_value(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    return values[0] if values else None


def _mediawiki_api_error_message(api_error: Any) -> str:
    if isinstance(api_error, dict) and isinstance(api_error.get("code"), str):
        return f"MediaWiki API rejected the page request ({api_error['code']})."
    return "MediaWiki API rejected the page request."
