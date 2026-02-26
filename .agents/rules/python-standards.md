---
description: CineMate Python 코딩 표준 - 타입 힌트, 환경변수, 에러 처리
globs: **/**/*.py
---

# Python 코딩 표준

## 환경변수는 반드시 .env + python-dotenv

```python
# ✅ GOOD - 모듈 상단에서 1회 로드
from dotenv import load_dotenv
import os
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set in .env")

# ❌ BAD - 하드코딩
OPENAI_API_KEY = "sk-..."
```

## 타입 힌트 필수 (TypedDict 포함)

```python
# ✅ GOOD
def get_retriever(persist_dir: str, k: int = 4) -> VectorStoreRetriever:
    ...
class DeepState(TypedDict):
    messages: Annotated[list, add_messages]
    verdict: Literal["PASS", "REVISE", ""]

# ❌ BAD
def get_retriever(persist_dir, k=4):
    ...
```

## LangChain LLM 초기화는 함수/클래스 외부에서 1회

```python
# ✅ GOOD - 모듈 레벨 싱글턴
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ❌ BAD - 호출마다 재생성 (비용·속도 낭비)
def router_node(state):
    llm = ChatOpenAI(...)
```

## 에러 처리

```python
# ✅ GOOD - 명시적 예외 + 로깅
import logging
logger = logging.getLogger(__name__)

try:
    docs = retriever.invoke(query)
except Exception as e:
    logger.error("Retrieval failed: %s", e)
    raise RuntimeError("Vector store retrieval failed") from e

# ❌ BAD - 무시
try:
    docs = retriever.invoke(query)
except:
    pass
```

## 프롬프트는 core/prompts.py에 상수로 관리

```python
# ✅ GOOD - core/prompts.py
RESEARCHER_PROMPT = """..."""
ANALYST_PROMPT = """..."""

# ❌ BAD - 노드 함수 내부에 인라인 프롬프트
def rag_node(state):
    prompt = "당신은 영화 분석가입니다..."
```
