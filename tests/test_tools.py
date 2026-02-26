"""
core/tools.py 단위 테스트.

실제 외부 API를 호출하지 않고 mock으로 동작을 검증한다.

실행:
  uv run pytest tests/test_tools.py -v
"""

from unittest.mock import MagicMock, patch

import pytest


# ── wikipedia_search ─────────────────────────────────────────────────────────

def test_wikipedia_search_found():
    """페이지가 존재하면 제목·요약·섹션을 포함한 문자열을 반환해야 한다."""
    mock_section = MagicMock()
    mock_section.title = "Plot"
    mock_section.text = "Tony Stark snaps his fingers."

    mock_page = MagicMock()
    mock_page.exists.return_value = True
    mock_page.title = "Avengers: Endgame"
    mock_page.summary = "A 2019 Marvel film."
    mock_page.sections = [mock_section]

    with patch("core.tools._wiki") as mock_wiki:
        mock_wiki.page.return_value = mock_page
        from core.tools import wikipedia_search

        result = wikipedia_search.invoke({"query": "Avengers Endgame"})

    assert "Avengers: Endgame" in result
    assert "A 2019 Marvel film." in result
    assert "Plot" in result
    assert "Tony Stark snaps his fingers." in result


def test_wikipedia_search_not_found():
    """페이지가 없으면 not-found 메시지를 반환해야 한다."""
    mock_page = MagicMock()
    mock_page.exists.return_value = False

    with patch("core.tools._wiki") as mock_wiki:
        mock_wiki.page.return_value = mock_page
        from core.tools import wikipedia_search

        result = wikipedia_search.invoke({"query": "NonExistentMovie12345"})

    assert "not found" in result.lower()


# ── tavily_search ─────────────────────────────────────────────────────────────

def test_tavily_search_no_api_key(monkeypatch):
    """TAVILY_API_KEY 미설정 시 RuntimeError를 발생시켜야 한다."""
    monkeypatch.setattr("core.tools._TAVILY_API_KEY", "")
    from core.tools import tavily_search

    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        tavily_search.invoke({"query": "Marvel 2025"})


def test_tavily_search_returns_results(monkeypatch):
    """검색 결과가 있으면 제목·URL·내용을 포함한 문자열을 반환해야 한다."""
    monkeypatch.setattr("core.tools._TAVILY_API_KEY", "fake-key")

    mock_response = {
        "results": [
            {
                "title": "Marvel 2025 Films",
                "url": "https://example.com/marvel-2025",
                "content": "Upcoming Marvel movies in 2025...",
            }
        ]
    }

    with patch("core.tools.TavilyClient") as MockClient:
        MockClient.return_value.search.return_value = mock_response
        from core.tools import tavily_search

        result = tavily_search.invoke({"query": "Marvel 2025"})

    assert "Marvel 2025 Films" in result
    assert "https://example.com/marvel-2025" in result
    assert "Upcoming Marvel movies" in result


def test_tavily_search_no_results(monkeypatch):
    """검색 결과가 없으면 'No results found.' 를 반환해야 한다."""
    monkeypatch.setattr("core.tools._TAVILY_API_KEY", "fake-key")

    with patch("core.tools.TavilyClient") as MockClient:
        MockClient.return_value.search.return_value = {"results": []}
        from core.tools import tavily_search

        result = tavily_search.invoke({"query": "unknown query xyz"})

    assert result == "No results found."


# ── tmdb_search ───────────────────────────────────────────────────────────────

def _make_tmdb_responses():
    """search + credits mock 응답을 생성한다."""
    search_json = {
        "results": [
            {"id": 299534, "title": "Avengers: Endgame", "release_date": "2019-04-26", "overview": "After the devastating events..."}
        ]
    }
    credits_json = {
        "cast": [
            {"name": "Robert Downey Jr."},
            {"name": "Chris Evans"},
        ],
        "crew": [
            {"name": "Anthony Russo", "job": "Director"},
        ],
    }
    return search_json, credits_json


def test_tmdb_search_returns_metadata(monkeypatch):
    """TMDB 응답에서 제목, 감독, 출연진, 개봉일이 포함된 문자열을 반환해야 한다."""
    monkeypatch.setattr("core.tools._TMDB_API_KEY", "fake-tmdb-key")
    monkeypatch.setattr("core.tools._TMDB_ACCESS_TOKEN", "")

    search_json, credits_json = _make_tmdb_responses()

    search_resp = MagicMock()
    search_resp.json.return_value = search_json
    search_resp.raise_for_status = MagicMock()

    credits_resp = MagicMock()
    credits_resp.json.return_value = credits_json
    credits_resp.raise_for_status = MagicMock()

    with patch("core.tools.requests.get", side_effect=[search_resp, credits_resp]):
        from core.tools import tmdb_search

        result = tmdb_search.invoke({"query": "Avengers Endgame"})

    assert "Avengers: Endgame" in result
    assert "2019-04-26" in result
    assert "Anthony Russo" in result
    assert "Robert Downey Jr." in result
    assert "https://www.themoviedb.org/movie/299534" in result


def test_tmdb_search_no_results(monkeypatch):
    """TMDB 검색 결과가 없으면 not-found 메시지를 반환해야 한다."""
    monkeypatch.setattr("core.tools._TMDB_API_KEY", "fake-tmdb-key")
    monkeypatch.setattr("core.tools._TMDB_ACCESS_TOKEN", "")

    empty_resp = MagicMock()
    empty_resp.json.return_value = {"results": []}
    empty_resp.raise_for_status = MagicMock()

    with patch("core.tools.requests.get", return_value=empty_resp):
        from core.tools import tmdb_search

        result = tmdb_search.invoke({"query": "NonExistentFilm99999"})

    assert "No TMDB results found" in result


def test_tmdb_search_no_credentials(monkeypatch):
    """TMDB_API_KEY와 TMDB_ACCESS_TOKEN 모두 없으면 RuntimeError를 발생시켜야 한다."""
    monkeypatch.setattr("core.tools._TMDB_API_KEY", "")
    monkeypatch.setattr("core.tools._TMDB_ACCESS_TOKEN", "")

    # requests.get이 호출되면 _tmdb_get에서 RuntimeError가 발생해야 함
    with pytest.raises(RuntimeError, match="TMDB"):
        from core.tools import tmdb_search

        tmdb_search.invoke({"query": "Avengers"})
