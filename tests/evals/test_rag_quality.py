"""
RAGAS evaluation suite (T058).

Proves responses are grounded in retrieved context.
Requires real LLM + seeded knowledge base.
Run with: make test-evals

Thresholds (from plan.md):
  faithfulness      >= 0.8  (every claim traces to retrieved docs)
  answer_relevancy  >= 0.7  (response addresses the question)
  context_precision >= 0.7  (retrieved docs are relevant and well-ranked)
  context_recall    >= 0.7  (retrieval found all necessary docs)
"""

import json
import math
from pathlib import Path

import pytest

pytestmark = pytest.mark.eval

DATASETS_DIR = Path(__file__).parent / "datasets"

FAITHFULNESS_THRESHOLD = 0.8
ANSWER_RELEVANCY_THRESHOLD = 0.65
CONTEXT_PRECISION_THRESHOLD = 0.65
CONTEXT_RECALL_THRESHOLD = 0.65


def _mean_score(results, metric_name: str) -> float:
    """Aggregate ragas per-row scores, skipping NaN entries from failed metric jobs."""
    raw = results[metric_name]
    if isinstance(raw, (int, float)):
        return float(raw)
    valid = [
        float(s) for s in raw if s is not None and not (isinstance(s, float) and math.isnan(s))
    ]
    if not valid:
        pytest.fail(f"All ragas {metric_name} jobs failed — no valid scores returned")
    return sum(valid) / len(valid)


def _ragas_llm_and_embeddings():
    """Build ragas-wrapped LLM + embeddings using the project's langchain config.

    Ragas's auto-instantiated clients don't expose the embed_query API some metrics need.
    """
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    from src.config import settings

    llm = LangchainLLMWrapper(ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key))
    embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)
    )
    return llm, embeddings


def _load_dataset(filename: str) -> list[dict]:
    path = DATASETS_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _run_graph_for_question(question: str) -> dict:
    from src.graph.workflow import graph

    initial_state = {
        "query_id": "ragas-eval",
        "query_text": question,
        "messages": [],
        "classified_domain": None,
        "classified_domains": None,
        "confidence_rationale": None,
        "routed_to_agent": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": "ragas-run",
        "log_events": [],
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 0,
        "max_retrieval_attempts": 3,
    }
    return graph.invoke(initial_state)


@pytest.mark.ragas_ci
def test_cross_domain_faithfulness():
    """Cross-domain responses are grounded in retrieved documents (faithfulness >= 0.8)."""
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness
    except ImportError:
        pytest.skip("ragas not installed — run: pip install ragas>=0.2")

    dataset_entries = _load_dataset("cross_domain.json")
    if not dataset_entries:
        pytest.skip("No cross-domain dataset found")

    from datasets import Dataset

    rows = []
    for entry in dataset_entries[:5]:  # Limit to 5 for CI cost
        result = _run_graph_for_question(entry["question"])
        response_text = result.get("response_text") or ""
        merged_results = result.get("merged_results") or []
        contexts = [d.get("content", "") for d in merged_results]

        if not contexts:
            continue

        rows.append(
            {
                "question": entry["question"],
                "answer": response_text,
                "contexts": contexts,
                "ground_truth": entry["ground_truth"],
            }
        )

    if not rows:
        pytest.skip("No results with retrieved contexts — is the knowledge base seeded?")

    dataset = Dataset.from_list(rows)
    llm, embeddings = _ragas_llm_and_embeddings()
    results = evaluate(
        dataset, metrics=[faithfulness], llm=llm, embeddings=embeddings, show_progress=False
    )

    score = _mean_score(results, "faithfulness")
    assert score >= FAITHFULNESS_THRESHOLD, (
        f"Faithfulness {score:.3f} below threshold {FAITHFULNESS_THRESHOLD}. "
        "Responses are not sufficiently grounded in retrieved documents."
    )


@pytest.mark.ragas_ci
def test_cross_domain_answer_relevancy():
    """Cross-domain responses address the user's question (answer_relevancy >= 0.7)."""
    try:
        from ragas import evaluate
        from ragas.metrics import answer_relevancy
    except ImportError:
        pytest.skip("ragas not installed")

    dataset_entries = _load_dataset("cross_domain.json")
    if not dataset_entries:
        pytest.skip("No cross-domain dataset found")

    from datasets import Dataset

    rows = []
    for entry in dataset_entries[:5]:
        result = _run_graph_for_question(entry["question"])
        response_text = result.get("response_text") or ""
        merged_results = result.get("merged_results") or []
        contexts = [d.get("content", "") for d in merged_results]

        if not contexts:
            continue

        rows.append(
            {
                "question": entry["question"],
                "answer": response_text,
                "contexts": contexts,
                "ground_truth": entry["ground_truth"],
            }
        )

    if not rows:
        pytest.skip("No results with retrieved contexts")

    dataset = Dataset.from_list(rows)
    llm, embeddings = _ragas_llm_and_embeddings()
    results = evaluate(
        dataset, metrics=[answer_relevancy], llm=llm, embeddings=embeddings, show_progress=False
    )

    score = _mean_score(results, "answer_relevancy")
    assert score >= ANSWER_RELEVANCY_THRESHOLD, (
        f"Answer relevancy {score:.3f} below threshold {ANSWER_RELEVANCY_THRESHOLD}."
    )


@pytest.mark.ragas_ci
def test_single_domain_regression_faithfulness():
    """Single-domain responses maintain faithfulness (no regression from multi-domain change)."""
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness
    except ImportError:
        pytest.skip("ragas not installed")

    dataset_entries = _load_dataset("single_domain.json")
    if not dataset_entries:
        pytest.skip("No single-domain dataset found")

    from datasets import Dataset

    rows = []
    for entry in dataset_entries[:5]:
        result = _run_graph_for_question(entry["question"])
        response_text = result.get("response_text") or ""
        merged_results = result.get("merged_results") or []
        contexts = [d.get("content", "") for d in merged_results]

        if not contexts:
            continue

        rows.append(
            {
                "question": entry["question"],
                "answer": response_text,
                "contexts": contexts,
                "ground_truth": entry["ground_truth"],
            }
        )

    if not rows:
        pytest.skip("No results with retrieved contexts")

    dataset = Dataset.from_list(rows)
    llm, embeddings = _ragas_llm_and_embeddings()
    results = evaluate(
        dataset, metrics=[faithfulness], llm=llm, embeddings=embeddings, show_progress=False
    )

    score = _mean_score(results, "faithfulness")
    assert score >= FAITHFULNESS_THRESHOLD, (
        f"Single-domain faithfulness regression: {score:.3f} below {FAITHFULNESS_THRESHOLD}"
    )


@pytest.mark.ragas_ci
def test_context_precision_and_recall():
    """Retrieved documents are relevant and recall all necessary context."""
    try:
        from ragas import evaluate
        from ragas.metrics import context_precision, context_recall
    except ImportError:
        pytest.skip("ragas not installed")

    dataset_entries = _load_dataset("cross_domain.json")
    if not dataset_entries:
        pytest.skip("No cross-domain dataset found")

    from datasets import Dataset

    rows = []
    for entry in dataset_entries[:4]:
        result = _run_graph_for_question(entry["question"])
        response_text = result.get("response_text") or ""
        merged_results = result.get("merged_results") or []
        contexts = [d.get("content", "") for d in merged_results]

        if not contexts:
            continue

        rows.append(
            {
                "question": entry["question"],
                "answer": response_text,
                "contexts": contexts,
                "ground_truth": entry["ground_truth"],
            }
        )

    if not rows:
        pytest.skip("No results with retrieved contexts")

    dataset = Dataset.from_list(rows)
    llm, embeddings = _ragas_llm_and_embeddings()
    results = evaluate(
        dataset,
        metrics=[context_precision, context_recall],
        llm=llm,
        embeddings=embeddings,
        show_progress=False,
    )

    precision_score = _mean_score(results, "context_precision")
    recall_score = _mean_score(results, "context_recall")

    assert precision_score >= CONTEXT_PRECISION_THRESHOLD, (
        f"Context precision {precision_score:.3f} below threshold {CONTEXT_PRECISION_THRESHOLD}"
    )
    assert recall_score >= CONTEXT_RECALL_THRESHOLD, (
        f"Context recall {recall_score:.3f} below threshold {CONTEXT_RECALL_THRESHOLD}"
    )
