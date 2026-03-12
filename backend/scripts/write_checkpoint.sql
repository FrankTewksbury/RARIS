UPDATE manifests
SET checkpoint_data = jsonb_build_object(
  'type', 'depth_hint_repair',
  'batch_n', 0,
  'api_calls_used', 0,
  'written_at', now() AT TIME ZONE 'UTC',
  'visited', (
    SELECT jsonb_agg(id)
    FROM sources
    WHERE manifest_id = 'raris-manifest-insurance---domain-regulations-20260311023257'
      AND depth_hint != 'title'
  ),
  'queue_items', (
    SELECT jsonb_agg(
      jsonb_build_object(
        'target_type', 'source_title',
        'target_id', s.id,
        'priority', 5,
        'depth', 2,
        'discovered_from', '',
        'metadata', jsonb_build_object(
          'citation', s.citation,
          'url', s.url,
          'manifest_id', s.manifest_id
        )
      )
    )
    FROM sources s
    WHERE s.manifest_id = 'raris-manifest-insurance---domain-regulations-20260311023257'
      AND s.depth_hint = 'title'
      AND NOT EXISTS (
        SELECT 1 FROM sources c
        WHERE c.manifest_id = s.manifest_id
          AND c.id LIKE s.id || '__%'
      )
  )
)
WHERE id = 'raris-manifest-insurance---domain-regulations-20260311023257'
RETURNING
  jsonb_array_length(checkpoint_data->'queue_items') AS queue_items,
  jsonb_array_length(checkpoint_data->'visited') AS visited,
  checkpoint_data->>'written_at' AS written_at;
