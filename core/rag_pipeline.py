"""
core/rag_pipeline.py

RAG 파이프라인: DataSource 추상화, 문서 적재, ChromaDB 임베딩, Retriever 반환.
"""

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings

load_dotenv()

logger = logging.getLogger(__name__)


def _create_embeddings():
    """AOAI_* (Azure OpenAI) 또는 OPENAI_API_KEY 기준으로 임베딩 클라이언트 생성."""
    aoai_key = os.getenv("AOAI_API_KEY")
    aoai_endpoint = os.getenv("AOAI_ENDPOINT")
    if aoai_key and aoai_endpoint:
        return AzureOpenAIEmbeddings(
            azure_endpoint=aoai_endpoint.rstrip("/"),
            api_key=aoai_key,
            model=os.getenv("AOAI_DEPLOY_EMBED_3_SMALL", "text-embedding-3-small"),
            openai_api_version=os.getenv("AOAI_API_VERSION", "2024-02-01"),
        )
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIEmbeddings(model="text-embedding-3-small")
    raise RuntimeError(
        "Set either AOAI_API_KEY + AOAI_ENDPOINT (Azure) or OPENAI_API_KEY in .env"
    )


_embeddings = _create_embeddings()


def get_embeddings():
    """테스트 등에서 동일 임베딩 설정을 쓸 때 사용. RAGPipeline과 같은 인스턴스."""
    return _embeddings


_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=80,
    separators=["\n\n", "\n", ".", " "],
)


class DataSource(ABC):
    """모든 데이터 소스의 공통 인터페이스."""

    @abstractmethod
    def fetch(self, movie_id: str) -> str:
        """영화 ID(또는 제목)를 받아 텍스트 반환."""
        ...


class LocalFileSource(DataSource):
    """data/raw/ 하위 txt 파일을 읽어 반환."""

    def __init__(self, raw_dir: str = "data/raw") -> None:
        self.raw_dir = Path(raw_dir)

    def fetch(self, movie_id: str) -> str:
        """movie_id는 상대 경로 (예: 'marvel/avengers_endgame')."""
        path = self.raw_dir / f"{movie_id}.txt"
        if not path.exists():
            raise FileNotFoundError(f"Raw file not found: {path}")
        return path.read_text(encoding="utf-8")


def _load_documents_from_dir(raw_dir: Path) -> list[Document]:
    """data/raw/ 하위 모든 txt 파일을 Document 리스트로 로드."""
    docs: list[Document] = []

    for txt_file in raw_dir.rglob("*.txt"):
        series = txt_file.parent.name
        movie_title = txt_file.stem.replace("_", " ").title()
        text = txt_file.read_text(encoding="utf-8")

        if not text.strip():
            logger.warning("Empty file skipped: %s", txt_file)
            continue

        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": txt_file.name,
                    "movie": movie_title,
                    "series": series,
                },
            )
        )

    logger.info("Loaded %d raw documents from %s", len(docs), raw_dir)
    return docs


class RAGPipeline:
    def __init__(self, persist_dir: str = "data/vectorstore") -> None:
        self.persist_dir = persist_dir

    def build(self, raw_dir: str = "data/raw") -> None:
        """load → split → embed → persist 전체 파이프라인 1회 실행."""
        raw_path = Path(raw_dir)
        if not raw_path.exists():
            raise RuntimeError(
                f"raw_dir does not exist: {raw_dir}. Run ingest_data.py first."
            )

        docs = _load_documents_from_dir(raw_path)
        if not docs:
            raise RuntimeError(
                f"No txt files found in {raw_dir}. Run ingest_data.py first."
            )

        chunks = _splitter.split_documents(docs)
        logger.info("Split into %d chunks", len(chunks))

        Chroma.from_documents(
            documents=chunks,
            embedding=_embeddings,
            persist_directory=self.persist_dir,
        )
        logger.info("ChromaDB persisted to %s", self.persist_dir)

    def get_retriever(self, k: int = 4) -> VectorStoreRetriever:
        """기존 vectorstore 로드 후 retriever 반환."""
        vectorstore = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=_embeddings,
        )
        count = vectorstore._collection.count()
        if count == 0:
            raise RuntimeError(
                f"Vector store at '{self.persist_dir}' is empty. Run RAGPipeline.build() first."
            )
        logger.info("Loaded vectorstore with %d chunks", count)
        return vectorstore.as_retriever(search_kwargs={"k": k})
