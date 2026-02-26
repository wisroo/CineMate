---
description: CineMate 프로젝트 레이어 구조 및 모듈 배치 원칙
---

# 프로젝트 레이어 아키텍처

## 레이어 역할 분리 (절대 원칙)

| 레이어        | 위치                         | 허용 의존성               |
| ------------- | ---------------------------- | ------------------------- |
| 비즈니스 로직 | `core/`, `graph/`            | LangChain, LangGraph만    |
| 서비스 레이어 | `app/streamlit/`, `app/api/` | Streamlit 또는 FastAPI    |
| 데이터 레이어 | `data/`, `scripts/`          | ChromaDB, 수집 라이브러리 |

## 파일 배치 규칙 (모드별 구조)

- 에이전트 모드 분리: `graph/agent_graph.py` (팝콘 모드) 및 `graph/director_graph.py` (디렉터 모드)
- Agent 로직, RAG, 프롬프트, 툴 → 반드시 `core/` 또는 `graph/`
- 도구 분리: `core/tools.py`에 팝콘 모드용 `TOOLS`, 디렉터 모드용 `RESEARCHER_TOOLS` 분리
- 프롬프트 관리: `core/prompts.py`에 역할별 프롬프트 정의 (RESEARCHER, ANALYST, EDITOR, REVIEWER)
- 공유 데이터 모델(dataclass, TypedDict) → `graph/schemas.py` (ChatState, DeepState)
- Streamlit 관련 코드 → `app/streamlit/`에만 (모드 선택 UI 포함)
- 데이터 수집/초기화 스크립트 → `scripts/`

## 신규 파일 추가 시 체크

- `core/` 또는 `graph/`에 `import streamlit`, `import fastapi` 절대 금지
- 새 데이터 소스 추가 → `core/rag_pipeline.py`의 `DataSource` 인터페이스 구현
- 새 Tool 추가 → `core/tools.py`에 `@tool` 데코레이터로 추가 (`rag_search` 처럼 내부 파이프라인 래핑 포함)
- 새 서비스 레이어 추가 → `app/` 하위에 새 디렉토리 생성, `graph/agent_graph.py`의 `CineMateAgent` 재사용
