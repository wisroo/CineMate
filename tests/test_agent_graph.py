"""
CineMateAgent 통합 테스트 (5가지 질문 시나리오 + 멀티턴 확인).

전제 조건:
  - data/vectorstore 가 구축되어 있어야 합니다.
    먼저 실행: uv run python scripts/ingest_data.py
    그다음:   uv run python -c "from core.rag_pipeline import RAGPipeline; RAGPipeline().build()"
  - .env에 OPENAI_API_KEY(또는 AOAI_*), TMDB_API_KEY, TAVILY_API_KEY 설정 필요

실행 (답변 내용 출력):
  uv run pytest tests/test_agent_graph.py -v -s
"""

import pytest

from graph.agent_graph import CineMateAgent
from graph.schemas import AgentResponse

_SKIP_MSG = (
    "Vector store not built or API keys missing. "
    "Run: uv run python scripts/ingest_data.py && "
    'uv run python -c "from core.rag_pipeline import RAGPipeline; RAGPipeline().build()"'
)

_DIVIDER = "-" * 60


def _print_response(query: str, resp: AgentResponse) -> None:
    """테스트 결과에서 실제 응답 내용을 출력한다. pytest -s 옵션 필요."""
    print(f"\n{_DIVIDER}")
    print(f"Q: {query}")
    print(f"Agent : {resp.agent_used}")
    if resp.sources:
        print(f"Sources: {', '.join(resp.sources)}")
    print(f"Answer:\n{resp.answer}")
    print(_DIVIDER)


@pytest.fixture(scope="module")
def agent():
    try:
        return CineMateAgent()
    except RuntimeError as e:
        pytest.skip(f"Agent init failed: {e}")


def _run(agent: CineMateAgent, query: str, session_id: str = "test-default") -> AgentResponse:
    try:
        return agent.run(query, session_id=session_id)
    except RuntimeError as e:
        if "empty" in str(e).lower() or "vectorstore" in str(e).lower():
            pytest.skip(_SKIP_MSG)
        raise


# ── RAG 시나리오 ────────────────────────────────────────────────────────────

def test_rag_tony_stark_sacrifice(agent):
    """내적 질문 → RAG Agent가 응답해야 한다."""
    query = "엔드게임에서 토니가 희생한 이유?"
    resp = _run(agent, query)
    _print_response(query, resp)

    assert resp.agent_used == "RAG Agent", f"Expected RAG Agent, got: {resp.agent_used}"
    assert resp.answer.strip(), "answer가 비어 있습니다."
    assert len(resp.sources) >= 1, "sources가 비어 있습니다."


def test_rag_hector_identity(agent):
    """코코 헥터의 정체 → RAG Agent."""
    query = "코코에서 헥터의 진짜 정체는?"
    resp = _run(agent, query)
    _print_response(query, resp)

    assert resp.agent_used == "RAG Agent"
    assert resp.answer.strip()


def test_rag_soul_22(agent):
    """소울 22번 질문 → RAG Agent, CoT 스타일 답변."""
    query = "소울에서 22번이 지구에 가고 싶지 않았던 진짜 이유는?"
    resp = _run(agent, query)
    _print_response(query, resp)

    assert resp.agent_used == "RAG Agent"
    assert resp.answer.strip()


# ── Tool 시나리오 ────────────────────────────────────────────────────────────

def test_tool_marvel_upcoming(agent):
    """최신 정보 질문 → Tool Agent가 응답해야 한다."""
    query = "마블 2025년 개봉 예정작은?"
    resp = _run(agent, query, session_id="test-tool-1")
    _print_response(query, resp)

    assert resp.agent_used == "Tool Agent", f"Expected Tool Agent, got: {resp.agent_used}"
    assert resp.answer.strip()


def test_tool_box_office(agent):
    """박스오피스 수치 → Tool Agent."""
    query = "Avengers Endgame worldwide box office"
    resp = _run(agent, query, session_id="test-tool-2")
    _print_response(query, resp)

    assert resp.agent_used == "Tool Agent"
    assert resp.answer.strip()


# ── AgentResponse 구조 검증 ──────────────────────────────────────────────────

def test_response_is_agent_response(agent):
    """run()의 반환 타입이 AgentResponse 이어야 한다."""
    query = "블랙 팬서의 줄거리는?"
    resp = _run(agent, query)
    _print_response(query, resp)

    assert isinstance(resp, AgentResponse)
    assert resp.session_id


def test_response_agent_used_valid(agent):
    """agent_used는 'RAG Agent' 또는 'Tool Agent' 이어야 한다."""
    query = "블랙 팬서의 줄거리는?"
    resp = _run(agent, query, session_id="test-valid-2")
    _print_response(query, resp)

    assert resp.agent_used in {"RAG Agent", "Tool Agent"}


# ── 멀티턴 테스트 ─────────────────────────────────────────────────────────────

def test_multiturn_context_preserved(agent):
    """동일 session_id로 두 번 질문하면 이전 대화 맥락이 유지되어야 한다."""
    session = "test-multiturn"

    q1 = "토니 스타크가 누구야?"
    first = _run(agent, q1, session_id=session)
    _print_response(q1, first)
    assert first.answer.strip()

    q2 = "그가 엔드게임에서 어떻게 희생했어?"
    second = _run(agent, q2, session_id=session)
    _print_response(q2, second)
    assert second.answer.strip(), "두 번째 응답이 비어 있습니다."

    answer_lower = second.answer.lower()
    assert any(kw in answer_lower for kw in ["tony", "stark", "토니", "스타크", "iron", "아이언"]), (
        "멀티턴 맥락이 유지되지 않은 것으로 보입니다."
    )
