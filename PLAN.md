# CineMate - 설계 문서

> 디즈니 · 마블 · 픽사 세계관 분석 AI Agent  
> Multi-Agent (RAG + ReAct) · LangGraph · Streamlit

---

## 1. 프로젝트 개요

| 항목      | 내용                                                                                                                                |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 목표      | 사용자 질문을 자동 분류하여, 작품 내적 질문은 RAG로 심층 해석 제공, 외부 정보 질문은 실시간 검색 도구로 답변하는 Multi-Agent 시스템 |
| 핵심 가치 | OTT 플랫폼 고객의 세계관 이해도 향상 → 시청 유지율 및 몰입도 증대                                                                   |
| 현재 단계 | Streamlit 기반 프로토타입 (검증용)                                                                                                  |
| 최종 목표 | `core/` + `graph/` 레이어를 그대로 가져가 FastAPI 백엔드에 연동하여 실서비스 배포                                                   |

---

## 2. 시스템 아키텍처

```
[사용자 입력 - Streamlit / FastAPI / CLI 등 어떤 UI든 가능]
                     ↓
         ┌───────────────────────┐
         │   CineMateAgent.run() │  ← 단일 진입점 (UI 무관)
         │   (graph/agent_graph) │
         └──────────┬────────────┘
                    │
            ┌───────┴────────┐
            ▼                ▼
        "rag"             "tool"
            ↓                ↓
    ┌───────────────┐  ┌──────────────────┐
    │  RAG Node     │  │  ReAct Tool Node │
    │               │  │                  │
    │  ChromaDB     │  │  Wikipedia Tool  │
    │  검색 →       │  │  Tavily Tool     │
    │  CoT 프롬프트 │  │  TMDB Tool       │
    └───────┬───────┘  └────────┬─────────┘
            └──────────┬────────┘
                       ↓
              AgentResponse(
                answer, agent_used, sources
              )
```

### LangGraph 노드 및 엣지

```
START
  └─→ router_node     (질문 분류: "rag" | "tool")
        ├─→ rag_node  (ChromaDB 검색 + CoT LLM 호출)  ─→ END
        └─→ tool_node (ReAct: 도구 선택 + 실행)        ─→ END
```

**Memory**: `MemorySaver` checkpointer로 `thread_id` 기반 멀티턴 대화 상태 보존

---

## 3. 프로젝트 구조 (확장성 기반 설계)

```
CineMate/
│
├── core/                        # ✅ 비즈니스 로직 (UI/API 완전 독립)
│   ├── __init__.py
│   ├── rag_pipeline.py          # 문서 로드 / 청킹 / ChromaDB / Retriever
│   ├── prompts.py               # 모든 프롬프트 템플릿 (Router, RAG, Tool)
│   └── tools.py                 # @tool 정의 (Wikipedia, Tavily, TMDB)
│
├── graph/                       # ✅ Agent 로직 (UI/API 완전 독립)
│   ├── __init__.py
│   ├── agent_graph.py           # State, 노드, 엣지, 그래프 컴파일
│   └── schemas.py               # AgentResponse 등 공유 데이터 모델
│
├── data/
│   ├── raw/                     # 원본 수집 데이터
│   │   ├── marvel/
│   │   └── pixar/
│   └── vectorstore/             # ChromaDB 저장소 (gitignore)
│
├── scripts/
│   ├── constants.py             # MovieConfig TypedDict + 수집 관련 상수
│   ├── movies.py                # 수집 대상 영화 목록 (MOVIES)
│   ├── fetchers.py              # Fetcher Protocol + TMDBFetcher + WikipediaFetcher
│   └── ingest_data.py           # 수집 오케스트레이터 + CLI (argparse)
│
├── app/                         # 서비스 레이어 (교체 가능)
│   ├── streamlit/               # [현재] 테스트 UI
│   │   └── main.py
│   └── api/                     # [미래] FastAPI 백엔드 (선택)
│       ├── __init__.py
│       ├── main.py              # FastAPI app, lifespan
│       ├── routes/
│       │   └── chat.py          # POST /v1/chat
│       └── schemas.py           # Pydantic Request/Response 모델
│
├── docker/                      # 배포 설정
│   ├── Dockerfile.streamlit
│   ├── Dockerfile.api
│   └── docker-compose.yml
│
├── tests/                       # 단위/통합 테스트
│   ├── test_rag_pipeline.py
│   ├── test_agent_graph.py
│   └── test_tools.py
│
├── .env.example
├── .env                         # 실제 API 키 (gitignore)
├── requirements.txt
├── requirements-dev.txt         # pytest, black, ruff 등
└── README.md
```

### 레이어 역할 분리 원칙

| 레이어        | 위치                         | 역할                  | 외부 의존              |
| ------------- | ---------------------------- | --------------------- | ---------------------- |
| 비즈니스 로직 | `core/`, `graph/`            | Agent 실행, RAG, 도구 | ❌ 없음 (LangChain만)  |
| 서비스 레이어 | `app/streamlit/`, `app/api/` | 요청 수신 · 응답 반환 | Streamlit 또는 FastAPI |
| 데이터 레이어 | `data/`, `scripts/`          | 수집 · 저장 · 임베딩  | ChromaDB               |

---

## 4. 핵심 인터페이스 설계 (이식성 핵심)

`core/`와 `graph/`는 UI에 무관하게 동일한 인터페이스를 제공합니다.

```python
# graph/schemas.py
from dataclasses import dataclass

@dataclass
class AgentResponse:
    answer: str
    agent_used: str          # "RAG Agent" | "Tool Agent"
    sources: list[str]       # 출처 문서/URL 목록
    session_id: str

# graph/agent_graph.py
class CineMateAgent:
    def run(self, query: str, session_id: str = "default") -> AgentResponse:
        """UI/API 불문 동일하게 사용 가능한 단일 진입점"""
        ...
```

**Streamlit에서 사용:**

```python
# app.py
agent = CineMateAgent()
response = agent.run(user_input, session_id=st.session_state.session_id)
st.write(response.answer)
```

**FastAPI로 확장 시 (코드 변경 없음):**

```python
# app/api/routes/chat.py
agent = CineMateAgent()

@router.post("/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    response = agent.run(request.message, session_id=request.session_id)
    return ChatResponse(answer=response.answer, agent_used=response.agent_used)
```

---

## 5. 데이터 수집 전략

초기 구축 시 방법별 장단점을 고려하여 선택합니다.

### 방법 비교

| 방법               | 속도         | 품질          | 비용   | 적합한 경우             |
| ------------------ | ------------ | ------------- | ------ | ----------------------- |
| Wikipedia API      | ⚡ 매우 빠름 | 보통          | 무료   | 빠른 프로토타입 구축    |
| TMDB API           | ⚡ 빠름      | 높음 (구조화) | 무료   | 영화 메타데이터, 줄거리 |
| IMDb 웹 스크래핑   | 보통         | 높음          | 무료   | 리뷰, 트리비아          |
| 수동 큐레이션      | 느림         | 매우 높음     | 인건비 | 심층 분석 문서          |
| PDF 로드           | 보통         | 매우 높음     | 무료   | 학술 논문, 비평 기사    |
| YouTube Transcript | 보통         | 중간          | 무료   | 영상 리뷰, 해설         |

### 권장 전략 (단계별)

```
Phase 1 (현재): TMDB API + Wikipedia API
  → ingest_data.py에서 자동 수집, data/raw/ 저장

Phase 2 (선택): PDF + 수동 큐레이션
  → data/raw/curated/ 폴더에 txt/pdf 파일 추가만 하면 자동 적재

Phase 3 (확장): 웹 스크래핑
  → scripts/scrapers/ 폴더에 scraper 추가
```

### 데이터 소스 추상화 인터페이스

두 레이어의 역할이 다르므로 인터페이스를 분리한다.

**RAG 소비 인터페이스 — `core/rag_pipeline.py`**

RAG 파이프라인이 이미 저장된 데이터를 읽는 방법을 추상화한다.
`core/`는 LangChain 의존성만 허용하므로, 외부 API 라이브러리(`requests` 등)를 사용하는
수집 클래스는 이 인터페이스를 구현할 수 없다.

```python
# core/rag_pipeline.py
class DataSource(ABC):
    """RAG 파이프라인이 문서를 읽는 인터페이스. 새 저장 포맷 추가 시 구현한다."""
    @abstractmethod
    def fetch(self, movie_id: str) -> str: ...

class LocalFileSource(DataSource):  # data/raw/ 로컬 파일 읽기
    def fetch(self, movie_id: str) -> str: ...
```

**수집 인터페이스 — `scripts/fetchers.py`**

외부 API 또는 스크래퍼에서 원본 텍스트를 가져와 `data/raw/`에 저장하는 역할.
`scripts/` 레이어에서만 사용되며 RAG 파이프라인과 무관하다.

```python
# scripts/fetchers.py
class Fetcher(Protocol):
    """외부 소스에서 영화 텍스트를 수집하는 인터페이스."""
    def fetch(self, movie: MovieConfig) -> str: ...

class TMDBFetcher:          # TMDB API → 구조화된 메타데이터
    def fetch(self, movie: MovieConfig) -> str: ...

class WikipediaFetcher:     # Wikipedia → 줄거리/제작 정보
    def fetch(self, movie: MovieConfig) -> str: ...

# scripts/ingest_data.py에서 조합하여 사용
fetchers: list[Fetcher] = [TMDBFetcher(), WikipediaFetcher()]
```

### 수집 대상 영화 목록 (초기)

| 시리즈 | 영화                    | 수집 방법        |
| ------ | ----------------------- | ---------------- |
| Marvel | Avengers: Endgame       | TMDB + Wikipedia |
| Marvel | Black Panther           | TMDB + Wikipedia |
| Marvel | Spider-Man: No Way Home | TMDB + Wikipedia |
| Marvel | Thor: Ragnarok          | TMDB + Wikipedia |
| Pixar  | Inside Out 2            | TMDB + Wikipedia |
| Pixar  | Soul                    | TMDB + Wikipedia |
| Pixar  | Coco                    | TMDB + Wikipedia |

---

## 6. LangGraph State 설계

```python
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class CineMateState(TypedDict):
    messages: Annotated[list, add_messages]   # 전체 대화 히스토리 (멀티턴)
    query: str                                 # 현재 사용자 질문
    route: Literal["rag", "tool"]              # 라우터 분류 결과
    retrieved_context: str                     # RAG 검색 결과 문서들
    agent_used: str                            # "RAG Agent" | "Tool Agent"
    sources: list[str]                         # 출처 목록
    final_answer: str                          # 최종 응답
```

---

## 7. 프롬프트 엔지니어링

### ROUTER_PROMPT (라우팅 정확도 최대화)

```
당신은 영화 질문을 분류하는 라우터입니다.

"rag"  : 줄거리, 캐릭터 심리, 결말 해석, 세계관 설명, 장면 분석
"tool" : 최신 개봉일, 박스오피스, 배우 출연작/나이, 시리즈 차기작 정보

예시)
"엔드게임에서 토니가 희생한 이유?" → rag
"마블 2025년 개봉 예정작은?"     → tool
"코코에서 헥터의 진짜 정체는?"   → rag

질문: {query}
"rag" 또는 "tool" 중 하나만 출력하세요.
```

### RAG_SYSTEM_PROMPT (Role + CoT + Few-shot)

```
[ROLE]
당신은 디즈니, 마블, 픽사 세계관의 수석 스토리텔러 겸 영화 분석가 CineMate입니다.

[CHAIN OF THOUGHT - 반드시 이 순서로 추론하세요]
① [사실 확인]   Context에서 질문 관련 사실을 먼저 추출하세요.
② [캐릭터 분석] 인물의 심리적 동기나 상황의 의미를 추론하세요.
③ [세계관 연결] 다른 작품 또는 시리즈 전체 흐름과 연결 지점을 찾으세요.
④ [핵심 통찰]   위 분석을 종합하여 깊이 있는 최종 해석을 제시하세요.

[FEW-SHOT EXAMPLE]
Q: 소울(Soul)에서 22번이 지구에 가고 싶지 않았던 진짜 이유는?
A: ①사실: 22번은 수백 년간 지구행을 거부했고, 수많은 멘토의 설득도 실패했습니다.
②분석: 거부는 무능함이 아닌 '삶이 의미 있을 것'이라는 기대에 대한 두려움입니다.
③연결: 조의 꿈 집착과 대비되어 "꿈이 삶의 목적이 아닐 수 있다"는 주제를 강화합니다.
④통찰: 삶의 의미는 거창한 목적이 아닌 순간의 감각과 경험 자체임을 보여줍니다.

[CONTEXT]
{context}

[QUESTION]
{question}
```

---

## 8. Streamlit UI 설계

```
┌─────────────────────────────────────────────────┐
│  🎬 CineMate            [사이드바]               │
│  ─────────────────────────────────────────────  │
│  사이드바:                                        │
│  · 적재된 영화 목록 (7편)                         │
│  · 질문 예시 버튼 → 클릭 시 입력창 자동 채움      │
│  · 마지막 응답의 에이전트 경로 표시               │
│                                                   │
│  메인:                                            │
│  [채팅 히스토리 - st.chat_message]                │
│  [💬 입력창 - st.chat_input]                      │
│  [⏳ 스피너 - st.spinner]                         │
│  [배지: 🔍 RAG Agent | 🌐 Tool Agent]             │
│  [출처 expander - 검색된 문서/URL 목록]            │
└─────────────────────────────────────────────────┘
```

---

## 9. FastAPI 확장 설계 (Phase 2)

`core/`와 `graph/`는 변경 없이 그대로 사용합니다.

```python
# app/api/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from graph.agent_graph import CineMateAgent

agent: CineMateAgent

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent = CineMateAgent()   # 서버 시작 시 1회 초기화
    yield

app = FastAPI(lifespan=lifespan)
```

```python
# app/api/routes/chat.py
@router.post("/v1/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    response = agent.run(request.message, session_id=request.session_id)
    return ChatResponse(
        answer=response.answer,
        agent_used=response.agent_used,
        sources=response.sources,
    )
```

---

## 10. Docker 배포 설계

### docker-compose.yml 구조

```yaml
services:
  streamlit: # 프로토타입 UI
    build:
      context: .
      dockerfile: docker/Dockerfile.streamlit
    ports: ["8501:8501"]
    volumes: ["./data:/app/data"]
    env_file: .env

  api: # FastAPI 백엔드 (Phase 2)
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    ports: ["8000:8000"]
    volumes: ["./data:/app/data"]
    env_file: .env
```

---

## 11. 기술 스택

| 구분            | 기술                     | 비고                    |
| --------------- | ------------------------ | ----------------------- |
| LLM             | GPT-4o-mini              | 비용 효율 + 충분한 성능 |
| Embedding       | text-embedding-3-small   | 속도/비용 균형          |
| Vector DB       | ChromaDB (local persist) | 설치 간편, 로컬 완결    |
| Agent Framework | LangChain + LangGraph    | 필수 요건               |
| Memory          | LangGraph MemorySaver    | 멀티턴 대화             |
| UI              | Streamlit                | 현재 단계               |
| Backend         | FastAPI                  | Phase 2 (선택)          |
| Data 수집       | TMDB API + Wikipedia     | 무료, 빠른 구축         |
| 외부 검색 Tool  | Tavily + Wikipedia Tool  | ReAct 필수 요건         |
| 환경변수        | python-dotenv            | API 키 보안 관리        |
| 배포            | Docker + docker-compose  | 선택 요건               |

---

## 12. 개발 일정

### Day 1: 기반 공사 + RAG 파이프라인

| 시간 | 작업                                                            |
| ---- | --------------------------------------------------------------- |
| 오전 | requirements.txt, .env.example, 폴더 구조 생성                  |
| 오전 | `graph/schemas.py` - AgentResponse 데이터 모델 정의             |
| 오후 | `scripts/ingest_data.py` - TMDB API + Wikipedia로 영화 7편 수집 |
| 오후 | `core/rag_pipeline.py` - load / split / embed / persist 구현    |
| 오후 | 단위 테스트: `retriever.invoke("토니 스타크 희생")` 결과 확인   |

### Day 2: Multi-Agent + LangGraph

| 시간 | 작업                                                                   |
| ---- | ---------------------------------------------------------------------- |
| 오전 | `core/prompts.py` - Router, RAG (CoT+Few-shot), Tool 프롬프트          |
| 오전 | `core/tools.py` - `@tool` wikipedia_search, tavily_search, tmdb_search |
| 오후 | `graph/agent_graph.py` - State, router_node, rag_node, tool_node       |
| 오후 | LangGraph 엣지 연결 + MemorySaver 적용                                 |
| 오후 | 통합 테스트 (5가지 질문 시나리오 + 멀티턴 확인)                        |

### Day 3: Streamlit UI + 마무리

| 시간 | 작업                                       |
| ---- | ------------------------------------------ |
| 오전 | `app.py` - 채팅 UI, 사이드바, 라우팅 배지  |
| 오전 | `st.session_state`로 thread_id 관리        |
| 오후 | Dockerfile, docker-compose.yml 작성 (선택) |
| 오후 | README.md 업데이트, 코드 정리              |
| 오후 | 과제 보고서 작성                           |

---

## 13. 평가 요건 체크리스트

| 요건                                   | 구현 위치                                | 상태 |
| -------------------------------------- | ---------------------------------------- | ---- |
| Prompt Engineering (Role/CoT/Few-shot) | `core/prompts.py`                        | 📋   |
| LangGraph Multi-Agent                  | `graph/agent_graph.py`                   | 📋   |
| ReAct Tool Agent                       | `graph/agent_graph.py` + `core/tools.py` | 📋   |
| 멀티턴 대화 Memory                     | LangGraph MemorySaver                    | 📋   |
| 원본 데이터 수집 및 전처리             | `scripts/ingest_data.py`                 | 📋   |
| ChromaDB Vector DB                     | `core/rag_pipeline.py`                   | 📋   |
| RAG 지식 검색                          | `graph/agent_graph.py` rag_node          | 📋   |
| Streamlit UI                           | `app.py`                                 | 📋   |
| FastAPI 백엔드                         | `app/api/` (선택)                        | 📋   |
| Docker 배포                            | `docker/` (선택)                         | 📋   |
| 환경변수 관리                          | `.env` + `python-dotenv`                 | 📋   |
| 파일 모듈화                            | 전체 구조                                | 📋   |

---

## 14. 차별화 포인트

1. **Dual-Agent 자동 분기**: 질문 성격에 따라 RAG ↔ ReAct 자동 선택 (단순 RAG/Tool과 차별화)
2. **도메인 특화 CoT 프롬프트**: 영화 분석 흐름(사실→심리→세계관→통찰)에 최적화
3. **라우팅 투명성**: UI에서 어떤 에이전트가 답변했는지 표시 (신뢰도·UX 향상)
4. **완전한 레이어 분리**: `core/`+`graph/`를 그대로 FastAPI에 붙일 수 있는 이식성
5. **다중 데이터 소스 추상화**: TMDB, Wikipedia, 로컬 파일 등 소스 교체/추가 용이
