"""Section-aware chunking utilities."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List


@dataclass(frozen=True)
class Chunk:
    start_line: int
    end_line: int
    context: str
    body: str


def split_by_headings(text: str, min_lines: int = 20) -> List[Chunk]:
    """Split markdown into chunks with inherited heading context.

    The top-level heading is treated as context for all following chunks, not
    as its own card. Each chunk contains the full heading path in `context` and
    only the body text that should be converted.
    """
    lines = text.splitlines()
    if not lines:
        return []

    chunks: List[Chunk] = []
    heading_stack: list[str] = []
    body_start = 0
    current_heading_line = 0

    def flush_body(end_line: int) -> None:
        nonlocal body_start
        body_lines = lines[body_start:end_line]
        body = "\n".join(body_lines).strip()
        if body and not _is_trivial_preamble(body):
            context = " / ".join(heading_stack)
            chunks.append(Chunk(body_start, end_line - 1, context, body))

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            if idx > body_start:
                flush_body(idx)

            level = len(stripped) - len(stripped.lstrip("#"))
            heading_text = stripped[level:].strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(heading_text)
            body_start = idx + 1
            current_heading_line = idx

    flush_body(len(lines))

    if not chunks:
        if len(lines) <= min_lines:
            return [Chunk(0, len(lines) - 1, "", text.strip())]

        size = max(min_lines, len(lines) // max(1, len(lines) // min_lines))
        for start in range(0, len(lines), size):
            end = min(len(lines), start + size)
            body = "\n".join(lines[start:end]).strip()
            if body:
                chunks.append(Chunk(start, end - 1, "", body))

    return chunks


def _is_trivial_preamble(body: str) -> bool:
    """Detect heading-adjacent filler that should be treated as context only."""
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return True

    if len(lines) == 1:
        line = lines[0]
        if re.fullmatch(r"https?://\S+|<https?://\S+>", line):
            return True
        if len(line) < 8 and not re.search(r"[A-Za-z]", line):
            return True

    return False
