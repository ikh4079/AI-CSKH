import json
from typing import Any

from app.core.config import get_settings
from app.utils.text import normalize_text

settings = get_settings()


class RAGService:
    def __init__(self) -> None:
        self.index = None
        self._faq_cache: list[dict[str, str]] | None = None

    def _load_faq_items(self) -> list[dict[str, str]]:
        if self._faq_cache is not None:
            return self._faq_cache

        faq_path = settings.resolve_path(settings.faq_path)
        if not faq_path.exists():
            self._faq_cache = []
            return self._faq_cache

        self._faq_cache = json.loads(faq_path.read_text(encoding="utf-8"))
        return self._faq_cache

    def _keyword_fallback(self, query: str, top_k: int) -> list[dict[str, str]]:
        query_tokens = set(normalize_text(query).split())
        ranked: list[tuple[int, dict[str, str]]] = []
        for item in self._load_faq_items():
            haystack = normalize_text(f"{item['question']} {item['answer']}")
            score = sum(1 for token in query_tokens if token and token in haystack)
            if score > 0:
                ranked.append((score, item))
        ranked.sort(key=lambda value: value[0], reverse=True)
        return [item for _, item in ranked[:top_k]]

    def _load_index(self):
        if self.index is not None:
            return self.index

        from llama_index.core import Document, StorageContext, VectorStoreIndex, load_index_from_storage
        from llama_index.vector_stores.faiss import FaissVectorStore

        index_path = settings.resolve_path(settings.index_dir)
        if index_path.exists():
            storage_context = StorageContext.from_defaults(persist_dir=str(index_path))
            self.index = load_index_from_storage(storage_context)
            return self.index

        faq_path = settings.resolve_path(settings.faq_path)
        if not faq_path.exists():
            return None

        payload = json.loads(faq_path.read_text(encoding="utf-8"))
        documents = [
            Document(text=item["answer"], metadata={"question": item["question"], "source": "faq"})
            for item in payload
        ]
        import faiss

        faiss_index = faiss.IndexFlatL2(1536)
        vector_store = FaissVectorStore(faiss_index=faiss_index)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        self.index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
        index_path.mkdir(parents=True, exist_ok=True)
        self.index.storage_context.persist(persist_dir=str(index_path))
        return self.index

    def retrieve(self, query: str, top_k: int = 3) -> list[Any]:
        try:
            index = self._load_index()
        except Exception:
            index = None
        if index is None:
            return []
        retriever = index.as_retriever(similarity_top_k=top_k)
        return retriever.retrieve(query)

    def format_context(self, query: str) -> str:
        docs = self.retrieve(query)
        if not docs:
            fallback_items = self._keyword_fallback(query, top_k=3)
            return "\n\n".join(
                f"FAQ gần nhất: {item['question']}\nTrả lời: {item['answer']}" for item in fallback_items
            )
        return "\n\n".join(
            f"FAQ gần nhất: {doc.metadata.get('question', 'N/A')}\nTrả lời: {doc.text}"
            for doc in docs
        )


rag_service = RAGService()
