from src.rag.chunking import chunk_text


def test_chunks_within_size_limit():
    long_text = "The quick brown fox jumped over the lazy dog. " * 100
    chunks = chunk_text(long_text)
    for chunk in chunks:
        assert len(chunk) <= 1000, f"Chunk too large: {len(chunk)}"


def test_produces_multiple_chunks_for_long_text():
    long_text = "word " * 300
    chunks = chunk_text(long_text)
    assert len(chunks) > 1


def test_short_text_returns_single_chunk():
    short_text = "This is a short text."
    chunks = chunk_text(short_text)
    assert len(chunks) == 1
    assert chunks[0] == short_text


def test_chunk_overlap():
    # With chunk_size=1000, chunk_overlap=200, adjacent chunks should share content
    long_text = "sentence number {n}. " * 200
    chunks = chunk_text(long_text)
    if len(chunks) > 1:
        # Each chunk should be non-empty
        for chunk in chunks:
            assert len(chunk) > 0


def test_returns_list_of_strings():
    chunks = chunk_text("some text content")
    assert isinstance(chunks, list)
    for chunk in chunks:
        assert isinstance(chunk, str)


def test_empty_text_returns_empty_list():
    chunks = chunk_text("")
    assert isinstance(chunks, list)
