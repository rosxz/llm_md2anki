llm_md2anki — LLM-assisted Markdown → Anki MVP
=============================================

This is a minimal MVP that implements an LLM-driven conversion workflow for turning arbitrary Markdown into the expected `md-to-anki`-style markdown (cloze-ready, card-split). It supports whole-file or chunked conversion, creates temporary suggested/user-edit files when fixes are needed, and includes a pluggable Gemini provider.

Usage (basic):

```bash
cd /home/crea/Projects/llm_md2anki
export GEMINI_API_KEY="your-key"
python -m llm_md2anki convert examples/minimal.md --whole --output /tmp/minimal.converted.md
```

Or read from stdin:

```bash
cat messy.md | python -m llm_md2anki convert - --whole --output /tmp/messy.converted.md
```

Requirements: see `requirements.txt`.

This is an MVP for iterative development; it intentionally keeps the validation rules simple so it can be extended and integrated with `md-to-anki` later.

## Notes

- The converter normalizes output toward `md-to-anki` input expectations, but it does not yet call `md-to-anki` directly.
- The initial workflow is whole-file first, with chunked mode available for larger or messier files.
- Temporary fix suggestions are written to your system temp directory when validation fails.
