"""
graph/schemas.py

LangGraph 상태 타입 및 에이전트 응답 데이터 클래스 정의.
"""

from dataclasses import dataclass
from typing import Annotated, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


@dataclass
class AgentResponse:
    answer: str
    agent_used: (
        str  # "RAG Agent" | "Tool Agent" | "Researcher, Analyst, Editor, Reviewer"
    )
    sources: list[str]
    session_id: str


class DeepState(TypedDict):
    """디렉터 모드 (4-에이전트 파이프라인) 상태"""

    messages: Annotated[list[AnyMessage], add_messages]  # 멀티턴 대화 이력
    query: str
    english_query: str  # 영어로 번역된 검색용 쿼리
    raw_data: str  # Researcher 수집 결과 (plain text)
    draft: str  # Analyst 초안
    final_draft: str  # Editor 윤문 결과
    revision_count: int  # 무한 루프 방지 카운터 (최대 2회)
    review_feedback: str  # Reviewer 피드백 (REVISE 시)
    verdict: Literal["PASS", "REVISE", ""]
    sources: list[str]
    agent_used: str  # 실행된 에이전트 이력 (콤마 구분)
