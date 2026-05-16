# AI Usage

Tool: OpenAI Codex

Used for boilerplate generation and infrastructure scaffolding.

Codex generated initial drafts of some app modules and config files. These were reviewed, tested, and in several cases modified before use. The two-pass query engine structure and the reconciler algorithm were the main areas where generated code was adjusted manually after testing edge cases.

Redis was suggested for caching and rejected. The dict-based cache is enough for single-worker deployment and the interface is already abstracted for a future swap.

## How I verified

- 10 tests pass locally: pytest app/tests/ -v
- Hit /health and /query manually, checked response structure
- Verified reconciler on real CSV data: S001 on 2026-04-01 gives 24.5C from both sources after conversion
- Verified correlation ID echoes back in the response header
