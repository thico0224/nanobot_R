"""
Academic search tool for nanobot: arXiv + Semantic Scholar + OpenAlex

- arXiv: official Atom API, no key
- Semantic Scholar: official API, no key required for basic usage
- OpenAlex: official API, no key

Returns JSON string with normalized fields.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any, Literal
from urllib.parse import quote_plus

import httpx

from nanobot.agent.tools.base import Tool


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


class AcademicSearchTool(Tool):
    name = "academic_search"
    description = (
        "Unified research paper search across arXiv, Semantic Scholar, and OpenAlex. "
        "Returns normalized paper metadata with URLs/DOI when available."
    )

    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keywords"},
            "source": {
                "type": "string",
                "enum": ["research", "semantic_scholar", "openalex", "auto"],
                "default": "auto",
                "description": "Data source: auto prefers arXiv for newest, then Semantic Scholar/OpenAlex for metadata",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "default": 8,
                "description": "Number of results (1-20)",
            },
            "year_from": {
                "type": "integer",
                "minimum": 1900,
                "maximum": 2100,
                "description": "Optional filter: only keep papers >= this year (best-effort by source)",
            },
        },
        "required": ["query"],
    }

    def __init__(self, semantic_scholar_api_key: str | None = None, timeout_s: float = 20.0):
        # API key optional; leave empty for most use-cases
        self.s2_key = semantic_scholar_api_key
        self.timeout_s = timeout_s

    async def execute(
        self,
        query: str,
        source: Literal["research", "semantic_scholar", "openalex", "auto"] = "auto",
        max_results: int = 8,
        year_from: int | None = None,
        **kwargs: Any,
    ) -> str:
        query = _clean(query)
        if not query:
            return json.dumps({"error": "query is empty"})

        max_results = max(1, min(int(max_results), 20))

        if source == "auto":
            # default: freshest first
            # 1) arXiv for newest preprints
            # 2) Semantic Scholar for structured metadata / citations (best effort)
            # 3) OpenAlex for broad coverage
            # We'll return a merged list with a 'source' field.
            results: list[dict[str, Any]] = []
            results.extend(await self._arxiv(query, max_results=max_results))
            # Fill remaining slots with S2 then OpenAlex
            remain = max_results - len(results)
            if remain > 0:
                results.extend(await self._semantic_scholar(query, max_results=remain))
                remain = max_results - len(results)
            if remain > 0:
                results.extend(await self._openalex(query, max_results=remain))

            results = self._filter_year(results, year_from)
            return json.dumps({"query": query, "source": "auto", "count": len(results), "results": results}, ensure_ascii=False)

        if source == "research":
            results = await self._arxiv(query, max_results=max_results)
        elif source == "semantic_scholar":
            results = await self._semantic_scholar(query, max_results=max_results)
        elif source == "openalex":
            results = await self._openalex(query, max_results=max_results)
        else:
            return json.dumps({"error": f"unknown source: {source}"})

        results = self._filter_year(results, year_from)
        return json.dumps({"query": query, "source": source, "count": len(results), "results": results}, ensure_ascii=False)

    def _filter_year(self, results: list[dict[str, Any]], year_from: int | None) -> list[dict[str, Any]]:
        if not year_from:
            return results
        out = []
        for r in results:
            y = r.get("year")
            try:
                if y is not None and int(y) >= int(year_from):
                    out.append(r)
            except Exception:
                # if year missing or non-int, keep it out (strict)
                pass
        return out

    async def _arxiv(self, query: str, max_results: int) -> list[dict[str, Any]]:
        # Atom API
        url = (
            "http://export.arxiv.org/api/query"
            f"?search_query=all:{quote_plus(query)}"
            f"&start=0&max_results={max_results}"
            "&sortBy=submittedDate&sortOrder=descending"
        )
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.get(url)
            r.raise_for_status()

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(r.text)
        entries = root.findall("atom:entry", ns)

        out: list[dict[str, Any]] = []
        for e in entries:
            title = _clean(e.findtext("atom:title", default="", namespaces=ns))
            summary = _clean(e.findtext("atom:summary", default="", namespaces=ns))
            published = (e.findtext("atom:published", default="", namespaces=ns) or "")[:10]
            year = None
            if published[:4].isdigit():
                year = int(published[:4])

            authors = []
            for a in e.findall("atom:author", ns):
                authors.append(_clean(a.findtext("atom:name", default="", namespaces=ns)))

            abs_url = None
            pdf_url = None
            for link in e.findall("atom:link", ns):
                rel = link.get("rel")
                href = link.get("href")
                if rel == "alternate":
                    abs_url = href
                elif rel == "related":
                    pdf_url = href

            arxiv_id = _clean(e.findtext("atom:id", default="", namespaces=ns))

            out.append(
                {
                    "source": "research",
                    "title": title,
                    "authors": [a for a in authors if a],
                    "year": year,
                    "published": published,
                    "abstract": summary,
                    "url": abs_url or arxiv_id,
                    "pdf_url": pdf_url,
                    "doi": None,
                    "venue": None,
                    "citations": None,
                }
            )
        return out

    async def _semantic_scholar(self, query: str, max_results: int) -> list[dict[str, Any]]:
        # Official API: /graph/v1/paper/search
        # Docs fields: title, year, authors, venue, url, externalIds (DOI), citationCount, abstract
        base = "https://api.semanticscholar.org/graph/v1/paper/search"
        fields = "title,year,authors,venue,url,externalIds,citationCount,abstract"

        headers = {}
        if self.s2_key:
            headers["x-api-key"] = self.s2_key

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.get(
                base,
                params={"query": query, "limit": max_results, "fields": fields},
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()

        out: list[dict[str, Any]] = []
        for item in data.get("data", [])[:max_results]:
            authors = [a.get("name") for a in (item.get("authors") or []) if a.get("name")]
            doi = None
            ext = item.get("externalIds") or {}
            doi = ext.get("DOI") or ext.get("doi")

            out.append(
                {
                    "source": "semantic_scholar",
                    "title": item.get("title"),
                    "authors": authors,
                    "year": item.get("year"),
                    "published": None,
                    "abstract": item.get("abstract"),
                    "url": item.get("url"),
                    "pdf_url": None,
                    "doi": doi,
                    "venue": item.get("venue"),
                    "citations": item.get("citationCount"),
                }
            )
        return out

    async def _openalex(self, query: str, max_results: int) -> list[dict[str, Any]]:
        # OpenAlex works endpoint
        base = "https://api.openalex.org/works"
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.get(
                base,
                params={
                    "search": query,
                    "per_page": max_results,
                    "sort": "cited_by_count:desc",
                },
                headers={"User-Agent": "nanobot-research-search/1.0"},
            )
            r.raise_for_status()
            data = r.json()

        out: list[dict[str, Any]] = []
        for w in (data.get("results") or [])[:max_results]:
            title = w.get("title")
            year = w.get("publication_year")

            authorships = w.get("authorships") or []
            authors = []
            for a in authorships:
                au = (a.get("author") or {}).get("display_name")
                if au:
                    authors.append(au)

            doi = w.get("doi")
            if isinstance(doi, str) and doi.startswith("https://doi.org/"):
                doi = doi.replace("https://doi.org/", "")

            url = w.get("id")  # OpenAlex work id URL
            landing = w.get("primary_location", {}) or {}
            primary_url = (landing.get("source") or {}).get("host_organization_lineage")
            # OpenAlex doesn't always provide a direct landing page; keep id URL as reference.

            out.append(
                {
                    "source": "openalex",
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "published": None,
                    "abstract": None,  # OpenAlex abstracts are inverted index; keep None in MVP
                    "url": url,
                    "pdf_url": None,
                    "doi": doi,
                    "venue": (landing.get("source") or {}).get("display_name"),
                    "citations": w.get("cited_by_count"),
                }
            )
        return out
