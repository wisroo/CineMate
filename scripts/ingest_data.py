"""
영화 데이터 수집 오케스트레이터.

movies.py의 MOVIES 목록을 순회하며 각 영화를 수집하고 data/raw/ 에 txt로 저장한다.
이미 파일이 존재하면 스킵 (멱등성 보장).

실행:
    uv run python scripts/ingest_data.py                      # 전체 수집
    uv run python scripts/ingest_data.py --series marvel      # 시리즈 필터
    uv run python scripts/ingest_data.py --title "Coco"       # 단일 영화
"""

import argparse
import logging
import time

from constants import RAW_DIR, RATE_LIMIT_SLEEP, MovieConfig
from fetchers import Fetcher, TMDBFetcher, WikipediaFetcher
from movies import MOVIES

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def ingest_movie(movie: MovieConfig, tmdb: Fetcher, wiki: Fetcher) -> None:
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
    parser = argparse.ArgumentParser(description="영화 데이터 수집 스크립트")
    parser.add_argument("--series", help="특정 시리즈만 수집 (예: marvel, pixar)")
    parser.add_argument("--title", help="특정 영화만 수집 (예: 'Coco')")
    args = parser.parse_args()

    targets = MOVIES
    if args.series:
        targets = [m for m in targets if m["series"] == args.series]
    if args.title:
        targets = [m for m in targets if m["title"] == args.title]

    if not targets:
        logger.warning("No movies matched the given filters.")
        return

    tmdb = TMDBFetcher()
    wiki = WikipediaFetcher()

    for movie in targets:
        try:
            ingest_movie(movie, tmdb, wiki)
        except Exception as e:
            logger.error("Failed to ingest %s: %s", movie["title"], e)
        time.sleep(RATE_LIMIT_SLEEP)

    logger.info("Ingest complete. Files saved to %s", RAW_DIR)


if __name__ == "__main__":
    main()
