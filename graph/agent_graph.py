"""
LangGraph Multi-Agent 그래프: router → rag_node | tool_node.

그래프 흐름:
  START → router_node → (conditional) rag_node | tool_node → END

Memory:
  InMemorySaver checkpointer로 thread_id 기반 멀티턴 대화 상태를 보존한다.
"""

import logging
import os
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from core.prompts import RAG_SYSTEM_PROMPT, ROUTER_PROMPT, TOOL_SYSTEM_PROMPT
from core.rag_pipeline import RAGPipeline
from core.tools import TOOLS
from graph.schemas import AgentResponse

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
_llm_with_tools = _llm.bind_tools(TOOLS)
_tool_map = {t.name: t for t in TOOLS}


class CineMateState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    route: Literal["rag", "tool"]
    retrieved_context: str
    agent_used: str
    sources: list[str]
    final_answer: str


def router_node(state: CineMateState) -> dict:
    """질문을 분석해 'rag' 또는 'tool' 경로를 결정한다."""
    query = state["query"]
    prompt = ROUTER_PROMPT.format(query=query)
    response = _llm.invoke([HumanMessage(content=prompt)])
    raw = response.content.strip().lower()
    route: Literal["rag", "tool"] = "tool" if "tool" in raw else "rag"
    logger.info("Router decision: %s (raw=%r)", route, raw)
    return {"route": route}


# 한국어 질문 시 벡터 검색 품질을 위해 영문 키워드를 붙여 재검색할 때 사용
_RAG_QUERY_KEYWORDS = [
    ("엔드게임", "Avengers Endgame Tony Stark"),
    ("토니", "Tony Stark Iron Man"),
    ("스타크", "Tony Stark"),
    ("블랙 팬서", "Black Panther"),
    ("스파이더맨", "Spider-Man No Way Home"),
    ("소울", "Soul 22"),
    ("코코", "Coco Hector"),
    ("헥터", "Coco Hector"),
    ("인사이드 아웃", "Inside Out"),
    ("토르", "Thor Ragnarok"),
]


def _retrieval_query(query: str) -> str:
    """한국어 포함 시 영문 키워드를 붙여 검색 정확도를 높인다."""
    added = []
    for kr, en in _RAG_QUERY_KEYWORDS:
        if kr in query and en not in added:
            added.append(en)
    if added:
        return f"{query} {' '.join(added)}"
    return query


def rag_node(state: CineMateState) -> dict:
    """ChromaDB에서 관련 문서를 검색하고 CoT 프롬프트로 LLM 답변을 생성한다."""
    query = state["query"]

    pipeline = RAGPipeline()
    try:
        retriever = pipeline.get_retriever(k=4)
        retrieval_query = _retrieval_query(query)
        docs = retriever.invoke(retrieval_query)
    except RuntimeError as e:
        logger.error("RAG retrieval failed: %s", e)
        raise

    context = "\n\n".join(doc.page_content for doc in docs)
    sources = list({doc.metadata.get("source", "") for doc in docs if doc.metadata.get("source")})

    prompt = RAG_SYSTEM_PROMPT.format(context=context, question=query)
    response = _llm.invoke([HumanMessage(content=prompt)])
    answer = response.content

    return {
        "retrieved_context": context,
        "final_answer": answer,
        "sources": sources,
        "agent_used": "RAG Agent",
        "messages": [AIMessage(content=answer)],
    }


def tool_node(state: CineMateState) -> dict:
    """ReAct 루프: LLM이 도구 호출을 멈출 때까지 반복 실행 후 최종 답변을 반환한다."""
    query = state["query"]
    messages = [
        HumanMessage(content=TOOL_SYSTEM_PROMPT),
        HumanMessage(content=query),
    ]
    sources: list[str] = []

    for _ in range(5):
        response = _llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for call in response.tool_calls:
            tool_fn = _tool_map.get(call["name"])
            if tool_fn is None:
                tool_result = f"Unknown tool: {call['name']}"
            else:
                try:
                    tool_result = tool_fn.invoke(call["args"])
                except Exception as e:
                    logger.error("Tool %s failed: %s", call["name"], e)
                    tool_result = f"Tool error: {e}"

            if isinstance(tool_result, str) and tool_result.startswith("[") and "](" in tool_result:
                sources.append(tool_result.split("](")[1].split(")")[0])

            messages.append(
                ToolMessage(content=str(tool_result), tool_call_id=call["id"])
            )

    final_message = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls),
        None,
    )
    answer = final_message.content if final_message else "도구 검색 결과를 요약하지 못했습니다."

    return {
        "final_answer": answer,
        "sources": sources,
        "agent_used": "Tool Agent",
        "messages": [AIMessage(content=answer)],
    }


def _route_selector(state: CineMateState) -> Literal["rag", "tool"]:
    return state["route"]


def _build_graph() -> StateGraph:
    builder = StateGraph(CineMateState)
    builder.add_node("router", router_node)
    builder.add_node("rag", rag_node)
    builder.add_node("tool", tool_node)

    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", _route_selector, {"rag": "rag", "tool": "tool"})
    builder.add_edge("rag", END)
    builder.add_edge("tool", END)

    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


_graph = _build_graph()


class CineMateAgent:
    """UI/API 무관 단일 진입점. Streamlit·FastAPI·CLI 모두 이 클래스만 사용한다."""

    def run(self, query: str, session_id: str = "default") -> AgentResponse:
        config = {"configurable": {"thread_id": session_id}}
        final_state = _graph.invoke(
            {"messages": [HumanMessage(content=query)], "query": query},
            config,
        )
        return AgentResponse(
            answer=final_state.get("final_answer", ""),
            agent_used=final_state.get("agent_used", ""),
            sources=final_state.get("sources", []),
            session_id=session_id,
        )
