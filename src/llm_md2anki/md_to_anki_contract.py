"""md-to-anki compatibility helpers.

This module centralizes the prompt contract and output cleanup for the MVP.
The goal is not to fully reimplement md-to-anki, but to produce markdown that
fits its expected input format reliably.
"""
from __future__ import annotations

import re
import json
from typing import Iterable


def _build_section_map(text: str, max_lines: int = 200) -> list[dict[str, object]]:
    """Create a compact heading/line-range map instead of repeating the whole file."""
    lines = text.splitlines()
    sections: list[dict[str, object]] = []
    current_heading: str | None = None
    current_start = 1

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            if current_heading is not None:
                sections.append(
                    {
                        "start_line": current_start,
                        "end_line": idx - 1,
                        "heading": current_heading,
                    }
                )
            level = len(stripped) - len(stripped.lstrip("#"))
            current_heading = stripped[level:].strip()
            current_start = idx

    if current_heading is not None:
        sections.append({"start_line": current_start, "end_line": len(lines), "heading": current_heading})

    if len(sections) > max_lines:
        return sections[:max_lines]
    return sections


CONTRACT_NAME = "md-to-anki"


def build_chunk_plan_prompt(text: str, candidate_chunks: list[dict[str, object]]) -> str:
    """Ask the model to revise auto-selected chunk boundaries.

    The model receives the whole file plus the current candidate chunks and
    returns a revised JSON chunk plan.
    """
    prompt = [
        "You are planning markdown chunks before conversion into md-to-anki.",
        "Return only valid JSON. No markdown fences, no explanation.",
        "The JSON must have this shape: {\"chunks\": [{\"start_line\": 1, \"end_line\": 10, \"context\": \"...\", \"reason\": \"...\"}]}",
        "Use 1-based inclusive line numbers from the original file.",
        "Each chunk should contain the section's relevant information and should not cut out section-specific information.",
        "Certain headings and subheadings may be excluded as standalone chunks if they are mainly titles or categories; in that case, fold them into the following chunk's context.",
        "Prefer fewer, more semantically complete chunks over many tiny chunks.",
        "Keep chunk order the same as the source file.",
        "If a chunk is only a title, heading, URL, or category label, mark that information as context rather than a standalone chunk body.",
        "If a section has enough content to stand alone, keep it as a chunk and include its context in the context field.",
        "Do not invent new content. Only revise chunk boundaries and contexts.",
    ]
    prompt.append(
        "\nAUTO_SELECTED_CHUNKS (revise boundaries only; the file structure is summarized below):\n"
        + json.dumps(candidate_chunks, ensure_ascii=False, separators=(",", ":"))
    )
    section_map = _build_section_map(text)
    prompt.append("\nSECTION_MAP:\n" + json.dumps(section_map, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(prompt)


def parse_chunk_plan(text: str) -> list[dict[str, object]]:
    """Parse a model response into chunk plan items.

    Accepts a direct list or an object with a `chunks` field.
    """
    cleaned = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()

    payload = json.loads(cleaned)
    if isinstance(payload, dict) and "chunks" in payload:
        chunks = payload["chunks"]
    else:
        chunks = payload
    if not isinstance(chunks, list):
        raise ValueError("Chunk plan must be a list or contain a 'chunks' list")
    return chunks


def _system_rules() -> list[str]:
    return [
        "You convert arbitrary Markdown into md-to-anki compatible Markdown.",
        "Return only Markdown, with no explanation or code fences.",
        "Preserve the document's meaning, order and content (i.e. do not remove or significantly alter it).",
        "Use double blank lines between cards.",
        "Use **bold** or explicit {{c#::text}} cloze markers for the important answer text.",
        "If a sentence reveals the answer later in the same card, cloze the later occurrence too or move the explanation to Extra.",
        "When the answer is a set of options, it is acceptable to hide all key options on the same card (for example, all three items in a 3-item list).",
        "Keep headings, lists, code blocks, and links when they help preserve meaning.",
        "Use --- to separate an Extra field from the card text when needed.",
        "If there is an obvious repeated answer term across multiple lines, keep the cloze consistent across all occurrences.",
        "If a heading is provided as CONTEXT, treat it as topical metadata for the following content, not as a card by itself unless the body explicitly asks for a card.",
    ]


def _examples() -> list[str]:
    return [
        "",
        "Examples:",
        "Input: What is the difference between X and Y.\nY is the bla bla.",
        "Good output: What is the difference between X and {{c1::Y}}?\n\n---\n{{c1::Y}} is the bla bla.",
        "Input: What are the 3 taint options:\n- X\n- Y\n- Z",
        "Good output: What are the 3 taint options: {{c1::X}}, {{c2::Y}}, {{c3::Z}}",
    ]


def build_system_prompt(whole_file: bool = False) -> str:
    """The constant instructions/examples. Sent once per conversation batch."""
    rules = _system_rules()
    if whole_file:
        rules.append("Treat the whole file as a single conversion task and normalize it globally.")
    return "\n".join(rules + _examples())


def build_chunk_user_prompt(*, context: str = "", body: str) -> str:
    """The per-chunk user turn (no system rules; those are the conversation prefix)."""
    parts: list[str] = []
    if context.strip():
        parts.append("CONTEXT:\n" + context.strip())
    parts.append("INPUT:\n" + body.strip() + "\n")
    return "\n\n".join(parts)


def build_initial_prompt(
    text: str,
    *,
    whole_file: bool,
    context: str = "",
    batch_memory: str = "",
) -> str:
    prompt = build_system_prompt(whole_file=whole_file)
    if batch_memory.strip():
        prompt += "\n\nBATCH_MEMORY:\n" + batch_memory.strip()
    if context.strip():
        prompt += "\n\nCONTEXT:\n" + context.strip()
    prompt += "\n\nINPUT:\n" + text.strip() + "\n"
    return prompt


def build_fix_prompt(
    original: str,
    converted: str,
    errors: Iterable[str],
    context: str = "",
    batch_memory: str = "",
) -> str:
    lines = [
        "The current conversion failed validation.",
        "Fix it minimally.",
        "Return only the corrected Markdown.",
        "If CONTEXT is provided, keep it as metadata and do not render it as a standalone card unless necessary.",
        "Validation errors:",
    ]
    for error in errors:
        lines.append(f"- {error}")
    lines.extend([
        ("\nBATCH_MEMORY:\n" + batch_memory.strip()) if batch_memory.strip() else "",
        ("\nCONTEXT:\n" + context.strip()) if context.strip() else "",
        "\nORIGINAL:\n" + original.strip(),
        "\nCURRENT_CONVERSION:\n" + converted.strip(),
    ])
    return "\n".join(part for part in lines if part)


def normalize_llm_markdown(text: str) -> str:
    """Strip common assistant wrappers from generated Markdown."""
    stripped = text.strip()

    fenced = re.fullmatch(r"```(?:markdown)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()

    if stripped.lower().startswith("markdown:\n"):
        stripped = stripped.split("\n", 1)[1].strip()

    return stripped
