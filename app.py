"""
app.py

CineMate Streamlit 채팅 UI: 팝콘 모드(싱글 에이전트)와 디렉터 모드(4-에이전트 파이프라인)를 제공한다.

실행:
  uv run streamlit run app.py
"""

import sys
import uuid
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from graph.agent_graph import CineMateAgent
from graph.schemas import AgentResponse

# ─── 설정 ──────────────────────────────────────────────────────────────────────

MOVIES: list[str] = [
    "Avengers: Endgame",
    "Black Panther",
    "Spider-Man: No Way Home",
    "Thor: Ragnarok",
    "Inside Out 2",
    "Soul",
    "Coco",
]

EXAMPLE_CHAT = [
    "엔드게임에서 토니가 희생한 이유?",
    "코코에서 헥터의 진짜 정체는?",
    "소울에서 22번이 지구에 가고 싶지 않았던 이유는?",
    "마블 2025년 개봉 예정작은?",
]

EXAMPLE_DIRECTOR = [
    "인사이드 아웃 2에서 불안이가 통제판을 잡았을 때의 연출적 의미는?",
    "코코에서 헥터의 정체가 영화의 주제 의식에 미치는 영향",
    "엔드게임에서 토니 스타크가 쓴 '나는 아이언맨이다'의 의미",
    "소울에서 22번은 왜 지구에 가기 싫었을까?",
]

# ─── CSS 주입 ──────────────────────────────────────────────────────────────────

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── 전체 배경 */
.stApp {
    background-color: #0f172a;
    color: #f8fafc;
}

/* ── 사이드바 */
section[data-testid="stSidebar"] {
    background: #0f172a;
    border-right: 1px solid #1e293b;
}
section[data-testid="stSidebar"] * {
    color: #cbd5e1 !important;
}

/* ── 버튼 초기화 */
.stButton > button {
    background: transparent;
    border: 1px solid #334155;
    color: #94a3b8;
    border-radius: 8px;
    transition: all 0.2s;
}
.stButton > button:hover {
    border-color: #6366f1;
    color: #a5b4fc;
    background: rgba(99,102,241,0.08);
}

/* ── chat_input 입력창 */
div[data-testid="stChatInput"] {
    padding-bottom: 1rem !important;
    max-width: 100%;
}

/* 입력 영역: 흰 배경 + 진한 테두리 */
div[data-testid="stChatInput"] > div:first-child {
    background-color: #ffffff !important;
    border: 2px solid #334155 !important;
    border-radius: 16px !important;
    width: 100% !important;
    box-sizing: border-box !important;
}

/* 텍스트 영역: 흰 배경에 검은 글씨 */
div[data-testid="stChatInput"] textarea {
    background-color: #ffffff !important;
    color: #0f172a !important;
    -webkit-text-fill-color: #0f172a !important;
    caret-color: #0f172a !important;
    min-height: 2.5rem !important;
    field-sizing: content !important;
    resize: none !important;
    overflow-y: auto !important;
}
div[data-testid="stChatInput"] textarea::placeholder,
div[data-testid="stChatInput"] textarea::-webkit-input-placeholder,
div[data-testid="stChatInput"] textarea::-moz-placeholder {
    color: #475569 !important;
    -webkit-text-fill-color: #475569 !important;
}

/* 전송 버튼 (흰 배경에 맞게 진한 아이콘) */
div[data-testid="stChatInput"] button {
    background: transparent !important;
}
div[data-testid="stChatInput"] svg {
    fill: #334155 !important;
}

/* ── 사용자 채팅 버블 */
[data-testid="stChatMessageContent"] {
    background: transparent;
}

/* ── 스피너 */
.stSpinner > div { color:#a5b4fc; }

/* ── 디바이더 */
hr { border-color: #1e293b !important; border-top-width: 1px !important; }

/* ── 제목 */
h1, h2, h3 { color: #f1f5f9 !important; }

/* ── 모드 뱃지 */
.badge-popcorn {
    display:inline-flex; align-items:center; gap:6px;
    background: linear-gradient(135deg,#f59e0b,#ea580c);
    color:#fff; font-weight:600; font-size:0.78rem;
    padding:4px 12px; border-radius:99px;
}
.badge-director {
    display:inline-flex; align-items:center; gap:6px;
    background: linear-gradient(135deg,#3b82f6,#4338ca);
    color:#fff; font-weight:600; font-size:0.78rem;
    padding:4px 12px; border-radius:99px;
}

/* ── 파이프라인 스텝 박스 */
.pipeline-step {
    font-size:0.78rem; padding:6px 12px;
    border-radius:8px; margin-bottom:4px;
    border: 1px solid #334155;
    background: #1e293b;
    display: flex; align-items:center; gap:8px;
}
.pipeline-step.done   { border-color:#22c55e; color:#86efac; }
.pipeline-step.active { border-color:#6366f1; color:#c7d2fe; }
.pipeline-step.wait   { color:#475569; }

/* ── 답변 카드 */
.answer-card {
    background:#1e293b;
    border:1px solid #334155;
    border-radius:16px;
    padding:20px 24px;
    color:#e2e8f0;
    line-height:1.75;
}
.answer-card strong { color:#a5b4fc; }

/* ── 출처 칩 */
.source-chip {
    display:inline-block;
    background:#0f172a;
    border:1px solid #334155;
    color:#64748b;
    border-radius:6px;
    font-size:0.72rem;
    padding:2px 10px;
    margin:2px;
}

/* ── 모드 선택 카드 */
.mode-card {
    border-radius:20px;
    padding:32px 24px;
    text-align:center;
    border: 2px solid transparent;
}

/* ── 숨김 streamlit 요소 */
#MainMenu, footer, header { visibility:hidden; display:none; }

/* 기본 테마의 흰색 배경 그라데이션 오버라이드 제거 */
.stApp > header { background: transparent !important; }
.st-emotion-cache-16txtl3 { padding-top: 2rem; }
</style>
"""

# ─── 에이전트 ──────────────────────────────────────────────────────────────────


@st.cache_resource
def get_agent() -> CineMateAgent:
    return CineMateAgent()


# ─── 세션 초기화 ───────────────────────────────────────────────────────────────


def _init_session() -> None:
    defaults = {
        "session_id": str(uuid.uuid4()),
        "chat_history": [],
        "last_response": None,
        "pending_question": None,
        "mode": "chat",  # "chat" | "director"
        "page": "landing",  # "landing" | "chat"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_chat() -> None:
    """대화를 초기화하고 새로운 세션 ID를 발급합니다."""
    st.session_state.chat_history = []
    st.session_state.last_response = None
    st.session_state.session_id = str(uuid.uuid4())


# ─── 사이드바 ──────────────────────────────────────────────────────────────────


def _render_sidebar() -> None:
    with st.sidebar:
        # 로고
        st.markdown(
            "<div style='display:flex;align-items:center;gap:8px;margin-bottom:4px'>"
            "<span style='font-size:1.4rem'>🎬</span>"
            "<span style='font-size:1.2rem;font-weight:800;letter-spacing:.05em;color:#f1f5f9'>CineMate</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption("Disney · Marvel · Pixar AI Agent")
        st.divider()

        # 모드 전환
        st.markdown("**모드 선택**")
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "🍿 팝콘",
                use_container_width=True,
                type="primary" if st.session_state.mode == "chat" else "secondary",
            ):
                if st.session_state.mode != "chat":
                    st.session_state.mode = "chat"
                    _reset_chat()
                st.session_state.page = "chat"
                st.rerun()
        with col2:
            if st.button(
                "🎬 디렉터",
                use_container_width=True,
                type="primary" if st.session_state.mode == "director" else "secondary",
            ):
                if st.session_state.mode != "director":
                    st.session_state.mode = "director"
                    _reset_chat()
                st.session_state.page = "chat"
                st.rerun()

        st.divider()

        # 현재 모드 설명
        if st.session_state.mode == "chat":
            st.markdown(
                "<div class='badge-popcorn'>🍿 팝콘 모드 활성</div>",
                unsafe_allow_html=True,
            )
            st.caption("빠르고 정확한 싱글 에이전트 답변")
        else:
            st.markdown(
                "<div class='badge-director'>🎬 디렉터 모드 활성</div>",
                unsafe_allow_html=True,
            )
            st.caption("4-에이전트 심층 분석 파이프라인")

        st.divider()

        # 영화 목록
        st.markdown("**📁 데이터베이스**")
        for m in MOVIES:
            st.markdown(
                f"<span style='color:#64748b;font-size:.8rem'>● {m}</span>",
                unsafe_allow_html=True,
            )

        st.divider()

        # 예시 질문
        st.markdown("**💡 예시 질문**")
        examples = (
            EXAMPLE_DIRECTOR if st.session_state.mode == "director" else EXAMPLE_CHAT
        )
        for i, q in enumerate(examples):
            if st.button(q, key=f"ex_{i}", use_container_width=True):
                st.session_state.pending_question = q
                st.session_state.page = "chat"
                st.rerun()

        st.divider()

        # 마지막 응답 경로
        last: AgentResponse | None = st.session_state.last_response
        if last:
            st.markdown("**마지막 응답 경로**")
            if "Reviewer" in (last.agent_used or ""):
                st.markdown(
                    "<div class='badge-director'>🎬 Director Pipeline</div>",
                    unsafe_allow_html=True,
                )
            elif "RAG" in (last.agent_used or ""):
                st.success(f"🔍 {last.agent_used}")
            else:
                st.info(f"🌐 {last.agent_used}")


# ─── 랜딩 페이지 ───────────────────────────────────────────────────────────────


def _render_landing() -> None:
    st.markdown(
        "<h1 style='text-align:center;font-size:2.4rem;font-weight:800;"
        "background:linear-gradient(90deg,#a5b4fc,#818cf8);-webkit-background-clip:text;"
        "-webkit-text-fill-color:transparent;margin-bottom:4px'>🎬 CineMate</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#64748b;margin-bottom:28px'>"
        "Disney · Marvel · Pixar 세계관 AI 탐험가</p>",
        unsafe_allow_html=True,
    )

    # 랜딩 페이지: 카드 아래 CTA 버튼만 박스 스타일로 보이게 (해당 박스만 클릭 시 진입)
    st.markdown(
        """
        <style>
        /* 랜딩 CTA 버튼 공통 */
        [data-testid="column"] .stButton > button {
            margin-top: 20px !important;
            padding: 10px 0 !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
            font-size: .95rem !important;
            width: 100% !important;
            transition: background .2s, color .2s !important;
        }
        /* 팝콘(첫 번째 컬럼) */
        [data-testid="column"]:nth-of-type(1) .stButton > button {
            background: rgba(245,158,11,.2) !important;
            color: #fbbf24 !important;
            border: 1.5px solid rgba(245,158,11,.4) !important;
        }
        [data-testid="column"]:nth-of-type(1) .stButton > button:hover {
            background: rgba(245,158,11,.35) !important;
            color: #fcd34d !important;
            border-color: #f59e0b !important;
        }
        /* 디렉터(두 번째 컬럼) */
        [data-testid="column"]:nth-of-type(2) .stButton > button {
            background: rgba(99,102,241,.2) !important;
            color: #a5b4fc !important;
            border: 1.5px solid rgba(99,102,241,.4) !important;
        }
        [data-testid="column"]:nth-of-type(2) .stButton > button:hover {
            background: rgba(99,102,241,.35) !important;
            color: #c7d2fe !important;
            border-color: #6366f1 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown(
            """
            <div class='mode-card' style='height: 100%; background:linear-gradient(135deg,rgba(245,158,11,.12),rgba(234,88,12,.06));
            border-color:rgba(245,158,11,.3)'>
                <div style='font-size:3rem;margin-bottom:12px'>🍿</div>
                <h2 style='color:#fbbf24;font-size:1.5rem;margin-bottom:8px'>팝콘 모드</h2>
                <p style='color:#94a3b8;font-size:.9rem'>가볍게 즐기는 영화 정보<br>줄거리 · 팩트 체크 · 박스오피스</p>
                <div style='margin-top:16px;color:#f59e0b;font-size:.85rem;font-weight:600'>⚡ 빠른 단일 에이전트</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("🍿 팝콘 모드 진입", key="landing_chat", use_container_width=True):
            if st.session_state.mode != "chat":
                _reset_chat()
            st.session_state.mode = "chat"
            st.session_state.page = "chat"
            st.rerun()

    with col2:
        st.markdown(
            """
            <div class='mode-card' style='height: 100%; background:linear-gradient(135deg,rgba(59,130,246,.12),rgba(67,56,202,.06));
            border-color:rgba(99,102,241,.3)'>
                <div style='font-size:3rem;margin-bottom:12px'>🎬</div>
                <h2 style='color:#818cf8;font-size:1.5rem;margin-bottom:8px'>디렉터 모드</h2>
                <p style='color:#94a3b8;font-size:.9rem'>감독의 시선으로 보는 심층 분석<br>캐릭터 심리 · 세계관 연결 · 메타포</p>
                <div style='margin-top:16px;color:#6366f1;font-size:.85rem;font-weight:600'>✨ 4-에이전트 파이프라인</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "🎬 디렉터 모드 진입", key="landing_director", use_container_width=True
        ):
            if st.session_state.mode != "director":
                _reset_chat()
            st.session_state.mode = "director"
            st.session_state.page = "chat"
            st.rerun()


# ─── 채팅 렌더 ─────────────────────────────────────────────────────────────────


def _render_mode_header() -> None:
    if st.session_state.mode == "chat":
        st.markdown(
            "<div class='badge-popcorn' style='margin-bottom:8px'>🍿 팝콘 모드</div>",
            unsafe_allow_html=True,
        )
        st.caption("디즈니·마블·픽사 세계관에 대해 무엇이든 질문하세요.")
    else:
        st.markdown(
            "<div class='badge-director' style='margin-bottom:8px'>🎬 디렉터 모드</div>",
            unsafe_allow_html=True,
        )
        st.caption("Researcher → Analyst → Editor → Reviewer 4단계 심층 분석")


def _render_sources(sources: list[str]) -> None:
    if not sources:
        return
    chips = "".join(f"<span class='source-chip'>📎 {s}</span>" for s in sources)
    st.markdown(f"<div style='margin-top:8px'>{chips}</div>", unsafe_allow_html=True)


def _render_agent_badge(agent_used: str) -> None:
    if "Reviewer" in agent_used:
        st.markdown(
            f"<div class='badge-director' style='margin-top:8px'>🎬 {agent_used}</div>",
            unsafe_allow_html=True,
        )
    elif "RAG" in agent_used:
        st.markdown(
            f"<span style='color:#86efac;font-size:.78rem'>🔍 {agent_used}</span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<span style='color:#7dd3fc;font-size:.78rem'>🌐 {agent_used}</span>",
            unsafe_allow_html=True,
        )


def _render_chat_history() -> None:
    for turn in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(turn["query"])
        with st.chat_message("assistant"):
            st.markdown(
                f"<div class='answer-card'>{turn['answer']}</div>",
                unsafe_allow_html=True,
            )
            _render_agent_badge(turn["agent_used"])
            _render_sources(turn["sources"])


def _process_query(query: str) -> None:
    agent = get_agent()
    mode = st.session_state.mode

    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant"):
        if mode == "director":
            # 디렉터 모드: 4단계 파이프라인 진행 상황 표시
            status_placeholder = st.empty()

            def _show_step(step: int) -> None:
                steps = [
                    ("🔍", "Researcher", "리서처가 자료를 수집 중입니다..."),
                    ("🧠", "Analyst", "애널리스트가 심층 분석 중입니다..."),
                    ("✍️", "Editor", "에디터가 디즈니 톤으로 윤문 중입니다..."),
                    ("✅", "Reviewer", "리뷰어가 품질을 검수 중입니다..."),
                ]
                lines = []
                for i, (icon, name, desc) in enumerate(steps):
                    if i < step:
                        cls = "done"
                        mark = "✅"
                    elif i == step:
                        cls = "active"
                        mark = "⏳"
                    else:
                        cls = "wait"
                        mark = "○"
                    lines.append(
                        f"<div class='pipeline-step {cls}'>{mark} <b>{icon} {name}</b>"
                        + (f" — {desc}" if i == step else "")
                        + "</div>"
                    )
                status_placeholder.markdown(
                    "<div style='margin-bottom:12px'>" + "".join(lines) + "</div>",
                    unsafe_allow_html=True,
                )

            # 단계별 표시 (실제 실행은 백엔드에서 한 번에 처리)
            _show_step(0)
            resp = agent.run(
                query, session_id=st.session_state.session_id, mode="director"
            )
            _show_step(4)  # 모두 완료

        else:
            # 팝콘 모드
            with st.spinner("🍿 분석 중..."):
                resp = agent.run(
                    query, session_id=st.session_state.session_id, mode="chat"
                )

        # 답변 출력
        st.markdown(
            f"<div class='answer-card'>{resp.answer}</div>",
            unsafe_allow_html=True,
        )
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


# ─── 메인 ──────────────────────────────────────────────────────────────────────


def main() -> None:
    st.set_page_config(
        page_title="CineMate",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    _init_session()

    if st.session_state.page == "landing":
        # 랜딩 페이지: 상단 여백 제거 CSS 주입 (사이드바 버튼 숨김 제거)
        st.markdown(
            """
            <style>
            section[data-testid="stSidebar"] { display: none; }
            .st-emotion-cache-1jicfl2 { padding-top: 2rem; }
            </style>
            """,
            unsafe_allow_html=True,
        )
        _render_landing()
    else:
        # 브라우저 캐시로 사이드바가 접혀있을 수 있으므로 CSS로 강제 고정
        st.markdown(
            """
            <style>
            section[data-testid="stSidebar"] {
                display: block !important;
                transform: none !important;
                min-width: 244px !important;
                visibility: visible !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        _render_sidebar()
        _render_mode_header()
        _render_chat_history()

        # pending_question 처리 (예시 버튼 클릭)
        query: str | None = None
        if st.session_state.pending_question:
            query = st.session_state.pending_question
            st.session_state.pending_question = None

        user_input = st.chat_input("영화에 대해 질문하세요... 🎬")
        if user_input:
            query = user_input

        if query:
            _process_query(query)


if __name__ == "__main__":
    main()
