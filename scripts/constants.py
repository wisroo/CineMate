"""
scripts/ 레이어 전용 상수 및 데이터 타입 정의.

수집 대상 설정(MovieConfig)과 Fetcher 동작을 결정하는 모든 상수를 여기서 관리한다.
"""

from pathlib import Path
from typing import TypedDict

RAW_DIR = Path("data/raw")

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_LANGUAGE = "en-US"
TMDB_REQUEST_TIMEOUT = 10
TMDB_CAST_LIMIT = 10

RATE_LIMIT_SLEEP = 0.3

WIKI_USER_AGENT = "CineMate/1.0 (educational project)"
WIKI_SECTIONS = frozenset({"Plot", "Synopsis", "Cast", "Production", "Themes"})


class MovieConfig(TypedDict):
    """단일 영화 수집 설정. ingest 단계에서만 사용되며 RAG/채팅 레이어로 전달되지 않는다."""

    id: str
    title: str
    series: str
    filename: str
    wiki: str
