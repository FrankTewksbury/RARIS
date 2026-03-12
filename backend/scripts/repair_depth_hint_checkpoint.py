"""
repair_depth_hint_checkpoint.py

One-time repair script for manifest sources missing depth_hint from L1 prompts.

Steps:
  1. Update depth_hint on all NULL sources using type-based classification rules.
  2. Build a BFS queue snapshot from all undrilled sources (depth_hint = 'title')
     that have not yet been expanded (i.e., no child sources exist in the DB).
  3. Write the snapshot as a new checkpoint on the manifest so Resume picks it up.

Usage:
  docker compose exec backend uv run python scripts/repair_depth_hint_checkpoint.py \
      --manifest-id raris-manifest-insurance---domain-regulations-20260311023257 [--dry-run]
"""

import argparse
import asyncio
import datetime
import json
import sys

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

# Adjust path so app imports work when run from /app inside the container
sys.path.insert(0, "/app")

from app.database import async_session
from app.models.manifest import Manifest, Source


# --------------------------------------------------------------------------- #
# depth_hint classification rules by source type
# --------------------------------------------------------------------------- #
TYPE_TO_DEPTH_HINT: dict[str, str] = {
    "statute":    "title",   # top-level code titles → need chapter expansion
    "regulation": "title",   # top-level admin code titles → need chapter expansion
    "guidance":   "leaf",    # bulletins/orders indexes → no children
    "standard":   "leaf",    # advisory standards → no children
    "educational": "leaf",
    "guide":      "leaf",
}

# Map depth_hint → BFS node_type used by the engine
DEPTH_HINT_TO_NODE_TYPE: dict[str, str] = {
    "title":   "source_title",
    "chapter": "source_chapter",
    "section": "source_section",
}


async def run(manifest_id: str, dry_run: bool) -> None:
    async with async_session() as db:
        # ------------------------------------------------------------------ #
        # 1. Fetch manifest
        # ------------------------------------------------------------------ #
        manifest = await db.get(Manifest, manifest_id)
        if manifest is None:
            print(f"ERROR: manifest '{manifest_id}' not found.")
            sys.exit(1)
        print(f"Manifest: {manifest_id}  status={manifest.status}")

        # ------------------------------------------------------------------ #
        # 2. Count NULL depth_hint sources
        # ------------------------------------------------------------------ #
        null_count_result = await db.execute(
            select(func.count()).select_from(Source).where(
                Source.manifest_id == manifest_id,
                Source.depth_hint.is_(None),
            )
        )
        null_count = null_count_result.scalar() or 0
        print(f"Sources with NULL depth_hint: {null_count}")

        if null_count == 0:
            print("Nothing to repair.")
            return

        # ------------------------------------------------------------------ #
        # 3. Update depth_hint per type using raw SQL to avoid enum cast issues
        # ------------------------------------------------------------------ #
        from sqlalchemy import text as _text

        update_sql = _text("""
            UPDATE sources
            SET depth_hint = CASE type::text
                WHEN 'statute'    THEN 'title'
                WHEN 'regulation' THEN 'title'
                WHEN 'guidance'   THEN 'leaf'
                WHEN 'standard'   THEN 'leaf'
                WHEN 'educational' THEN 'leaf'
                WHEN 'guide'      THEN 'leaf'
                ELSE 'leaf'
            END
            WHERE manifest_id = :manifest_id
              AND depth_hint IS NULL
        """)

        if dry_run:
            # Preview counts per type without updating
            preview_sql = _text("""
                SELECT type::text, COUNT(*),
                    CASE type::text
                        WHEN 'statute'    THEN 'title'
                        WHEN 'regulation' THEN 'title'
                        ELSE 'leaf'
                    END AS would_set
                FROM sources
                WHERE manifest_id = :manifest_id AND depth_hint IS NULL
                GROUP BY type::text
                ORDER BY type::text
            """)
            result = await db.execute(preview_sql, {"manifest_id": manifest_id})
            updated_total = 0
            for row in result.fetchall():
                print(f"  [DRY-RUN] Would set depth_hint='{row[2]}' on {row[1]} sources of type='{row[0]}'")
                updated_total += row[1]
        else:
            result = await db.execute(update_sql, {"manifest_id": manifest_id})
            updated_total = result.rowcount
            await db.commit()
            print(f"Committed depth_hint updates ({updated_total} rows).")

        # ------------------------------------------------------------------ #
        # 4. Find all undrilled 'title' sources (no child sources yet)
        # ------------------------------------------------------------------ #
        # A source is "undrilled" if no other source has an id that starts with
        # this source's id + "__" (the compound ID separator used by the engine).
        # We approximate this by fetching all title-level sources and checking
        # for children.
        title_sources_result = await db.execute(
            select(Source).where(
                Source.manifest_id == manifest_id,
                Source.depth_hint == "title",
            )
        )
        title_sources = title_sources_result.scalars().all()
        print(f"\nTotal 'title' sources after repair: {len(title_sources)}")

        # Fetch all source IDs for child-check
        all_ids_result = await db.execute(
            select(Source.id).where(Source.manifest_id == manifest_id)
        )
        all_ids: set[str] = {row[0] for row in all_ids_result.fetchall()}

        # Also collect visited set = all source IDs already in DB (already processed)
        # The engine uses visited to skip re-expansion; we pre-populate with all
        # non-title sources so we don't re-expand anything already done.
        visited_sources_result = await db.execute(
            select(Source.id).where(
                Source.manifest_id == manifest_id,
                Source.depth_hint != "title",
            )
        )
        visited: list[str] = [row[0] for row in visited_sources_result.fetchall()]

        undrilled: list[Source] = []
        for src in title_sources:
            prefix = src.id + "__"
            has_children = any(sid.startswith(prefix) for sid in all_ids)
            if not has_children:
                undrilled.append(src)

        print(f"Undrilled 'title' sources (no children yet): {len(undrilled)}")

        if not undrilled:
            print("All title sources already have children — no checkpoint needed.")
            return

        # ------------------------------------------------------------------ #
        # 5. Build queue snapshot matching DiscoveryQueue.to_snapshot() shape
        # ------------------------------------------------------------------ #
        queue_items = []
        for src in undrilled:
            node_type = DEPTH_HINT_TO_NODE_TYPE.get(src.depth_hint or "title", "source_title")
            queue_items.append({
                "target_type":    node_type,
                "target_id":      src.id,
                "priority":       5,
                "depth":          2,
                "discovered_from": "",
                "metadata": {
                    "source_id":   src.id,
                    "citation":    src.citation,
                    "url":         src.url,
                    "manifest_id": manifest_id,
                },
            })

        checkpoint = {
            "type":           "depth_hint_repair",
            "batch_n":        0,
            "api_calls_used": 0,
            "queue_items":    queue_items,
            "visited":        visited,
            "written_at":     datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        print(f"\nCheckpoint summary:")
        print(f"  queue_items : {len(queue_items)}")
        print(f"  visited     : {len(visited)}")
        print(f"  written_at  : {checkpoint['written_at']}")

        if dry_run:
            print("\n[DRY-RUN] Checkpoint NOT written. Re-run without --dry-run to apply.")
            sample = queue_items[:3]
            print(f"Sample queue items: {json.dumps(sample, indent=2)}")
            return

        # ------------------------------------------------------------------ #
        # 6. Write checkpoint to manifest
        # ------------------------------------------------------------------ #
        manifest.checkpoint_data = checkpoint
        await db.commit()
        print(f"\nCheckpoint written to manifest '{manifest_id}'.")
        print(f"You can now click Resume in the UI to expand the {len(queue_items)} undrilled sources.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair depth_hint and write BFS checkpoint.")
    parser.add_argument("--manifest-id", required=True, help="Target manifest ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to DB")
    args = parser.parse_args()
    asyncio.run(run(args.manifest_id, args.dry_run))


if __name__ == "__main__":
    main()
