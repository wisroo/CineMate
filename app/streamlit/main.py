"""
CineMate Streamlit 채팅 UI.

실행:
  uv run streamlit run app/streamlit/main.py
"""

import sys
import uuid
from pathlib import Path

# streamlit run 은 스크립트 위치 기준으로 실행되므로 프로젝트 루트를 명시적으로 추가한다.
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from graph.agent_graph import CineMateAgent
from graph.schemas import AgentResponse

MOVIES: list[str] = [
    "Avengers: Endgame",
    "Black Panther",
    "Spider-Man: No Way Home",
    "Thor: Ragnarok",
    "Inside Out 2",
    "Soul",
    "Coco",
]

EXAMPLE_QUESTIONS: list[str] = [
    "엔드게임에서 토니가 희생한 이유?",
    "코코에서 헥터의 진짜 정체는?",
    "소울에서 22번이 지구에 가고 싶지 않았던 진짜 이유는?",
    "마블 2025년 개봉 예정작은?",
    "Avengers Endgame worldwide box office",
]


@st.cache_resource
def get_agent() -> CineMateAgent:
    return CineMateAgent()


def _init_session() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "last_response" not in st.session_state:
        st.session_state.last_response = None
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None


def _render_sidebar() -> None:
    with st.sidebar:
        st.title("🎬 CineMate")
        st.caption("디즈니·마블·픽사 세계관 분석 AI Agent")

        st.divider()
        st.subheader("적재된 영화 목록")
        for movie in MOVIES:
            st.markdown(f"- {movie}")

        st.divider()
        st.subheader("질문 예시")
        for i, q in enumerate(EXAMPLE_QUESTIONS):
            if st.button(q, key=f"ex_{i}", use_container_width=True):
                st.session_state.pending_question = q
                st.rerun()

        st.divider()
        last: AgentResponse | None = st.session_state.last_response
        if last:
            st.subheader("마지막 응답 경로")
            if last.agent_used == "RAG Agent":
                st.success(f"🔍 {last.agent_used}")
            else:
                st.info(f"🌐 {last.agent_used}")


def _render_agent_badge(agent_used: str) -> None:
    if agent_used == "RAG Agent":
        st.success(f"🔍 {agent_used}", icon=None)
    else:
        st.info(f"🌐 {agent_used}", icon=None)


def _render_sources(sources: list[str]) -> None:
    if sources:
        with st.expander("출처 보기"):
            for src in sources:
                st.write(src)


def _render_chat_history() -> None:
    for turn in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(turn["query"])
        with st.chat_message("assistant"):
            st.write(turn["answer"])
            _render_agent_badge(turn["agent_used"])
            _render_sources(turn["sources"])


def _process_query(query: str) -> None:
    agent = get_agent()

    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant"):
        with st.spinner("분석 중..."):
            resp = agent.run(query, session_id=st.session_state.session_id)

        st.write(resp.answer)
        _render_agent_badge(resp.agent_used)
        _render_sources(resp.sources)

    st.session_state.chat_history.append(
        {
            "query": query,
            "answer": resp.answer,
            "agent_used": resp.agent_used,
            "sources": resp.sources,
        }
    )
    st.session_state.last_response = resp


def main() -> None:
    st.set_page_config(page_title="CineMate", page_icon="🎬", layout="wide")
    _init_session()
    _render_sidebar()

    st.header("🎬 CineMate")
    st.caption("디즈니·마블·픽사 세계관에 대해 무엇이든 질문하세요.")

    _render_chat_history()

    # pending_question(예시 버튼 클릭)을 먼저 처리한 뒤 chat_input 확인
    query: str | None = None
    if st.session_state.pending_question:
        query = st.session_state.pending_question
        st.session_state.pending_question = None

    user_input = st.chat_input("영화에 대해 질문하세요...")
    if user_input:
        query = user_input

    if query:
        _process_query(query)


if __name__ == "__main__":
    main()
