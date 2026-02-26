"""
graph/agent_graph.py

LangGraph Multi-Agent 그래프: translation → router → (rag_node | tool_agent).

그래프 흐름:
  START → translation_node → router_node
  router_node → (conditional) rag_node | tool_agent
  tool_agent → (conditional) tools_node | END
  tools_node → tool_agent

Memory:
  InMemorySaver checkpointer로 thread_id 기반 멀티턴 대화 상태를 보존한다.
"""

import logging
import os
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from core.prompts import (
    RAG_SYSTEM_PROMPT,
    ROUTER_PROMPT,
    TOOL_SYSTEM_PROMPT,
    TRANSLATION_PROMPT,
)
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


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    english_query: str
    route: Literal["rag", "tool"]
    retrieved_context: str
    agent_used: str
    sources: list[str]
    final_answer: str


def translation_node(state: ChatState) -> dict:
    """사용자의 원본 질문을 영문으로 번역하여 검색 쿼리 품질을 높인다."""
    query = state.get("query")
    if not query and state.get("messages"):
        query = str(state["messages"][-1].content)

    prompt = TRANSLATION_PROMPT.format(query=query)
    response = _llm.invoke([HumanMessage(content=prompt)])
    english_query = str(response.content).strip()
    logger.info("Translated Query: %s -> %s", query, english_query)

    return {"english_query": english_query}


def router_node(state: ChatState) -> dict:
    """질문을 분석해 'rag' 또는 'tool' 경로를 결정한다."""
    query = state.get("query")
    if not query and state.get("messages"):
        query = str(state["messages"][-1].content)

    prompt = ROUTER_PROMPT.format(query=query)
    response = _llm.invoke([HumanMessage(content=prompt)])
    raw = response.content.strip().lower()
    route: Literal["rag", "tool"] = "tool" if "tool" in raw else "rag"
    logger.info("Router decision: %s (raw=%r)", route, raw)
    return {"route": route}


def rag_node(state: ChatState) -> dict:
    """ChromaDB에서 관련 문서를 검색하고 CoT 프롬프트로 LLM 답변을 생성한다."""
    query = state.get("query")
    if not query and state.get("messages"):
        query = str(state["messages"][-1].content)

    english_query = state.get("english_query", query)

    pipeline = RAGPipeline()
    try:
        retriever = pipeline.get_retriever(k=4)
        docs = retriever.invoke(english_query)
        logger.info("RAG invoked with english_query: %s", english_query)
    except RuntimeError as e:
        logger.error("RAG retrieval failed: %s", e)
        raise

    context = "\n\n".join(doc.page_content for doc in docs)
    sources = list(
        {doc.metadata.get("source", "") for doc in docs if doc.metadata.get("source")}
    )

    prompt = RAG_SYSTEM_PROMPT.format(context=context, question=query)
    messages = state.get("messages", [])[-10:]
    invoke_msgs = [SystemMessage(content=prompt)] + messages

    response = _llm.invoke(invoke_msgs)
    answer = str(response.content)

    return {
        "retrieved_context": context,
        "final_answer": answer,
        "sources": sources,
        "agent_used": "RAG Agent",
        "messages": [AIMessage(content=answer)],
    }


def tool_agent(state: ChatState) -> dict:
    """ReAct 루프: LLM을 호출하여 도구를 선택하거나 최종 답변을 생성한다."""
    english_query = state.get("english_query", "")
    system_prompt = TOOL_SYSTEM_PROMPT
    if english_query:
        system_prompt += f"\n\nSearch keywords constraint: You MUST prioritize using '{english_query}' when translating user intent to tool arguments."

    messages = state.get("messages", [])[-10:]
    invoke_msgs = [SystemMessage(content=system_prompt)] + messages

    response = _llm_with_tools.invoke(invoke_msgs)

    result = {
        "messages": [response],
        "agent_used": "Tool Agent",
    }

    if not response.tool_calls:
        result["final_answer"] = str(response.content)

    return result


def tools_node(state: ChatState) -> dict:
    """에이전트가 선택한 도구를 실행하고 결과를 반환한다."""
    messages = state.get("messages", [])
    last_message = messages[-1]

    new_messages = []
    new_sources = state.get("sources", [])
    if new_sources is None:
        new_sources = []
    sources_copy = list(new_sources)

    for call in last_message.tool_calls:  # type: ignore
        tool_fn = _tool_map.get(call["name"])
        if tool_fn is None:
            tool_result = f"Unknown tool: {call['name']}"
        else:
            try:
                tool_result = tool_fn.invoke(call["args"])
            except Exception as e:
                logger.error("Tool %s failed: %s", call["name"], e)
                tool_result = f"Tool error: {e}"

        if (
            isinstance(tool_result, str)
            and tool_result.startswith("[")
            and "](" in tool_result
        ):
            source = tool_result.split("](")[1].split(")")[0]
            if source not in sources_copy:
                sources_copy.append(source)

        new_messages.append(
            ToolMessage(content=str(tool_result), tool_call_id=call["id"])
        )

    return {
        "messages": new_messages,
        "sources": sources_copy,
    }


def _route_selector(state: ChatState) -> Literal["rag", "tool"]:
    return state["route"]


def _should_continue(state: ChatState) -> Literal["tools_node", "end"]:
    messages = state.get("messages", [])
    last_message = messages[-1]
    if getattr(last_message, "tool_calls", None):
        return "tools_node"
    return "end"


def _build_graph() -> StateGraph:
    builder = StateGraph(ChatState)
    builder.add_node("translation_node", translation_node)
    builder.add_node("router", router_node)
    builder.add_node("rag", rag_node)
    builder.add_node("tool_agent", tool_agent)
    builder.add_node("tools_node", tools_node)

    builder.add_edge(START, "translation_node")
    builder.add_edge("translation_node", "router")
    builder.add_conditional_edges(
        "router", _route_selector, {"rag": "rag", "tool": "tool_agent"}
    )

    builder.add_conditional_edges(
        "tool_agent", _should_continue, {"tools_node": "tools_node", "end": END}
    )
    builder.add_edge("tools_node", "tool_agent")

    builder.add_edge("rag", END)

    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


_graph = _build_graph()


# 디렉터 모드 그래프 (순환 참조 방지를 위해 런타임에 import)
def _get_director_graph():
    from graph.director_graph import _director_graph

    return _director_graph


class CineMateAgent:
    """UI/API 무관 단일 진입점. Streamlit·FastAPI·CLI 모두 이 클래스만 사용한다."""

    def run(
        self,
        query: str,
        session_id: str = "default",
        mode: Literal["chat", "director"] = "chat",
    ) -> AgentResponse:
        if mode == "director":
            director_graph = _get_director_graph()
            final_state = director_graph.invoke(
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

        # mode == "chat" (팝콘 모드)
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
