# Decisions Log

## 2026-02-25
- Initial scaffold created. Project type: application/full-stack. Persona: Lolita. PID: PID-RA7X1.
- Tech stack locked: Python/FastAPI + React/TypeScript + PostgreSQL + Redis
- LLM: configurable provider (openai | anthropic | gemini)
- Insurance domain selected as Phase 1 first vertical (all US, all lines)
- Phase 0 is next execution target
- Hybrid dev environment: Docker for db + redis only, backend/frontend run natively (faster iteration on Windows)
- Documentation minify standard: keep specs lean, no prose bloat
- In-memory asyncio.Queue for SSE event streaming (swap to Redis pub/sub for prod)
- Firecrawl optional with httpx static fallback — avoids hard dependency on paid API
- SHA-256 content hashing for staging dedup
- Phase 3 spec: section-based semantic chunking (preserves regulatory hierarchy)
- Phase 3 spec: pgvector + tsvector hybrid index in single PostgreSQL instance
- Phase 4 spec: 4 depth levels (Quick Check → Exhaustive) mapping to real compliance use cases
- Phase 4 spec: RRF (Reciprocal Rank Fusion) for combining dense + sparse search
- Phase 5 spec: YAML-based vertical config for domain onboarding
- Phase 6 spec: feedback-to-source tracer with auto confidence adjustment

## 2026-02-26
- Removed apt-get from backend Dockerfile — all Python deps ship manylinux wheels; eliminates Docker buildkit DNS flakiness on Windows
- Added selectinload to all async manifest queries — lazy-loading throws MissingGreenlet under asyncpg (SQLite tests don't catch this)
- Discovery agent batches source hunter in groups of 10 bodies — single call exceeded output token limits with 50+ bodies
- Landscape mapper prompt rewritten to demand exhaustive enumeration — "group as pattern" instruction was causing 5-state results
- OpenAI provider must forward max_tokens kwarg — was silently ignored, causing truncated responses
- Dashboard switched from single-column to sidebar+main grid — auto-displays results after SSE completion
