llm_md2anki — LLM-assisted Markdown → Anki MVP
=============================================

This is a minimal MVP that implements an LLM-driven conversion workflow for turning arbitrary Markdown into the expected `md-to-anki`-style markdown (cloze-ready, card-split). It supports whole-file or chunked conversion, creates temporary suggested/user-edit files when fixes are needed, and includes a pluggable provider interface for LLMs.

Usage (basic):

```bash
python -m llm_md2anki.cli convert input.md --chunked
```

Or read from stdin:

```bash
cat messy.md | python -m llm_md2anki.cli convert - --whole
```

Requirements: see `requirements.txt`.

This is an MVP for iterative development; it intentionally keeps the validation rules simple so it can be extended and integrated with `md-to-anki` later.
