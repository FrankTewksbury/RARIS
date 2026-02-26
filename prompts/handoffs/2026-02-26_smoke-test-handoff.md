---
type: handoff
from: Claude Code
to: Cursor Agent
created: 2026-02-26
source: claude-code
description: Post-smoke-test handoff — integration bugs fixed, discovery deepened, remaining hardening work
---

# Context Handoff — Claude Code → Cursor

**Project:** RARIS (Regulatory Analysis & Research Intelligence System)
**Directory:** X:\RARIS
**Date:** 2026-02-26

---

## MANDATORY READS BEFORE DOING ANYTHING

1. `CLAUDE.md` — Agent entry point, communication rules
2. `docs/DFW-CONSTITUTION.md` — Universal principles P1-P9
3. `docs/DFW-OPERATING-MANUAL.md` — Session lifecycle, tagging, handoff protocol
4. `context/_ACTIVE_CONTEXT.md` — Current project state
5. `context/003-journal-2026-02-26-smoke-test-and-discovery-depth.md` — This session's journal

---

## CONTEXT — What Just Happened

### Docker Smoke Test — PASSED
All 4 containers (PostgreSQL+pgvector, Redis, FastAPI backend, Nginx+React frontend) built and running on `docker compose up`. All 52 API routes reachable, health checks green.

### Bugs Fixed During Smoke Test
5 integration-level bugs were found and fixed that unit tests didn't catch:

1. **`uv.lock` missing from Dockerfile COPY** → `uv sync` failed in container
2. **`JSX.Element` → `ReactNode`** in ResponsePanel (React 19 type break)
3. **`apt-get` unreachable in Docker buildkit** on Windows → removed entirely, all deps ship binary wheels
4. **`MissingGreenlet` on manifest list** → lazy-loaded relationship in async context → added `selectinload`
5. **Trailing newline in domain names** → textarea sends `\n` → added `.strip()`

### Discovery Agent Overhauled
- Landscape mapper prompt now demands ALL 50 states individually (was "give 5 examples")
- Source hunter now **batches in groups of 10** bodies per LLM call (was 1 call for all)
- OpenAI provider now passes `max_tokens` (was silently ignoring it)
- First deep run produced 55+ bodies and 100+ sources

### Frontend Dashboard Revamped
- New sidebar + main layout (domain input + manifest list on left, results on right)
- Auto-displays manifest results when SSE generation completes
- No more "click the sidebar to find your results" confusion

---

## CURRENT STATE

**Branch:** `main`
**All tests:** 230 backend + 16 frontend — passing
**Docker:** All 4 containers running and healthy
**OpenAI API key:** Configured in `.env` (gitignored)

### Files Modified This Session (not yet committed)

| File | Change |
|------|--------|
| `backend/Dockerfile` | Removed apt-get, added uv.lock COPY |
| `backend/app/agent/discovery.py` | Batched source hunting, progress events |
| `backend/app/agent/prompts.py` | Deep discovery prompts (all 50 states) |
| `backend/app/llm/openai_provider.py` | max_tokens passthrough |
| `backend/app/services/manifest_service.py` | selectinload on list_manifests |
| `backend/app/routers/manifests.py` | domain .strip() |
| `frontend/src/pages/Dashboard.tsx` | Sidebar layout, auto-display results |
| `frontend/src/components/retrieval/ResponsePanel.tsx` | JSX.Element → ReactNode |
| `frontend/src/App.css` | Dashboard grid layout, manifest list styles |
| `.env` | OpenAI API key (gitignored) |

---

## YOUR TASK — Remaining Work

### High Priority

#### 1. Commit This Session's Changes
All changes above are unstaged. Commit with a message like:
```
fix: Docker smoke test fixes, deep discovery, dashboard results panel
```

#### 2. RSS / Federal Register Monitoring (Gap #3)
The change monitor (`app/feedback/monitor.py`) currently only does HTTP hash-check polling. The spec mentions RSS feed monitoring and Federal Register API integration. These are modeled in the data layer but not wired up.

**What to build:**
- RSS feed parser (use `feedparser` library) — poll registered feed URLs, detect new entries
- Federal Register API adapter — `https://www.federalregister.gov/api/v1/documents.json` with date-range filtering
- Wire into the existing `ChangeMonitor` class alongside hash-check
- Add `monitor_type` field to change events: `hash_check | rss | federal_register`

#### 3. Embedding Provider Abstraction (Gap #4)
Embeddings are hardcoded to OpenAI `text-embedding-3-large` in `app/retrieval/search.py` and `app/embedding_cache.py`. If only an Anthropic or Gemini key is set, embedding calls silently fail.

**What to build:**
- `app/embeddings/base.py` — abstract `EmbeddingProvider` with `async embed(texts: list[str]) -> list[list[float]]`
- `app/embeddings/openai_embeddings.py` — current OpenAI implementation
- `app/embeddings/registry.py` — pick provider based on available API keys
- Fallback: Anthropic doesn't offer embeddings, so Gemini's `text-embedding-004` is the alternative
- Update search.py and embedding_cache.py to use the registry

#### 4. Relationship Mapper Batching
With 100+ sources from deep discovery, the relationship mapper's input JSON may exceed input token limits. Apply the same batching pattern used for source hunting.

### Medium Priority

#### 5. Alembic in Production Lifespan (Gap #7)
Currently `Base.metadata.create_all` in `app/main.py` lifespan. In production, should run `alembic upgrade head` instead. Gate on `settings.environment`.

#### 6. Config Security (Gap #8)
- `cors_origins` should be configurable via env var (currently hardcoded to localhost)
- Add `SECRET_KEY` env var for future JWT signing
- Validate that at least one LLM API key is set on startup

#### 7. Ground Truth Eval Dataset (Gap #6)
Create `eval/insurance_ground_truth.json` with 20-30 Insurance domain question-answer pairs for precision@k benchmarking against the live corpus.

### Low Priority

#### 8. Frontend Polish
- Code splitting with `React.lazy` + `Suspense` on page routes
- Better loading/empty states on AcquisitionMonitor and CurationDashboard
- Update page title from "frontend" to "RARIS"

#### 9. CI Improvements
- Add mypy/pyright to CI pipeline
- Add Docker build smoke test to CI (build but don't run)
- Add integration test that boots all containers and hits `/health/ready`

---

## KEY ARCHITECTURE NOTES

### Async SQLAlchemy Gotcha
Any relationship access outside an `async with session:` block will throw `MissingGreenlet`. Always use `selectinload()` or `joinedload()` in queries. Unit tests with SQLite won't catch this — only PostgreSQL under asyncpg will.

### Source Hunter Batching Pattern
`discovery.py` now splits bodies into batches of 10, calls the LLM per batch, and renumbers source IDs globally. Follow this pattern for any LLM call that scales with input size.

### Docker Build on Windows
Docker buildkit has persistent DNS issues reaching `deb.debian.org` from within Debian-based images on Windows Docker Desktop. The fix was to remove all `apt-get` calls and rely on manylinux binary wheels. If a future dependency needs native compilation, consider switching to a pre-built base image.

---

## OPEN QUESTIONS

1. **State body name accuracy** — The LLM generates state department names and URLs. Many will be hallucinated. Need a verification step or a static lookup table of actual state insurance department URLs.
2. **Token budget** — A full 50-state discovery run costs ~$2-5 in OpenAI API calls (6+ source hunter batches × 16K output tokens). Should we add cost estimation to the UI?
3. **Concurrent batch calls** — Source hunter batches run sequentially. Could parallelize with `asyncio.gather` for ~6x speedup, but risks rate limits.

---

*Handoff from Claude Code — 2026-02-26*
