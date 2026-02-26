---
description: core/와 graph/의 이식성 원칙 - UI 교체 없이 실서비스 연동 가능하도록
globs: core/**/*.py,graph/**/*.py
---

# 비즈니스 로직 이식성 원칙

## CineMateAgent - 단일 진입점 패턴

`graph/agent_graph.py`의 `CineMateAgent.run()`이 유일한 외부 진입점입니다.
Streamlit, FastAPI, CLI 등 어떤 호출부도 이 메서드만 사용합니다. 두 가지 모드(chat, director)를 지원합니다.

```python
# ✅ GOOD - 타입이 명확한 단일 진입점 (모드 인자 추가)
class CineMateAgent:
    def run(self, query: str, mode: Literal["chat", "director"] = "chat", session_id: str = "default") -> AgentResponse:
        ...

# ❌ BAD - 반환 타입이 dict인 경우 (호출부에서 키를 알아야 함)
def run_agent(query: str) -> dict:
    ...
```

## 반환 타입은 항상 dataclass 또는 TypedDict

```python
# ✅ GOOD - graph/schemas.py에 정의된 타입 사용
from graph.schemas import AgentResponse

@dataclass
class AgentResponse:
    answer: str
    agent_used: str
    sources: list[str]
    session_id: str

# ❌ BAD - raw dict 반환
return {"answer": "...", "agent_used": "..."}
```

## UI 프레임워크 의존성 차단

```python
# ❌ BAD - core/ 또는 graph/ 안에서 절대 금지
import streamlit as st
from fastapi import HTTPException

# ✅ GOOD - 예외는 표준 Python 예외로
raise ValueError("Invalid query")
raise RuntimeError("Vector store not initialized")
```

## 세션 관리는 session_id 문자열로만

```python
# ✅ GOOD - 어떤 환경에서도 동작
agent.run(query, mode="chat", session_id="user-abc-123")

# ❌ BAD - 특정 프레임워크 객체를 직접 전달
agent.run(query, session=streamlit_session)
```
