from llm_md2anki.orchestrator import Orchestrator
from llm_md2anki.providers import StaticProvider, SequenceProvider


def test_whole_file_conversion_writes_output(capsys):
    provider = StaticProvider("# Card\n\nThis is **bold** content.")
    orchestrator = Orchestrator(provider=provider)
    output = orchestrator.run_from_text("# Input\nSome content", whole=True)
    captured = capsys.readouterr()
    assert "Conversion succeeded" in captured.out
    assert "# Card" in output


def test_chunked_conversion_processes_each_chunk(capsys):
    provider = SequenceProvider([
        "# Chunk 1\n\nFirst **card**.",
        "# Chunk 2\n\nSecond **card**.",
    ])
    orchestrator = Orchestrator(provider=provider)
    output = orchestrator.run_from_text("# A\nalpha\n\n# B\nbeta", chunked=True)
    captured = capsys.readouterr()
    assert "Processing chunk" in captured.out
    assert "Chunk 1" in output
    assert "Chunk 2" in output
