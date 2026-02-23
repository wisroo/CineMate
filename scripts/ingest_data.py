"""
영화 데이터 수집 스크립트.

TMDB API + Wikipedia API로 영화 7편 수집 후 data/raw/ 에 txt 파일로 저장.
이미 파일이 존재하면 스킵 (멱등성 보장).

실행: uv run python scripts/ingest_data.py
"""

import logging
import os
import time
from pathlib import Path

import requests
import wikipediaapi
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY is not set in .env")

TMDB_BASE = "https://api.themoviedb.org/3"

MOVIES: list[dict] = [
    {
        "id": "299534",
        "title": "Avengers: Endgame",
        "series": "marvel",
        "filename": "avengers_endgame",
        "wiki": "Avengers: Endgame",
    },
    {
        "id": "284054",
        "title": "Black Panther",
        "series": "marvel",
        "filename": "black_panther",
        "wiki": "Black Panther (film)",
    },
    {
        "id": "634649",
        "title": "Spider-Man: No Way Home",
        "series": "marvel",
        "filename": "spider_man_no_way_home",
        "wiki": "Spider-Man: No Way Home",
    },
    {
        "id": "284053",
        "title": "Thor: Ragnarok",
        "series": "marvel",
        "filename": "thor_ragnarok",
        "wiki": "Thor: Ragnarok",
    },
    {
        "id": "1022789",
        "title": "Inside Out 2",
        "series": "pixar",
        "filename": "inside_out_2",
        "wiki": "Inside Out 2",
    },
    {
        "id": "508442",
        "title": "Soul",
        "series": "pixar",
        "filename": "soul",
        "wiki": "Soul (2020 film)",
    },
    {
        "id": "354912",
        "title": "Coco",
        "series": "pixar",
        "filename": "coco",
        "wiki": "Coco (2017 film)",
    },
]

RAW_DIR = Path("data/raw")


class TMDBFetcher:
    def fetch(self, movie: dict) -> str:
        movie_id = movie["id"]
        title = movie["title"]

        detail_url = f"{TMDB_BASE}/movie/{movie_id}"
        credits_url = f"{TMDB_BASE}/movie/{movie_id}/credits"
        params = {"api_key": TMDB_API_KEY, "language": "en-US"}

        try:
            detail_resp = requests.get(detail_url, params=params, timeout=10)
            detail_resp.raise_for_status()
            detail = detail_resp.json()

            credits_resp = requests.get(credits_url, params=params, timeout=10)
            credits_resp.raise_for_status()
            credits = credits_resp.json()
        except requests.RequestException as e:
            logger.error("TMDB request failed for %s: %s", title, e)
            raise RuntimeError(f"TMDB fetch failed for {title}") from e

        genres = ", ".join(g["name"] for g in detail.get("genres", []))
        tagline = detail.get("tagline", "")
        overview = detail.get("overview", "")
        release_date = detail.get("release_date", "")
        runtime = detail.get("runtime", "")

        cast = credits.get("cast", [])[:10]
        cast_names = ", ".join(c["name"] for c in cast)

        director = next(
            (c["name"] for c in credits.get("crew", []) if c["job"] == "Director"),
            "Unknown",
        )

        parts = [
            f"Title: {title}",
            f"Release Date: {release_date}",
            f"Runtime: {runtime} minutes",
            f"Genres: {genres}",
            f"Director: {director}",
            f"Main Cast: {cast_names}",
        ]
        if tagline:
            parts.append(f"Tagline: {tagline}")
        if overview:
            parts.append(f"Overview: {overview}")

        return "\n".join(parts)


class WikipediaFetcher:
    def __init__(self) -> None:
        self._wiki = wikipediaapi.Wikipedia(
            language="en",
            user_agent="CineMate/1.0 (educational project)",
        )

    def fetch(self, movie: dict) -> str:
        wiki_title = movie["wiki"]
        title = movie["title"]

        page = self._wiki.page(wiki_title)
        if not page.exists():
            logger.warning("Wikipedia page not found: %s", wiki_title)
            return ""

        sections_to_include = {"Plot", "Synopsis", "Cast", "Production", "Themes"}
        parts: list[str] = [f"Wikipedia: {title}", page.summary]

        for section in page.sections:
            if section.title in sections_to_include:
                parts.append(f"\n## {section.title}\n{section.text}")
                for subsection in section.sections:
                    if subsection.text.strip():
                        parts.append(f"\n### {subsection.title}\n{subsection.text}")

        return "\n".join(parts)


def ingest_movie(movie: dict, tmdb: TMDBFetcher, wiki: WikipediaFetcher) -> None:
    series_dir = RAW_DIR / movie["series"]
    series_dir.mkdir(parents=True, exist_ok=True)

    out_path = series_dir / f"{movie['filename']}.txt"
    if out_path.exists():
        logger.info("SKIP (already exists): %s", out_path)
        return

    logger.info("Fetching: %s", movie["title"])

    tmdb_text = tmdb.fetch(movie)
    wiki_text = wiki.fetch(movie)

    separator = "\n\n" + "=" * 60 + "\n\n"
    combined = separator.join(filter(None, [tmdb_text, wiki_text]))

    out_path.write_text(combined, encoding="utf-8")
    logger.info("Saved: %s (%d chars)", out_path, len(combined))


def main() -> None:
    tmdb = TMDBFetcher()
    wiki = WikipediaFetcher()

    for movie in MOVIES:
        try:
            ingest_movie(movie, tmdb, wiki)
        except Exception as e:
            logger.error("Failed to ingest %s: %s", movie["title"], e)
        time.sleep(0.3)  # TMDB rate limit 방어

    logger.info("Ingest complete. Files saved to %s", RAW_DIR)


if __name__ == "__main__":
    main()
