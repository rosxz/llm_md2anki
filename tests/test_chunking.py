from llm_md2anki.chunking import split_by_headings


def test_split_by_headings():
    text = "# A\nline1\n## B\nline2\n# C\nline3"
    chunks = split_by_headings(text)
    assert len(chunks) >= 2
