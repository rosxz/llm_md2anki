"""Simple validator for the MVP output format."""
from __future__ import annotations

import re
from typing import List


class ValidationError(Exception):
    def __init__(self, message: str, start_line: int = 0, end_line: int = 0):
        super().__init__(message)
        self.start_line = start_line
        self.end_line = end_line


def validate_converted_markdown(text: str) -> List[ValidationError]:
    """Return validation errors for common format issues.

    MVP rules:
    - cards are separated by one or more blank lines
    - fenced code blocks must be balanced
    - cloze markers must be balanced if present
    """
    errors = []
    blocks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
    line_offset = 0
    for block in blocks:
        fence_count = block.count("```")
        if fence_count % 2 != 0:
            errors.append(ValidationError("Unbalanced fenced code block", line_offset, line_offset + block.count("\n")))

        if block.count("{{") != block.count("}}"):
            errors.append(ValidationError("Unbalanced cloze braces", line_offset, line_offset + block.count("\n")))

        line_offset += block.count("\n") + 2
    return errors
