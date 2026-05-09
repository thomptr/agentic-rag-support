import pytest

from src.db.connection import get_vector_store
from src.rag.ingest import ingest_domain

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def vector_store():
    return get_vector_store()


def test_ingest_billing_domain_succeeds(vector_store):
    count = ingest_domain("billing", vector_store)
    assert count >= 0  # 0 if already ingested, >0 on first run


def test_ingested_chunks_are_searchable(vector_store):
    ingest_domain("billing", vector_store)
    results = vector_store.similarity_search("pricing plans", k=3, filter={"domain": "billing"})
    assert len(results) > 0
    for doc in results:
        assert doc.metadata.get("domain") == "billing"


def test_ingest_is_idempotent(vector_store):
    ingest_domain("billing", vector_store)
    count_second_run = ingest_domain("billing", vector_store)
    assert count_second_run == 0  # Already ingested — skip


def test_all_domains_ingestible(vector_store):
    for domain in ("billing", "technical", "account"):
        count = ingest_domain(domain, vector_store)
        assert count >= 0


def test_chunk_metadata_contains_domain(vector_store):
    ingest_domain("billing", vector_store)
    results = vector_store.similarity_search("invoice", k=5, filter={"domain": "billing"})
    assert len(results) > 0
    for doc in results:
        assert "domain" in doc.metadata
        assert "title" in doc.metadata
        assert "source_file" in doc.metadata
