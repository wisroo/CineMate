"""
tests/test_director_graph.py

디렉터 모드 4-에이전트 파이프라인 통합 테스트.
"""

import pytest

from graph.director_graph import run_director
from graph.schemas import AgentResponse


def _print_response(query: str, resp: AgentResponse) -> None:
    print("\n" + "-" * 60)
    print(f"Q: {query}")
    print(f"Agent : {resp.agent_used}")
    print(f"Sources: {', '.join(resp.sources) if resp.sources else 'none'}")
    print(f"Answer:\n{resp.answer}")
    print("-" * 60)


# ── 기본 응답 구조 ──────────────────────────────────────────────────────────────


def test_director_returns_agent_response():
    """run_director()가 AgentResponse 인스턴스를 반환해야 한다."""
    query = "코코에서 헥터의 진짜 정체는?"
    resp = run_director(query)
    _print_response(query, resp)

    assert isinstance(resp, AgentResponse)
    assert resp.answer, "디렉터 모드 답변이 비어 있습니다."


def test_director_agent_used_contains_pipeline():
    """agent_used 필드에 Researcher, Analyst, Editor, Reviewer가 모두 포함되어야 한다."""
    query = "코코에서 헥터의 진짜 정체는?"
    resp = run_director(query, session_id="test-pipeline")
    _print_response(query, resp)

    for role in ("Researcher", "Analyst", "Editor", "Reviewer"):
        assert (
            role in resp.agent_used
        ), f"'{role}'가 agent_used에 없습니다: {resp.agent_used}"


# ── 무한 루프 방지 ──────────────────────────────────────────────────────────────


def test_director_revision_count_bounded():
    """revision_count가 2를 초과하지 않아야 한다 (무한 루프 방지)."""
    from graph.director_graph import _director_graph
    from langchain_core.messages import HumanMessage

    query = "소울에서 22번이 지구에 가기 싫었던 이유는?"
    final_state = _director_graph.invoke(
        {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "english_query": "",
            "raw_data": "",
            "draft": "",
            "final_draft": "",
            "revision_count": 0,
            "review_feedback": "",
            "verdict": "",
            "sources": [],
            "agent_used": "",
        }
    )
    assert (
        final_state.get("revision_count", 0) <= 2
    ), f"revision_count = {final_state.get('revision_count')} > 2, 무한 루프 위험!"
    assert final_state.get("final_draft"), "final_draft가 비어 있습니다."
