"""CUI (Romanian fiscal code) helpers shared by the company-centric scrapers."""

import logging

import httpx

from connectors.common.http import HttpClient, describe_error

log = logging.getLogger(__name__)

DEMOANAF_API = "https://demoanaf.ro/api"


class CuiLookupUnavailable(Exception):
    """The company-name -> CUI service did not answer (it is a third-party,
    paid service; ANAF itself only looks companies up by CUI)."""


def parse_cui(target: str) -> str | None:
    """"RO123" / " 123 " -> "123"; anything that is not a CUI -> None."""
    cui = target.upper().replace("RO", "").strip()
    return cui if cui.isdigit() else None


def resolve_cui(http: HttpClient, target: str) -> str | None:
    """The CUI itself if `target` is one, else the best company-name match.

    Returns None when no company matches; raises `CuiLookupUnavailable` when
    the name lookup itself is down, so callers can say so instead of reporting
    "nothing found".
    """
    cui = parse_cui(target)
    if cui:
        return cui

    # Imported here: the index module needs settings, this module is imported everywhere.
    from connectors.onrc.index import get_index

    index = get_index()
    if index is not None:
        firms = [firm for firm in index.search_firms(target, 1) if firm.cui]
        if firms:
            log.info("resolved %r to CUI %s (%s) in the ONRC index", target, firms[0].cui, firms[0].name)
            return firms[0].cui

    try:
        results = http.get(f"{DEMOANAF_API}/search", params={"q": target}).json()
    except (httpx.HTTPError, ValueError) as exc:
        log.info("CUI lookup for %r failed: %s", target, exc)
        raise CuiLookupUnavailable(
            f"company-name lookup unavailable: {describe_error(exc)}; search by CUI, "
            "or build the ONRC index (`just onrc-import`)"
        ) from exc

    companies = results.get("data", results) if isinstance(results, dict) else results
    if isinstance(companies, list) and companies:
        first = companies[0]
        cui = str(first.get("cui") or first.get("CUI") or "")
        if cui:
            log.info("resolved %r to CUI %s", target, cui)
            return cui

    return None
