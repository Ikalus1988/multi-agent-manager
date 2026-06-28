# Minimal memory layer plan

The current MVP is intentionally small: local API first, static export second.
It replaces the earlier multi-node vote workflow with an implementation path for
shared collaboration memory.

## What ships in v0

- `MemoryItem` table in the existing SQLite database.
- Local-only append/search API under `/api/memory/*`.
- Public/export boundary enforced by `sensitivity` + `sync_status`.
- Static export script writing `public/memory/items.jsonl` and
  `public/memory/index.json`.
- Basic `/memory` page for local inspection.

## Why this shape

Session context shows the real pain is scattered agent output, not a lack of
formal voting. The minimal layer lets each agent leave a compact, structured note
that another agent can find later. GitHub or misakanet.org can consume the same
sanitized JSONL export when cross-machine or cloud-only access is needed.

## Security posture

- Default item boundary: `private-local-only` + `local-only`.
- Export-ready statuses are rejected unless the item is `public` or
  `project-public`.
- Public content is scanned for common token assignments, bearer tokens, Windows
  paths, Unix home paths, UNC paths, and private/internal URLs.
- The scanner is a guardrail, not a sanitizer. Agents should write sanitized
  summaries instead of raw transcripts.

## Next implementation steps after this PR

1. Add a tiny CLI helper so local agents can run `python scripts/add_memory.py`.
2. Add pagination and tag filtering if item volume grows.
3. Let misakanet.org read `public/memory/index.json` and `items.jsonl` as static
   files before adding any write API.
4. Add optional full-text search or embeddings only after append/search/export is
   proven useful.
5. Add migration support if existing SQLite deployments need non-destructive
   schema upgrades; this PR assumes a fresh MVP database.
