"""
tests/test_agent_graph.py

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

from graph.agent_graph import CineMateAgent, _graph
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


def _run(
    agent: CineMateAgent, query: str, session_id: str = "test-default"
) -> AgentResponse:
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


def test_rag_black_panther(agent):
    """블랙 팬서 줄거리 질문 → RAG Agent (test_rag.py에서 이전)."""
    query = "블랙 팬서의 줄거리는?"
    resp = _run(agent, query)
    _print_response(query, resp)

    assert resp.agent_used == "RAG Agent", f"Expected RAG Agent, got: {resp.agent_used}"
    assert resp.answer.strip(), "answer가 비어 있습니다."


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

    assert (
        resp.agent_used == "Tool Agent"
    ), f"Expected Tool Agent, got: {resp.agent_used}"
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
    query = "코코에서 헥터의 진짜 정체는?"
    resp = _run(agent, query)
    _print_response(query, resp)

    assert isinstance(resp, AgentResponse)
    assert resp.session_id
    assert (
        "해당 정보가 없습니다" not in resp.answer
    ), "RAG Agent가 코코 데이터를 찾지 못했습니다."


def test_response_agent_used_valid(agent):
    """agent_used는 'RAG Agent' 또는 'Tool Agent' 이어야 한다."""
    query = "코코에서 헥터의 진짜 정체는?"
    resp = _run(agent, query, session_id="test-valid-2")
    _print_response(query, resp)

    assert resp.agent_used in {"RAG Agent", "Tool Agent"}
    assert (
        "해당 정보가 없습니다" not in resp.answer
    ), "RAG Agent가 코코 데이터를 찾지 못했습니다."


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
    assert any(
        kw in answer_lower
        for kw in ["tony", "stark", "토니", "스타크", "iron", "아이언"]
    ), "멀티턴 맥락이 유지되지 않은 것으로 보입니다."


# ── 내부 그래프 State 검증 (test_translation.py에서 이전) ─────────────────────


@pytest.fixture(scope="module")
def coco_state():
    """코코 영혼 조건 질문으로 _graph를 직접 invoke해 내부 State를 반환한다."""
    query = "코코에서 영혼들이 이승으로 오기 위한 조건은?"
    try:
        config = {"configurable": {"thread_id": "test-translation-fixture"}}
        return _graph.invoke(
            {
                "messages": [("user", query)],
                "query": query,
            },
            config,
        )
    except RuntimeError as e:
        if "empty" in str(e).lower() or "vectorstore" in str(e).lower():
            pytest.skip(_SKIP_MSG)
        raise


def test_translation_produces_english_query(coco_state):
    """translation_node가 english_query를 비어 있지 않게 채워야 한다."""
    english_query = coco_state.get("english_query", "")
    print(f"\nenglish_query: {english_query}")
    assert english_query.strip(), "english_query가 비어 있습니다."


def test_translation_result_is_english(coco_state):
    """번역 결과가 주로 ASCII(영문)로 구성되어야 한다."""
    english_query = coco_state.get("english_query", "")
    ascii_ratio = sum(1 for c in english_query if ord(c) < 128) / max(
        len(english_query), 1
    )
    assert (
        ascii_ratio >= 0.7
    ), f"번역 결과가 영문이 아닌 것으로 보입니다: {english_query!r}"


def test_router_assigns_valid_route(coco_state):
    """router_node가 'rag' 또는 'tool' 중 하나를 결정해야 한다."""
    route = coco_state.get("route")
    print(f"\nroute: {route}")
    assert route in {"rag", "tool"}, f"유효하지 않은 route: {route!r}"


def test_coco_plot_routes_to_rag(coco_state):
    """줄거리·스토리 관련 질문은 'rag' 경로로 라우팅되어야 한다."""
    route = coco_state.get("route")
    assert route == "rag", f"줄거리 질문이 rag로 라우팅되지 않았습니다: {route!r}"


def test_rag_route_populates_retrieved_context(coco_state):
    """rag 경로 실행 후 retrieved_context가 채워져야 한다."""
    context = coco_state.get("retrieved_context", "")
    print(f"\nretrieved_context (첫 300자):\n{context[:300]}")
    assert context.strip(), "retrieved_context가 비어 있습니다."
