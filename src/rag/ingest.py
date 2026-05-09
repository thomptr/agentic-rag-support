import hashlib
from pathlib import Path

from langchain_core.documents import Document

from src.db.connection import get_vector_store
from src.rag.chunking import chunk_text

KB_ROOT = Path(__file__).parent.parent.parent / "docs" / "knowledge_base"
DOMAINS = ["billing", "technical", "account"]


def _doc_id(source_file: str) -> str:
    return hashlib.md5(source_file.encode()).hexdigest()


def ingest_domain(domain: str, vector_store) -> int:
    domain_dir = KB_ROOT / domain
    if not domain_dir.exists():
        print(f"[ingest] No directory for domain: {domain}")
        return 0

    ingested = 0
    for md_file in sorted(domain_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        title = md_file.stem.replace("-", " ").title()
        source = str(md_file.relative_to(KB_ROOT.parent.parent))
        doc_id = _doc_id(source)

        existing = vector_store.similarity_search(
            " ",
            k=1,
            filter={"source_file": source},
        )
        if existing:
            print(f"[ingest] Skipping (already ingested): {source}")
            continue

        chunks = chunk_text(content)
        documents = [
            Document(
                page_content=chunk,
                metadata={
                    "domain": domain,
                    "doc_id": doc_id,
                    "title": title,
                    "source_file": source,
                    "chunk_index": i,
                },
            )
            for i, chunk in enumerate(chunks)
        ]
        vector_store.add_documents(documents)
        print(f"[ingest] Ingested {len(chunks)} chunks from {source}")
        ingested += len(chunks)

    return ingested


def ingest_all() -> None:
    vector_store = get_vector_store()
    total = 0
    for domain in DOMAINS:
        total += ingest_domain(domain, vector_store)
    print(f"[ingest] Complete. Total chunks: {total}")


if __name__ == "__main__":
    ingest_all()
