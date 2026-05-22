from src.rag.confidence import assess_confidence


class TestAssessConfidence:
    def test_high_similarity_sufficient_count_no_retry(self):
        docs = [{"content": f"doc {i}", "score": 0.85, "domain": "billing"} for i in range(5)]
        result = assess_confidence(docs, attempt=1)
        assert result["should_retry"] is False
        assert result["avg_similarity"] >= 0.6
        assert result["result_count"] == 5

    def test_low_avg_similarity_triggers_retry(self):
        docs = [{"content": f"doc {i}", "score": 0.3, "domain": "billing"} for i in range(5)]
        result = assess_confidence(docs, attempt=1)
        assert result["should_retry"] is True
        assert result["avg_similarity"] < 0.6

    def test_low_result_count_triggers_retry(self):
        docs = [
            {"content": f"doc {i}", "score": 0.9, "domain": "billing"}
            for i in range(1)  # only 1 doc, below MIN_RESULT_COUNT=3
        ]
        result = assess_confidence(docs, attempt=1)
        assert result["should_retry"] is True
        assert result["result_count"] < 3

    def test_sufficient_results_no_retry(self):
        docs = [{"content": f"doc {i}", "score": 0.75, "domain": "billing"} for i in range(4)]
        result = assess_confidence(docs, attempt=1)
        assert result["should_retry"] is False

    def test_avg_similarity_calculation(self):
        docs = [
            {"content": "doc1", "score": 0.8, "domain": "billing"},
            {"content": "doc2", "score": 0.6, "domain": "billing"},
            {"content": "doc3", "score": 0.7, "domain": "billing"},
        ]
        result = assess_confidence(docs, attempt=1)
        assert abs(result["avg_similarity"] - 0.7) < 0.001

    def test_empty_results_triggers_retry(self):
        result = assess_confidence([], attempt=1)
        assert result["should_retry"] is True
        assert result["result_count"] == 0

    def test_boundary_at_threshold_passes(self):
        from src.config import settings

        threshold = settings.confidence_threshold
        min_count = settings.min_result_count
        docs = [
            {"content": f"doc {i}", "score": threshold, "domain": "billing"}
            for i in range(min_count)
        ]
        result = assess_confidence(docs, attempt=1)
        # At exactly the threshold and min count, should not retry
        assert result["should_retry"] is False

    def test_result_has_required_fields(self):
        docs = [{"content": "doc1", "score": 0.8, "domain": "billing"}] * 3
        result = assess_confidence(docs, attempt=1)
        assert "score" in result
        assert "result_count" in result
        assert "avg_similarity" in result
        assert "should_retry" in result
        assert "reason" in result

    def test_should_retry_false_when_at_max_attempts(self):
        from src.config import settings

        # Even low confidence should not retry at max attempts
        docs = [{"content": f"doc {i}", "score": 0.2, "domain": "billing"} for i in range(1)]
        result = assess_confidence(docs, attempt=settings.max_retrieval_attempts)
        # At max attempts, no more retries regardless of confidence
        assert result["should_retry"] is False

    def test_top_k_mean_ignores_long_tail(self):
        """Strong top results should pass the gate even when a long tail of
        marginal matches drags the full average below threshold."""
        from src.config import settings

        # 3 strong hits + 7 weak ones. With confidence_top_k=3 the gate sees
        # only the strong ones; the legacy avg-over-all would see 0.32.
        strong = [{"content": f"s{i}", "score": 0.9, "domain": "billing"} for i in range(3)]
        tail = [{"content": f"t{i}", "score": 0.1, "domain": "billing"} for i in range(7)]
        docs = strong + tail

        result = assess_confidence(docs, attempt=1)

        # Gating score = top-3 mean = 0.9; avg_similarity = mean of all 10 = 0.34.
        assert abs(result["score"] - 0.9) < 1e-6
        assert abs(result["avg_similarity"] - 0.34) < 1e-6
        assert result["score"] > result["avg_similarity"]
        assert result["top_k"] == settings.confidence_top_k
        assert result["should_retry"] is False

    def test_top_k_clamped_when_fewer_results(self):
        """top_k should clamp to result_count when fewer results exist."""
        from src.config import settings

        # Only 2 results — fewer than configured top_k (3).
        docs = [{"content": f"doc {i}", "score": 0.8, "domain": "billing"} for i in range(2)]
        result = assess_confidence(docs, attempt=1)

        assert result["top_k"] == 2
        assert result["top_k"] <= settings.confidence_top_k
        # Score is the mean of however many we have.
        assert abs(result["score"] - 0.8) < 1e-6
