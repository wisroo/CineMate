"""
외부 API 수집기 (Fetcher).

Fetcher는 외부 소스에서 텍스트를 가져와 반환하는 수집 전용 컴포넌트다.
core/의 DataSource(RAG 소비용)와 역할이 다르며, scripts/ 레이어에서만 사용된다.

새 수집 소스를 추가할 때: Fetcher Protocol을 암묵적으로 구현하는 클래스를 이 파일에 추가한다.
"""

import logging
import os

import requests
import wikipediaapi
from dotenv import load_dotenv
from typing import Protocol

from constants import (
    MovieConfig,
    TMDB_BASE_URL,
    TMDB_LANGUAGE,
    TMDB_REQUEST_TIMEOUT,
    TMDB_CAST_LIMIT,
    WIKI_USER_AGENT,
    WIKI_SECTIONS,
)

load_dotenv()

logger = logging.getLogger(__name__)

_TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not _TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY is not set in .env")


class Fetcher(Protocol):
    """외부 소스에서 영화 텍스트를 수집하는 인터페이스."""

    def fetch(self, movie: MovieConfig) -> str:
        """MovieConfig를 받아 수집한 텍스트를 반환한다. 실패 시 빈 문자열 또는 예외."""
        ...


class TMDBFetcher:
    def fetch(self, movie: MovieConfig) -> str:
        movie_id = movie["id"]
        title = movie["title"]
        params = {"api_key": _TMDB_API_KEY, "language": TMDB_LANGUAGE}

        try:
            detail_resp = requests.get(
                f"{TMDB_BASE_URL}/movie/{movie_id}",
                params=params,
                timeout=TMDB_REQUEST_TIMEOUT,
            )
            detail_resp.raise_for_status()
            detail = detail_resp.json()

            credits_resp = requests.get(
                f"{TMDB_BASE_URL}/movie/{movie_id}/credits",
                params=params,
                timeout=TMDB_REQUEST_TIMEOUT,
            )
            credits_resp.raise_for_status()
            credits = credits_resp.json()
        except requests.RequestException as e:
            logger.error("TMDB request failed for %s: %s", title, e)
            raise RuntimeError(f"TMDB fetch failed for {title}") from e

        genres = ", ".join(g["name"] for g in detail.get("genres", []))
        cast_names = ", ".join(
            c["name"] for c in credits.get("cast", [])[:TMDB_CAST_LIMIT]
        )
        director = next(
            (c["name"] for c in credits.get("crew", []) if c["job"] == "Director"),
            "Unknown",
        )

        parts = [
            f"Title: {title}",
            f"Release Date: {detail.get('release_date', '')}",
            f"Runtime: {detail.get('runtime', '')} minutes",
            f"Genres: {genres}",
            f"Director: {director}",
            f"Main Cast: {cast_names}",
        ]
        if tagline := detail.get("tagline"):
            parts.append(f"Tagline: {tagline}")
        if overview := detail.get("overview"):
            parts.append(f"Overview: {overview}")

        return "\n".join(parts)


class WikipediaFetcher:
    def __init__(self) -> None:
        self._wiki = wikipediaapi.Wikipedia(
            language="en",
            user_agent=WIKI_USER_AGENT,
        )

    def fetch(self, movie: MovieConfig) -> str:
        wiki_title = movie["wiki"]
        title = movie["title"]

        page = self._wiki.page(wiki_title)
        if not page.exists():
            logger.warning("Wikipedia page not found: %s", wiki_title)
            return ""

        parts: list[str] = [f"Wikipedia: {title}", page.summary]

        for section in page.sections:
            if section.title in WIKI_SECTIONS:
                parts.append(f"\n## {section.title}\n{section.text}")
                for subsection in section.sections:
                    if subsection.text.strip():
                        parts.append(f"\n### {subsection.title}\n{subsection.text}")

        return "\n".join(parts)
