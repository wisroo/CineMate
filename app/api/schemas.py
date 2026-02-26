"""
app/api/schemas.py

FastAPI 요청/응답 Pydantic 모델: ChatRequest, ChatResponse.
"""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    answer: str
    agent_used: str
    sources: list[str]
    session_id: str
