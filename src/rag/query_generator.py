from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from src.config import settings


class _SearchQuery(BaseModel):
    query: str
    target_domain: str
    aspect: str


class _SearchQueryList(BaseModel):
    queries: list[_SearchQuery]


_QUERY_GEN_PROMPT = """You are a search query specialist for a customer support knowledge base.

Given a customer question and the domains it spans, generate up to {count} targeted search query variations
that will maximize retrieval recall. Each query should:
1. Target a specific domain (billing, technical, or account)
2. Focus on a different aspect or facet of the original question
3. Use terminology likely to match support documentation

Domains to cover: {domains}
Customer question: {question}

For SIMPLE, single-facet questions (e.g. "Why was I charged?"), generate exactly 1 query using the original question.
For COMPLEX, multi-facet questions with 2+ distinct concerns, generate 2-3 diverse query variations.

For each query specify:
- query: the reformulated search text
- target_domain: which domain to search (one of: billing, technical, account, all)
- aspect: which facet of the question this query addresses"""

_COMPLEX_INDICATORS = [
    " and ",
    " also ",
    " as well",
    " additionally",
    " both ",
    " plus ",
    " while ",
    " meanwhile ",
    "?",
    " multiple ",
    "cancel",
    "export",
    "team",
    "api",
    "webhook",
    "rate limit",
]


def _is_complex_query(query_text: str) -> bool:
    """Heuristic: detect multi-facet queries that benefit from expansion."""
    lower = query_text.lower()
    indicator_count = sum(1 for indicator in _COMPLEX_INDICATORS if indicator in lower)
    word_count = len(query_text.split())
    return indicator_count >= 2 or word_count >= 12


def generate_search_queries(
    query_text: str,
    classified_domains: list[str],
) -> list[dict]:
    """Generate domain-targeted search query variations using Claude structured output.

    Simple single-facet queries bypass multi-query expansion and use the original query.
    Complex multi-facet queries generate 2-3 semantically diverse variations.
    """
    try:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
        )
        structured_llm = llm.with_structured_output(_SearchQueryList)

        domains_str = ", ".join(classified_domains)
        prompt = _QUERY_GEN_PROMPT.format(
            count=settings.multi_query_count,
            domains=domains_str,
            question=query_text,
        )

        result = structured_llm.invoke(prompt)
        return [
            {
                "query": q.query,
                "target_domain": q.target_domain,
                "aspect": q.aspect,
            }
            for q in result.queries
        ]
    except Exception:
        # Fallback: use original query for each classified domain
        return [
            {
                "query": query_text,
                "target_domain": domain,
                "aspect": "general",
            }
            for domain in classified_domains
        ]
