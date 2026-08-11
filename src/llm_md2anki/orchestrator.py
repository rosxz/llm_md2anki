"""Orchestrator for chunked or whole-file LLM conversions."""
from __future__ import annotations

import sys
from typing import Any, Callable, cast
from .chunking import Chunk, split_by_headings
from .md_to_anki_contract import (
    build_chunk_plan_prompt,
    build_chunk_user_prompt,
    build_fix_prompt,
    build_initial_prompt,
    build_system_prompt,
    normalize_llm_markdown,
    parse_chunk_plan,
)
from .providers import Provider, build_provider
from .validator import validate_converted_markdown
from pathlib import Path
from rich.console import Console
import tempfile
import os


class Orchestrator:
    def __init__(
        self,
        provider: Provider | None = None,
        provider_name: str = "gemini",
        api_key: str | None = None,
        model: str = "gemini-2.0-flash",
        base_url: str | None = None,
        reasoning_effort: str | None = None,
        chunk_batch_size: int = 4,
    ):
        self.console = Console()
        self.provider = provider or build_provider(
            provider_name,
            api_key=api_key,
            model=model,
            base_url=base_url,
            reasoning_effort=reasoning_effort,
        )
        self.chunk_batch_size = max(1, chunk_batch_size)
        self.prompt_preview_chars = 900

    def run_from_file(self, path: str, chunked: bool = False, whole: bool = False):
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        return self._run_core(text, path, chunked=chunked, whole=whole)

    def run_from_text(self, text: str, chunked: bool = False, whole: bool = False):
        return self._run_core(text, "<stdin>", chunked=chunked, whole=whole)

    def _run_core(self, text: str, source: str, chunked: bool = False, whole: bool = False):
        # Decide mode
        if whole or (not chunked and len(text) < 4000):
            self.console.print("Processing whole file via LLM...")
            converted, meta = self._call_llm_convert(text, whole=True)
            errs = validate_converted_markdown(converted)
            if not errs:
                return self._finalize_output(converted, source)
            else:
                self.console.print(f"Validation returned {len(errs)} errors — entering fix loop")
                return self._handle_errors(converted, errs, source)

        # chunked
        chunks = self._plan_chunks(text, split_by_headings(text))
        outputs = []
        for batch_start in range(0, len(chunks), self.chunk_batch_size):
            batch = chunks[batch_start : batch_start + self.chunk_batch_size]
            # One system prompt per batch; each chunk is a new turn in the same
            # conversation, so the system prefix is sent once and can be cached.
            system_prompt = build_system_prompt()
            messages: list[dict[str, str]] = []
            self.console.print(
                f"Processing chunk batch {batch_start + 1}-{batch_start + len(batch)} of {len(chunks)}"
            )

            for idx, chunk in enumerate(batch, start=batch_start):
                self.console.print(
                    f"Processing chunk {idx+1}/{len(chunks)} (lines {chunk.start_line+1}-{chunk.end_line+1})"
                )
                user_content = build_chunk_user_prompt(context=chunk.context, body=chunk.body)
                messages.append({"role": "user", "content": user_content})
                converted = self._invoke_chat(system_prompt, messages, label=f"chunk {idx+1}")
                messages.append({"role": "assistant", "content": converted})
                errs = validate_converted_markdown(converted)
                attempt = 0
                while errs and attempt < 3:
                    self.console.print(
                        f"Chunk has {len(errs)} validation errors — asking LLM to fix (attempt {attempt+1})"
                    )
                    fix_text, _ = self._call_llm_fix(
                        chunk.body,
                        converted,
                        errs,
                        context=chunk.context,
                    )
                    # create temp user/suggestion files
                    sug = self._write_temp_file(fix_text, suffix=f"_suggest_{idx}.md")
                    usr = self._write_temp_file(chunk.body, suffix=f"_user_{idx}.md")
                    self.console.print(f"Suggested fix written to {sug}; user-edit file {usr}")
                    # For MVP, assume user approves suggestion
                    converted = fix_text
                    messages.append({"role": "assistant", "content": converted})
                    errs = validate_converted_markdown(converted)
                    attempt += 1
                outputs.append(converted)

        merged = "\n\n\n".join(outputs)
        final_errs = validate_converted_markdown(merged)
        if final_errs:
            self.console.print(f"Post-merge validation failed with {len(final_errs)} errors")
            return self._handle_errors(merged, final_errs, source)

        return self._finalize_output(merged, source)

    def _invoke_chat(self, system_prompt: str, messages: list[dict[str, str]], label: str) -> str:
        """Run one turn of a continuing conversation and return the content text."""
        chat_stream = getattr(self.provider, "chat_stream", None)
        if callable(chat_stream):
            self._log_chat(system_prompt, messages, label=label)
            content = self._render_stream(chat_stream(system_prompt, messages))
            return content
        # Fallback for providers without chat_stream: single-shot combined prompt.
        combined = system_prompt + "\n\n" + messages[-1]["content"]
        converted, _ = self._invoke_llm(combined, label=label)
        return converted

    def _call_llm_convert(self, text: str, whole: bool = False, context: str = "", batch_memory: str = ""):
        prompt = build_initial_prompt(text, whole_file=whole, context=context, batch_memory=batch_memory)
        return self._invoke_llm(prompt, label="convert")

    def _call_llm_fix(self, original: str, converted: str, errors, context: str = "", batch_memory: str = ""):
        prompt = build_fix_prompt(
            original,
            converted,
            [str(error) for error in errors],
            context=context,
            batch_memory=batch_memory,
        )
        return self._invoke_llm(prompt, label="fix")

    def _plan_chunks(self, text: str, candidate_chunks: list[Chunk]) -> list[Chunk]:
        """Ask the model to refine the auto-selected chunks for the whole file."""
        if not candidate_chunks:
            return []

        candidates_payload = []
        for idx, chunk in enumerate(candidate_chunks, start=1):
            candidates_payload.append(
                {
                    "candidate_index": idx,
                    "start_line": chunk.start_line + 1,
                    "end_line": chunk.end_line + 1,
                    "context": chunk.context,
                }
            )

        prompt = build_chunk_plan_prompt(text, candidates_payload)
        result_text, _ = self._invoke_llm(prompt, label="chunk-plan")

        try:
            planned = parse_chunk_plan(result_text)
        except Exception as exc:
            self.console.print(f"Chunk planning failed, falling back to automatic chunks: {exc}")
            return candidate_chunks

        planned_chunks: list[Chunk] = []
        lines = text.splitlines()
        for index, item in enumerate(planned, start=1):
            try:
                start_line = int(cast(Any, item.get("start_line")))
                end_line = int(cast(Any, item.get("end_line")))
            except Exception as exc:
                self.console.print(f"Invalid chunk plan item #{index}, falling back to automatic chunks: {exc}")
                return candidate_chunks

            if start_line < 1 or end_line < start_line or end_line > len(lines):
                self.console.print(
                    f"Chunk plan item #{index} has invalid range {start_line}-{end_line}, falling back to automatic chunks"
                )
                return candidate_chunks

            body = "\n".join(lines[start_line - 1 : end_line]).strip()
            context = str(item.get("context", "")).strip()
            planned_chunks.append(Chunk(start_line - 1, end_line - 1, context, body))

        planned_chunks.sort(key=lambda chunk: (chunk.start_line, chunk.end_line))
        if not planned_chunks:
            return candidate_chunks
        return planned_chunks

    def _invoke_llm(self, prompt: str, label: str) -> tuple[str, dict]:
        self._log_prompt(prompt, label=label)

        stream = cast(Callable[[str], Any] | None, getattr(self.provider, "generate_stream", None))
        if stream is not None:
            return self._render_stream(stream(prompt)), {}

        result = self.provider.generate(prompt)
        return normalize_llm_markdown(result.text), result.meta

    def _render_stream(self, stream_iter) -> str:
        """Render a stream of pieces (thinking indented + gray, content plain).

        Returns the normalized concatenated content (thinking is not part of the
        parseable result unless a provider falls back to it as content).
        """
        content_parts: list[str] = []
        thinking_open = False
        line_start = True
        GRAY = "\x1b[90m"
        RESET = "\x1b[0m"
        sys.stdout.write("\n")
        sys.stdout.flush()

        for piece in stream_iter:
            # Tolerate both StreamPiece objects and plain strings (e.g. test providers).
            if isinstance(piece, str):
                text, kind = piece, "content"
            else:
                text = getattr(piece, "text", "")
                kind = getattr(piece, "kind", "content")
            if not text:
                continue

            if kind == "thinking":
                if not thinking_open:
                    sys.stdout.write(GRAY)
                    thinking_open = True
                if line_start:
                    sys.stdout.write("\t")
                    line_start = False
                sys.stdout.write(text)
                line_start = text.endswith("\n")
            else:
                if thinking_open:
                    sys.stdout.write(RESET)
                    thinking_open = False
                    # Start content on a fresh line after thinking.
                    if not line_start:
                        sys.stdout.write("\n")
                    line_start = True
                sys.stdout.write(text)
                line_start = text.endswith("\n")
                content_parts.append(text)
            sys.stdout.flush()

        if thinking_open:
            sys.stdout.write(RESET)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return normalize_llm_markdown("".join(content_parts))

    def _log_prompt(self, prompt: str, label: str) -> None:
        preview = prompt.strip()
        truncated = len(preview) > self.prompt_preview_chars
        if truncated:
            preview = preview[: self.prompt_preview_chars].rstrip() + "\n... (truncated)"

        self.console.print(f"[bold]Prompt ({label}) preview[/bold] ({len(prompt)} chars):")
        self.console.print(preview)
        if truncated:
            self.console.print(f"[dim]Prompt truncated to first {self.prompt_preview_chars} characters[/dim]")

    def _log_chat(self, system_prompt: str, messages: list[dict[str, str]], label: str) -> None:
        """Show the conversation being sent: system prefix + the newest user turn."""
        sys_len = len(system_prompt)
        last = messages[-1] if messages else {}
        self.console.print(f"[bold]Chat ({label})[/bold] system={sys_len} chars, turns={len(messages)}")
        preview = system_prompt.strip()
        if len(preview) > self.prompt_preview_chars:
            preview = preview[: self.prompt_preview_chars].rstrip() + "\n... (system truncated)"
        self.console.print(f"[dim]System:[/dim] {preview}")
        user_preview = str(last.get("content", "")).strip()
        if len(user_preview) > self.prompt_preview_chars:
            user_preview = user_preview[: self.prompt_preview_chars].rstrip() + "\n... (user truncated)"
        self.console.print(f"[dim]Last {last.get('role', '?')} turn:[/dim] {user_preview}")

    def _write_temp_file(self, text: str, suffix: str = ".md") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="llmfix_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def _handle_errors(self, converted: str, errors, source: str):
        # For MVP: write suggestion and user files and stop
        sug = self._write_temp_file(converted, suffix="_final_suggest.md")
        usr = self._write_temp_file(converted, suffix="_final_user.md")
        self.console.print(f"Wrote suggestion {sug} and user-edit {usr}; please inspect and re-run")
        return converted

    def _finalize_output(self, converted: str, source: str):
        self.console.print("Conversion succeeded — output below:\n")
        print(converted)
        return converted
