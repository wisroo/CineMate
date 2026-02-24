"""
POST /v1/chat 엔드포인트.
"""

from fastapi import APIRouter, Request

from app.api.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/v1/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    agent = request.app.state.agent
    resp = agent.run(body.message, session_id=body.session_id)
    return ChatResponse(
        answer=resp.answer,
        agent_used=resp.agent_used,
        sources=resp.sources,
        session_id=resp.session_id,
    )
