"""
RAG 파이프라인 단위 테스트.

벡터스토어 의존 테스트: data/vectorstore 가 비어 있으면 skip 됩니다.
  - 먼저 실행: uv run python scripts/ingest_data.py
  - 그다음:   uv run python -c "from core.rag_pipeline import RAGPipeline; RAGPipeline().build()"

실행: uv run pytest tests/test_rag_pipeline.py -v
"""

import pytest

from core.rag_pipeline import LocalFileSource, RAGPipeline

_VECTORSTORE_SKIP_MSG = (
    "Vector store not built. Run: uv run python scripts/ingest_data.py && "
    'uv run python -c "from core.rag_pipeline import RAGPipeline; RAGPipeline().build()"'
)


@pytest.fixture(scope="module")
def retriever():
    try:
        pipeline = RAGPipeline()
        return pipeline.get_retriever(k=4)
    except RuntimeError as e:
        if "empty" in str(e).lower() or "Run RAGPipeline.build" in str(e):
            pytest.skip(_VECTORSTORE_SKIP_MSG)
        raise


@pytest.fixture(scope="module")
def vectorstore_count():
    from langchain_chroma import Chroma

    from core.rag_pipeline import get_embeddings

    vs = Chroma(
        persist_directory="data/vectorstore",
        embedding_function=get_embeddings(),
    )
    return vs._collection.count()


def test_retriever_returns_results(retriever):
    """토니 스타크 희생 관련 쿼리에 대해 문서가 반환되어야 한다."""
    docs = retriever.invoke("토니 스타크 희생")
    assert len(docs) >= 1, "retriever가 결과를 반환하지 않았습니다."


def test_retriever_result_has_content(retriever):
    """반환된 문서에 실제 텍스트가 있어야 한다."""
    docs = retriever.invoke("Tony Stark sacrifice Avengers Endgame")
    for doc in docs:
        assert doc.page_content.strip(), "빈 page_content가 반환되었습니다."


def test_retriever_result_has_required_metadata(retriever):
    """반환된 모든 문서에 source, movie, series 메타데이터가 있어야 한다."""
    docs = retriever.invoke("Tony Stark sacrifice Avengers Endgame")
    for doc in docs:
        assert "source" in doc.metadata, f"source 메타데이터 없음: {doc.metadata}"
        assert "movie" in doc.metadata, f"movie 메타데이터 없음: {doc.metadata}"
        assert "series" in doc.metadata, f"series 메타데이터 없음: {doc.metadata}"


def test_chunk_count_is_sufficient(vectorstore_count):
    """ChromaDB 총 청크 수가 200개 이상이어야 한다 (data-pipeline 기준)."""
    if vectorstore_count == 0:
        pytest.skip(_VECTORSTORE_SKIP_MSG)
    assert vectorstore_count >= 200, (
        f"청크 수가 부족합니다: {vectorstore_count}개 (기준: 200개 이상). "
        "ingest_data.py를 재실행하거나 수집 데이터를 확인하세요."
    )


def test_pixar_query_returns_results(retriever):
    """픽사 관련 쿼리에 대해 문서가 반환되어야 한다."""
    docs = retriever.invoke("Soul 22번 지구에 가고 싶지 않은 이유")
    assert len(docs) >= 1


def test_local_file_source_skip_missing(tmp_path):
    """존재하지 않는 파일 접근 시 FileNotFoundError가 발생해야 한다."""
    source = LocalFileSource(raw_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        source.fetch("nonexistent_movie")
