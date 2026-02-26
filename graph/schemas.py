from dataclasses import dataclass, field


@dataclass
class AgentResponse:
    answer: str
    agent_used: str  # "RAG Agent" | "Tool Agent"
    sources: list[str]
    session_id: str
