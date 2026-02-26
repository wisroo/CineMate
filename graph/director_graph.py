"""
graph/director_graph.py

디렉터 모드 4-에이전트 파이프라인

그래프 흐름:
  START → translation_node → researcher_agent → (tool_calls) → tools_node → researcher_agent
                          └─ (no tool_calls) → analyst → editor → reviewer
  reviewer → PASS          → END
           → REVISE & count < 2 → analyst
           → REVISE & count >= 2 → END (force stop)
"""

import logging
import os
import re
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from core.prompts import (
    ANALYST_PROMPT,
    EDITOR_PROMPT,
    RESEARCHER_PROMPT,
    REVIEWER_PROMPT,
    TRANSLATION_PROMPT,
)
from core.tools import RESEARCHER_TOOLS
from graph.schemas import AgentResponse, DeepState

load_dotenv()

logger = logging.getLogger(__name__)


def _create_llm():
    """AOAI_* (Azure) 또는 OPENAI_API_KEY 기준으로 ChatLLM 생성."""
    aoai_key = os.getenv("AOAI_API_KEY")
    aoai_endpoint = os.getenv("AOAI_ENDPOINT")
    if aoai_key and aoai_endpoint:
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_endpoint=aoai_endpoint.rstrip("/"),
            api_key=aoai_key,
            azure_deployment=os.getenv("AOAI_DEPLOY_GPT4O_MINI", "gpt-4o-mini"),
            openai_api_version=os.getenv("AOAI_API_VERSION", "2024-02-01"),
            temperature=0,
        )
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    raise RuntimeError(
        "Set either AOAI_API_KEY + AOAI_ENDPOINT (Azure) or OPENAI_API_KEY in .env"
    )


_llm = _create_llm()
_llm_researcher = _llm.bind_tools(RESEARCHER_TOOLS)
_tool_map = {t.name: t for t in RESEARCHER_TOOLS}


# ─────────────────── Translation ──────────────────────────────────────────────


def translation_node(state: DeepState) -> dict:
    """사용자의 원본 질문을 영문으로 번역하여 검색 쿼리 품질을 높인다."""
    query = state.get("query", "")
    if not query and state.get("messages"):
        query = str(state["messages"][-1].content)

    prompt = TRANSLATION_PROMPT.format(query=query)
    response = _llm.invoke([HumanMessage(content=prompt)])
    english_query = str(response.content).strip()
    logger.info("[Director] Translated Query: %s → %s", query, english_query)

    return {"english_query": english_query, "query": query or english_query}


# ─────────────────── Researcher (ReAct) ───────────────────────────────────────


def researcher_agent(state: DeepState) -> dict:
    """4가지 도구를 사용해 raw 데이터를 수집하는 ReAct 에이전트."""
    english_query = state.get("english_query") or state.get("query", "")
    system_msg = SystemMessage(content=RESEARCHER_PROMPT)

    messages = state.get("messages", [])[-10:]
    # 첫 진입 시 영어 쿼리를 메시지로 삽입해 도구 활용을 유도
    if not messages or not any("rag_search" in str(m) for m in messages):
        messages = [
            HumanMessage(
                content=f"Research the following question thoroughly: {english_query}"
            )
        ]

    invoke_msgs = [system_msg] + messages
    response = _llm_researcher.invoke(invoke_msgs)
    logger.info("[Director] Researcher tool_calls: %s", bool(response.tool_calls))

    result: dict = {"messages": [response]}

    # 도구 호출이 완료되어 최종 raw_data를 생산한 경우
    if not response.tool_calls:
        result["raw_data"] = str(response.content)
        result["agent_used"] = "Researcher"

    return result


def researcher_tools_node(state: DeepState) -> dict:
    """Researcher가 선택한 도구를 실행한다."""
    messages = state.get("messages", [])
    last_message = messages[-1]

    new_messages = []
    sources: list[str] = list(state.get("sources") or [])

    for call in last_message.tool_calls:  # type: ignore
        tool_fn = _tool_map.get(call["name"])
        if tool_fn is None:
            tool_result = f"Unknown tool: {call['name']}"
        else:
            try:
                tool_result = tool_fn.invoke(call["args"])
            except Exception as e:
                logger.error("[Director] Tool %s failed: %s", call["name"], e)
                tool_result = f"Tool error: {e}"

        if (
            isinstance(tool_result, str)
            and tool_result.startswith("[")
            and "](" in tool_result
        ):
            source = tool_result.split("](")[1].split(")")[0]
            if source not in sources:
                sources.append(source)

        new_messages.append(
            ToolMessage(content=str(tool_result), tool_call_id=call["id"])
        )

    return {"messages": new_messages, "sources": sources}


def _researcher_route(state: DeepState) -> Literal["researcher_tools_node", "analyst"]:
    """tool_calls가 있으면 도구 실행, 없으면 Analyst로 이동."""
    messages = state.get("messages", [])
    last = messages[-1] if messages else None
    if last and getattr(last, "tool_calls", None):
        return "researcher_tools_node"
    return "analyst"


# ─────────────────── Analyst (CoT) ────────────────────────────────────────────


def analyst(state: DeepState) -> dict:
    """수집된 raw_data를 기반으로 CoT 초안을 작성한다."""
    query = state.get("query", "")
    raw_data = state.get("raw_data", "")
    feedback = state.get("review_feedback", "")

    prompt = ANALYST_PROMPT.format(
        query=query,
        raw_data=raw_data,
        feedback=feedback or "없음",
    )
    response = _llm.invoke([HumanMessage(content=prompt)])
    logger.info("[Director] Analyst produced draft.")

    return {
        "draft": str(response.content),
        "agent_used": "Researcher, Analyst",
        "messages": [AIMessage(content=str(response.content))],
    }


# ─────────────────── Editor (Few-shot) ────────────────────────────────────────


def editor(state: DeepState) -> dict:
    """Analyst 초안을 디즈니 톤에 맞게 윤문한다."""
    draft = state.get("draft", "")
    prompt = EDITOR_PROMPT.format(draft=draft)
    response = _llm.invoke([HumanMessage(content=prompt)])
    logger.info("[Director] Editor produced final_draft.")

    return {
        "final_draft": str(response.content),
        "agent_used": "Researcher, Analyst, Editor",
        "messages": [AIMessage(content=str(response.content))],
    }


# ─────────────────── Reviewer ─────────────────────────────────────────────────


def reviewer(state: DeepState) -> dict:
    """최종 원고를 검수하여 PASS 또는 REVISE+FEEDBACK을 반환한다."""
    query = state.get("query", "")
    raw_data = state.get("raw_data", "")
    final_draft = state.get("final_draft", "")

    prompt = REVIEWER_PROMPT.format(
        query=query,
        raw_data=raw_data,
        final_draft=final_draft,
    )
    response = _llm.invoke([HumanMessage(content=prompt)])
    raw_output = str(response.content).strip()
    logger.info("[Director] Reviewer output: %r", raw_output)

    # VERDICT 파싱
    verdict: Literal["PASS", "REVISE", ""] = ""
    feedback = ""
    if "VERDICT: PASS" in raw_output:
        verdict = "PASS"
    elif "VERDICT: REVISE" in raw_output:
        verdict = "REVISE"
        feedback_match = re.search(r"FEEDBACK:\s*(.+)", raw_output, re.DOTALL)
        feedback = feedback_match.group(1).strip() if feedback_match else ""

    revision_count = state.get("revision_count", 0)
    return {
        "verdict": verdict,
        "review_feedback": feedback,
        "revision_count": revision_count + (1 if verdict == "REVISE" else 0),
        "agent_used": "Researcher, Analyst, Editor, Reviewer",
        "messages": [AIMessage(content=raw_output)],
    }


def _reviewer_route(state: DeepState) -> Literal["analyst", "end"]:
    """PASS이거나 revision_count >= 2이면 END, 아니면 재수정."""
    verdict = state.get("verdict", "")
    revision_count = state.get("revision_count", 0)

    if verdict == "PASS" or revision_count >= 2:
        logger.info(
            "[Director] Reviewer route → END (verdict=%s, count=%d)",
            verdict,
            revision_count,
        )
        return "end"

    logger.info("[Director] Reviewer route → REVISE (count=%d)", revision_count)
    return "analyst"


# ─────────────────── Graph Assembly ───────────────────────────────────────────


def _build_director_graph() -> StateGraph:
    builder = StateGraph(DeepState)

    builder.add_node("translation_node", translation_node)
    builder.add_node("researcher_agent", researcher_agent)
    builder.add_node("researcher_tools_node", researcher_tools_node)
    builder.add_node("analyst", analyst)
    builder.add_node("editor", editor)
    builder.add_node("reviewer", reviewer)

    builder.add_edge(START, "translation_node")
    builder.add_edge("translation_node", "researcher_agent")
    builder.add_conditional_edges(
        "researcher_agent",
        _researcher_route,
        {"researcher_tools_node": "researcher_tools_node", "analyst": "analyst"},
    )
    builder.add_edge("researcher_tools_node", "researcher_agent")
    builder.add_edge("analyst", "editor")
    builder.add_edge("editor", "reviewer")
    builder.add_conditional_edges(
        "reviewer",
        _reviewer_route,
        {"analyst": "analyst", "end": END},
    )

    return builder.compile()


_director_graph = _build_director_graph()


def run_director(query: str, session_id: str = "default") -> AgentResponse:
    """디렉터 모드 단독 실행 진입점 (테스트·직접 호출용)."""
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
    return AgentResponse(
        answer=final_state.get("final_draft", ""),
        agent_used=final_state.get("agent_used", ""),
        sources=final_state.get("sources", []),
        session_id=session_id,
    )
