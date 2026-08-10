"""Chunking utilities."""
from typing import List, Tuple


def split_by_headings(text: str, min_lines: int = 20) -> List[Tuple[int, int, str]]:
    """Split markdown by top-level headings. Returns list of (start_line, end_line, chunk_text)."""
    lines = text.splitlines()
    headings = []
    for i, line in enumerate(lines):
        if line.startswith("#"):
            headings.append(i)
    if not headings:
        # fallback: split into roughly equal chunks by lines
        chunks = []
        if len(lines) <= min_lines:
            return [(0, len(lines) - 1, "\n".join(lines))]
        size = max(min_lines, len(lines) // max(1, len(lines) // min_lines))
        for i in range(0, len(lines), size):
            chunks.append((i, min(len(lines) - 1, i + size - 1), "\n".join(lines[i : i + size])))
        return chunks

    # create chunks starting at each heading until next heading
    chunks = []
    for idx, start in enumerate(headings):
        end = headings[idx + 1] - 1 if idx + 1 < len(headings) else len(lines) - 1
        chunks.append((start, end, "\n".join(lines[start : end + 1])))
    return chunks
