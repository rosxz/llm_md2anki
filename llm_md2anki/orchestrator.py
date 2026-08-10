"""Orchestrator for chunked or whole-file LLM conversions."""
from __future__ import annotations

from .chunking import split_by_headings
from .providers import Provider, build_provider
from .validator import validate_converted_markdown, ValidationError
from pathlib import Path
from rich.console import Console
import tempfile
import os


class Orchestrator:
    def __init__(self, provider: Provider | None = None, provider_name: str = "gemini", api_key: str | None = None, model: str = "gemini-2.0-flash"):
        self.console = Console()
        self.provider = provider or build_provider(provider_name, api_key=api_key, model=model)

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
        chunks = split_by_headings(text)
        outputs = []
        for idx, (start, end, chunk_text) in enumerate(chunks):
            self.console.print(f"Processing chunk {idx+1}/{len(chunks)} (lines {start+1}-{end+1})")
            converted, meta = self._call_llm_convert(chunk_text)
            errs = validate_converted_markdown(converted)
            attempt = 0
            while errs and attempt < 3:
                self.console.print(f"Chunk has {len(errs)} validation errors — asking LLM to fix (attempt {attempt+1})")
                fix_text, _ = self._call_llm_fix(chunk_text, converted, errs)
                # create temp user/suggestion files
                sug = self._write_temp_file(fix_text, suffix=f"_suggest_{idx}.md")
                usr = self._write_temp_file(chunk_text, suffix=f"_user_{idx}.md")
                self.console.print(f"Suggested fix written to {sug}; user-edit file {usr}")
                # For MVP, assume user approves suggestion
                converted = fix_text
                errs = validate_converted_markdown(converted)
                attempt += 1
            outputs.append(converted)

        merged = "\n\n\n".join(outputs)
        final_errs = validate_converted_markdown(merged)
        if final_errs:
            self.console.print(f"Post-merge validation failed with {len(final_errs)} errors")
            return self._handle_errors(merged, final_errs, source)

        return self._finalize_output(merged, source)

    def _call_llm_convert(self, text: str, whole: bool = False):
        prompt = self._build_prompt_convert(text, whole=whole)
        result = self.provider.generate(prompt)
        return result.text, result.meta

    def _call_llm_fix(self, original: str, converted: str, errors):
        prompt = self._build_prompt_fix(original, converted, errors)
        result = self.provider.generate(prompt)
        return result.text, result.meta

    def _build_prompt_convert(self, text: str, whole: bool = False) -> str:
        header = [
            "You are a formatter that converts arbitrary markdown into md-to-anki compatible markdown.",
            "Return only markdown, no commentary.",
            "Preserve the meaning of the input.",
            "Use double blank lines to separate cards.",
            "Use **bold** or explicit {{c#::}} for cloze content.",
            "Use --- to separate Extra fields when helpful.",
        ]
        if whole:
            header.append("Treat the entire input as one document and normalize it holistically.")
        return "\n".join(header) + "\n\nINPUT:\n" + text

    def _build_prompt_fix(self, original: str, converted: str, errors) -> str:
        header = [
            "The converted markdown failed validation. Fix it minimally.",
            "Return only the corrected markdown.",
            "Validation errors:",
        ]
        for e in errors:
            header.append(f"- {e}")
        header.append("\nORIGINAL:\n" + original)
        header.append("\nCURRENT_CONVERSION:\n" + converted)
        return "\n".join(header)

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
