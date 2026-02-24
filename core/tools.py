"""
ReAct Tool 노드용 LangChain @tool 정의.

scripts/fetchers.py(수집·ingest 전용)와 역할이 다르며,
여기서는 에이전트가 런타임에 호출하는 실시간 검색 도구만 정의한다.
"""

import logging
import os

import requests
import wikipediaapi
from dotenv import load_dotenv
from langchain_core.tools import tool
from tavily import TavilyClient

load_dotenv()

logger = logging.getLogger(__name__)

_WIKI_USER_AGENT = "CineMate/1.0 (educational project)"
_TMDB_BASE_URL = "https://api.themoviedb.org/3"
_TMDB_API_KEY = os.getenv("TMDB_API_KEY") or ""
_TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN") or ""
_TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") or ""

_wiki = wikipediaapi.Wikipedia(language="en", user_agent=_WIKI_USER_AGENT)


@tool
def wikipedia_search(query: str) -> str:
    """Search Wikipedia for background information about a movie, character, or topic.

    Use this tool when you need factual background, production details, or plot summaries
    that are not time-sensitive.

    Args:
        query: Search term or movie title (e.g., "Avengers Endgame film")

    Returns:
        Wikipedia page summary and key sections, or a not-found message.
    """
    page = _wiki.page(query)
    if not page.exists():
        logger.warning("Wikipedia page not found: %s", query)
        return f"Wikipedia page not found for: {query}"

    sections_text: list[str] = [f"Wikipedia: {page.title}", page.summary[:2000]]
    target_sections = {"Plot", "Synopsis", "Cast", "Production", "Themes"}
    for section in page.sections:
        if section.title in target_sections and section.text.strip():
            sections_text.append(f"\n## {section.title}\n{section.text[:800]}")

    return "\n".join(sections_text)


@tool
def tavily_search(query: str) -> str:
    """Search the web for up-to-date movie information using Tavily.

    Use this tool for recent release dates, box office figures, upcoming sequels,
    actor filmographies, or any real-time information.

    Args:
        query: Search query (e.g., "Marvel 2025 upcoming movies release dates")

    Returns:
        Web search results with title, URL, and content snippets.
    """
    if not _TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is not set in .env")

    client = TavilyClient(api_key=_TAVILY_API_KEY)
    response = client.search(query, max_results=5)

    results: list[str] = []
    for r in response.get("results", []):
        title = r.get("title", "")
        url = r.get("url", "")
        content = r.get("content", "")[:400]
        results.append(f"[{title}]({url})\n{content}")

    return "\n\n".join(results) if results else "No results found."


def _tmdb_get(url: str) -> requests.Response:
    """API Key(v3) 또는 Bearer Access Token 중 설정된 것으로 TMDB 요청."""
    if _TMDB_API_KEY:
        return requests.get(
            url,
            params={"api_key": _TMDB_API_KEY, "language": "en-US"},
            timeout=10,
        )
    if _TMDB_ACCESS_TOKEN:
        return requests.get(
            url,
            params={"language": "en-US"},
            headers={
                "Authorization": f"Bearer {_TMDB_ACCESS_TOKEN}",
                "Accept": "application/json",
            },
            timeout=10,
        )
    raise RuntimeError("Set TMDB_API_KEY or TMDB_ACCESS_TOKEN in .env")


@tool
def tmdb_search(query: str) -> str:
    """Search TMDB for movie metadata: cast, director, release date, genres, and overview.

    Use this tool when you need structured movie metadata such as release dates,
    directors, or cast members.

    Args:
        query: Movie title or keyword (e.g., "Thor Ragnarok")

    Returns:
        Movie metadata including title, release date, director, cast, and overview.
    """
    search_resp = _tmdb_get(f"{_TMDB_BASE_URL}/search/movie?query={requests.utils.quote(query)}")
    search_resp.raise_for_status()
    results = search_resp.json().get("results", [])

    if not results:
        return f"No TMDB results found for: {query}"

    movie = results[0]
    movie_id = movie["id"]
    title = movie.get("title", "")
    release_date = movie.get("release_date", "N/A")
    overview = movie.get("overview", "")

    try:
        credits_resp = _tmdb_get(f"{_TMDB_BASE_URL}/movie/{movie_id}/credits")
        credits_resp.raise_for_status()
        credits = credits_resp.json()
        cast = ", ".join(c["name"] for c in credits.get("cast", [])[:5])
        director = next(
            (c["name"] for c in credits.get("crew", []) if c["job"] == "Director"),
            "Unknown",
        )
    except requests.RequestException as e:
        logger.warning("TMDB credits fetch failed for %s: %s", title, e)
        cast, director = "N/A", "N/A"

    return "\n".join([
        f"Title: {title}",
        f"Release Date: {release_date}",
        f"Director: {director}",
        f"Main Cast: {cast}",
        f"Overview: {overview}",
        f"TMDB URL: https://www.themoviedb.org/movie/{movie_id}",
    ])


TOOLS = [wikipedia_search, tavily_search, tmdb_search]
