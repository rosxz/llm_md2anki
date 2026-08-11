from llm_md2anki.orchestrator import Orchestrator
from llm_md2anki.providers import OpenCodeProvider, OpenRouterProvider, StaticProvider, SequenceProvider, build_provider


def test_whole_file_conversion_writes_output(capsys):
    provider = StaticProvider("# Card\n\nThis is **bold** content.")
    orchestrator = Orchestrator(provider=provider)
    output = orchestrator.run_from_text("# Input\nSome content", whole=True)
    captured = capsys.readouterr()
    assert "Conversion succeeded" in captured.out
    assert "# Card" in output


def test_chunked_conversion_processes_each_chunk(capsys):
    provider = SequenceProvider([
        '{"chunks": [{"start_line": 1, "end_line": 2, "context": "A", "reason": "keep body"}, {"start_line": 4, "end_line": 5, "context": "B", "reason": "keep body"}]}',
        "# Chunk 1\n\nFirst **card**.",
        "# Chunk 2\n\nSecond **card**.",
    ])
    orchestrator = Orchestrator(provider=provider)
    output = orchestrator.run_from_text("# A\nalpha\n\n# B\nbeta", chunked=True)
    captured = capsys.readouterr()
    assert "Processing chunk" in captured.out
    assert "Chunk 1" in output
    assert "Chunk 2" in output


def test_chunked_conversion_batches_and_resets_memory(capsys):
    provider = SequenceProvider([
        '{"chunks": [{"start_line": 1, "end_line": 2, "context": "A", "reason": "keep body"}, {"start_line": 4, "end_line": 5, "context": "B", "reason": "keep body"}, {"start_line": 7, "end_line": 8, "context": "C", "reason": "keep body"}]}',
        "# Chunk 1\n\nFirst **card**.",
        "# Chunk 2\n\nSecond **card**.",
        "# Chunk 3\n\nThird **card**.",
    ])
    orchestrator = Orchestrator(provider=provider, chunk_batch_size=2)
    output = orchestrator.run_from_text("# A\nalpha\n\n# B\nbeta\n\n# C\ngamma", chunked=True)
    captured = capsys.readouterr()
    assert "Processing chunk batch 1-2" in captured.out
    assert "Processing chunk batch 3-3" in captured.out
    assert "Chunk 1" in output
    assert "Chunk 3" in output


def test_build_provider_openrouter():
    provider = build_provider(name="openrouter", api_key="test-key", model="openrouter/free")
    assert isinstance(provider, OpenRouterProvider)
    assert provider.model == "openrouter/free"


def test_build_provider_opencode():
    provider = build_provider(name="opencode", api_key="test-key", model="opencode")
    assert isinstance(provider, OpenCodeProvider)
    assert provider.model == "opencode"


def test_streaming_output_and_prompt_truncation(capsys):
    class StreamingProvider:
        def generate(self, prompt: str):
            raise AssertionError("streaming path should be used")

        def generate_stream(self, prompt: str):
            yield "Hello"
            yield " world"

    orchestrator = Orchestrator(provider=StreamingProvider())
    long_input = "# Title\n" + ("x" * 2000)
    output = orchestrator.run_from_text(long_input, whole=True)
    captured = capsys.readouterr()
    assert "Prompt (convert) preview" in captured.out
    assert "(truncated)" in captured.out
    assert "Hello world" in captured.out.replace("\n", "")
    assert output == "Hello world"


class _FakeDelta:
    def __init__(self, content=None, reasoning=None):
        self.content = content
        self.reasoning_content = reasoning


class _FakeChoice:
    def __init__(self, delta):
        self.delta = delta


class _FakeEvent:
    def __init__(self, delta):
        self.choices = [_FakeChoice(delta)]


class _FakeCompletions:
    def __init__(self, events):
        self._events = events

    def create(self, **kwargs):
        return self._events


class _FakeClient:
    def __init__(self, events):
        self.chat = type("_Chat", (), {"completions": _FakeCompletions(events)})()
        self._events = events


def test_opencode_stream_prefers_content_over_reasoning():
    provider = OpenCodeProvider(api_key="test-key")
    events = [
        _FakeEvent(_FakeDelta(reasoning="thinking...")),
        _FakeEvent(_FakeDelta(content='{"chunks": []}')),
    ]
    provider._client = lambda: _FakeClient(events)
    pieces = list(provider.generate_stream("prompt"))
    kinds = [p.kind for p in pieces]
    assert kinds == ["thinking", "content"]
    # Only content is the parseable result.
    assert "".join(p.text for p in pieces if p.kind == "content") == '{"chunks": []}'


def test_opencode_stream_falls_back_to_reasoning_when_no_content():
    provider = OpenCodeProvider(api_key="test-key")
    events = [
        _FakeEvent(_FakeDelta(reasoning="the actual answer")),
        _FakeEvent(_FakeDelta(reasoning=" continues")),
    ]
    provider._client = lambda: _FakeClient(events)
    pieces = list(provider.generate_stream("prompt"))
    # Go gateway quirk: reasoning is the answer when content is empty.
    assert [p.kind for p in pieces] == ["thinking", "thinking", "content", "content"]
    # The orchestrator consumes only content pieces, which mirror the reasoning.
    assert "".join(p.text for p in pieces if p.kind == "content") == "the actual answer continues"
