"""
FastAPI 애플리케이션 진입점.

실행:
  uv run uvicorn app.api.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from graph.agent_graph import CineMateAgent

from .routes.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.agent = CineMateAgent()
    yield


app = FastAPI(
    title="CineMate API",
    description="디즈니·마블·픽사 세계관 분석 AI Agent REST API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(chat_router)
