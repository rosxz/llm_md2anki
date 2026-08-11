from llm_md2anki.chunking import split_by_headings


def test_split_by_headings():
    text = "# A\nline1\n## B\nline2\n# C\nline3"
    chunks = split_by_headings(text)
    assert len(chunks) >= 2


def test_skips_url_only_preamble():
    text = "# Kubernetes\n<https://notes.kodekloud.com/docs/Certified-Kubernetes-Administrator-CKA/Scheduling/Manual-Scheduling/page>\n\n## Concepts\nWhat is this?"
    chunks = split_by_headings(text)
    assert len(chunks) == 1
    assert chunks[0].context == "Kubernetes / Concepts"
    assert "What is this?" in chunks[0].body
