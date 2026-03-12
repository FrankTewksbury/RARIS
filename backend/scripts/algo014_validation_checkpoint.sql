UPDATE manifests
SET checkpoint_data = jsonb_build_object(
  'type', 'algo014_validation',
  'batch_n', 0,
  'api_calls_used', 0,
  'written_at', now() AT TIME ZONE 'UTC',
  'visited', (
    SELECT jsonb_agg(id)
    FROM sources
    WHERE manifest_id = 'raris-manifest-insurance---domain-regulations-20260311023257'
      AND id != 'new-jersey-department-of-banking-and-insurance__src-njac-title-11'
  ),
  'queue_items', jsonb_build_array(
    jsonb_build_object(
      'target_type', 'source_title',
      'target_id', 'new-jersey-department-of-banking-and-insurance__src-njac-title-11',
      'priority', 5,
      'depth', 2,
      'discovered_from', 'algo014_validation',
      'metadata', jsonb_build_object(
        'id', 'new-jersey-department-of-banking-and-insurance__src-njac-title-11',
        'name', 'N.J.A.C. Title 11 — Insurance (Administrative Code)',
        'citation', 'N.J.A.C. Title 11',
        'url', 'https://www.nj.gov/dobi/legsregs.htm',
        'type', 'regulation',
        'jurisdiction_code', 'NJ',
        'citation_format_hint', 'N.J.A.C.',
        'regulatory_body', 'new-jersey-department-of-banking-and-insurance',
        'sector_key', 'insurance_state',
        'depth_hint', 'title'
      )
    )
  )
)
WHERE id = 'raris-manifest-insurance---domain-regulations-20260311023257'
RETURNING
  jsonb_array_length(checkpoint_data->'queue_items') AS queue_items,
  jsonb_array_length(checkpoint_data->'visited') AS visited,
  checkpoint_data->>'written_at' AS written_at;
