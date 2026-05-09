import os

import pytest

from src.config import settings


@pytest.fixture(autouse=True, scope="session")
def _export_openai_key_for_ragas():
    if settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    yield
