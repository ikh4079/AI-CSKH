import json

import faiss
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.vector_stores.faiss import FaissVectorStore

from app.core.config import get_settings

settings = get_settings()


def main() -> None:
    faq_path = settings.resolve_path(settings.faq_path)
    index_path = settings.resolve_path(settings.index_dir)
    payload = json.loads(faq_path.read_text(encoding="utf-8"))
    documents = [
        Document(text=item["answer"], metadata={"question": item["question"], "source": "faq"})
        for item in payload
    ]
    faiss_index = faiss.IndexFlatL2(1536)
    vector_store = FaissVectorStore(faiss_index=faiss_index)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
    index_path.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(index_path))
    print(f"Rebuilt FAISS index at {index_path}")


if __name__ == "__main__":
    main()

