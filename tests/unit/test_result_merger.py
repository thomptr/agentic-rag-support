from src.rag.result_merger import merge_results


def _make_doc(content: str, score: float, domain: str = "billing") -> dict:
    return {
        "content": content,
        "metadata": {"domain": domain, "doc_id": f"doc-{hash(content)}"},
        "score": score,
        "domain": domain,
        "source_query": "test query",
    }


class TestMergeResults:
    def test_content_hash_dedup_removes_duplicates(self):
        doc = _make_doc("Refund policy: 30 days", 0.9)
        duplicate = _make_doc("Refund policy: 30 days", 0.85)  # same content, lower score
        results = merge_results([doc, duplicate])
        assert len(results) == 1
        # Should keep the higher-score copy
        assert results[0]["score"] == 0.9

    def test_score_based_ranking_orders_by_similarity(self):
        docs = [
            _make_doc("Low relevance doc", 0.5),
            _make_doc("High relevance doc", 0.95),
            _make_doc("Medium relevance doc", 0.75),
        ]
        results = merge_results(docs)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_max_context_documents_cap_enforced(self):
        from src.config import settings

        docs = [_make_doc(f"Document {i} unique content here", 0.9 - i * 0.01) for i in range(30)]
        results = merge_results(docs)
        assert len(results) <= settings.max_context_documents

    def test_empty_input_returns_empty_list(self):
        assert merge_results([]) == []

    def test_single_doc_returns_single_result(self):
        doc = _make_doc("Only document", 0.8)
        results = merge_results([doc])
        assert len(results) == 1

    def test_cross_domain_docs_all_included(self):
        billing_doc = _make_doc("Billing policy info", 0.9, domain="billing")
        account_doc = _make_doc("Account access info", 0.85, domain="account")
        technical_doc = _make_doc("API rate limits info", 0.8, domain="technical")
        results = merge_results([billing_doc, account_doc, technical_doc])
        assert len(results) == 3
        domains = {r["domain"] for r in results}
        assert domains == {"billing", "account", "technical"}

    def test_dedup_keeps_higher_score_among_duplicates(self):
        low_score = _make_doc("Same content here", 0.6)
        high_score = _make_doc("Same content here", 0.9)
        results = merge_results([low_score, high_score])
        assert len(results) == 1
        assert results[0]["score"] == 0.9

    def test_results_have_required_fields(self):
        doc = _make_doc("Test document content", 0.8)
        results = merge_results([doc])
        assert len(results) == 1
        r = results[0]
        assert "content" in r
        assert "score" in r
        assert "domain" in r
