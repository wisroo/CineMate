# CineMate

Ultimate Mate for your Cinema — 디즈니·마블·픽사 세계관 분석 AI Agent.

## 실행 환경: uv

이 프로젝트는 [uv](https://docs.astral.sh/uv/)를 Python 패키지·실행 환경으로 사용합니다.

### 사전 요구사항

- [uv 설치](https://docs.astral.sh/uv/getting-started/installation/) (권장: `curl -LsSf https://astral.sh/uv/install.sh | sh`)

### 설치 및 실행

```bash
# 1. 가상환경 생성 + 의존성 설치 (lockfile 기준)
uv sync

# 2. 환경 변수 설정 (.env에 API 키 입력)
cp .env.example .env
# Azure OpenAI(AOAI_*) 또는 OPENAI_API_KEY, TMDB_API_KEY, TAVILY_API_KEY 값 편집

# 3. 데이터 수집 (TMDB + Wikipedia → data/raw/)
uv run python scripts/ingest_data.py

# 4. ChromaDB 벡터스토어 빌드
uv run python -c "from core.rag_pipeline import RAGPipeline; RAGPipeline().build()"

# 5. 테스트
uv run pytest tests/test_rag_pipeline.py -v
```

### uv 명령 요약

| 명령 | 설명 |
|------|------|
| `uv sync` | lockfile 기준으로 의존성 설치 (dev 포함) |
| `uv sync --no-dev` | 프로덕션 의존성만 설치 |
| `uv run <cmd>` | 프로젝트 가상환경에서 명령 실행 |
| `uv add <pkg>` | 패키지 추가 후 lock 갱신 |
| `uv add --dev <pkg>` | 개발 전용 패키지 추가 |

의존성은 `pyproject.toml`과 `uv.lock`으로 관리됩니다. `requirements.txt`는 사용하지 않습니다.

### 환경 변수

- **Azure OpenAI (사내망 AOAI)**: `.env`에 `AOAI_ENDPOINT`, `AOAI_API_KEY`, `AOAI_DEPLOY_EMBED_3_SMALL`(임베딩 배포명)을 넣으면 Azure OpenAI를 사용합니다. 선택으로 `AOAI_API_VERSION`(기본 `2024-02-01`)을 지정할 수 있습니다.
- **OpenAI 직연결**: AOAI_* 를 쓰지 않을 때는 `OPENAI_API_KEY`만 설정하면 됩니다.
- **TMDB API 키 발급 시 "Application URL"**: 개발 단계에서는 실제 서비스 URL이 없어도 됩니다. 아래 중 하나를 넣으면 됩니다.
  - `http://localhost:8501` (로컬 Streamlit 기준)
  - `http://localhost:3000` (로컬 개발 서버)
  - `https://www.example.com` (플레이스홀더)
  - 나중에 배포 URL이 정해지면 TMDB 설정에서 URL을 수정할 수 있습니다.

### 참고

- `uv.lock`은 버전 재현을 위해 저장소에 포함하는 것을 권장합니다.
- macOS 26 x86_64 등 일부 환경에서는 ChromaDB의 선택 의존성 `onnxruntime` 휠이 없어, `pyproject.toml`에서 해당 플랫폼에서 제외하도록 설정해 두었습니다. OpenAI 임베딩만 사용하므로 동작에는 문제가 없습니다.
