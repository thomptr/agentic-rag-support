from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector

from src.config import settings

COLLECTION_NAME = "support_kb"


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )


def get_vector_store() -> PGVector:
    embeddings = get_embeddings()
    return PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        connection=settings.database_url,
        use_jsonb=True,
    )
