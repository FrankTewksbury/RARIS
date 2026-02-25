"""Raw Staging Layer — stores acquired content with full provenance metadata."""

import hashlib
from pathlib import Path

import yaml

STAGING_ROOT = Path("staging")


def compute_hash(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def stage_document(
    manifest_id: str,
    source_id: str,
    content: bytes,
    content_type: str,
    provenance: dict,
) -> dict:
    """Write content and provenance to the staging directory.

    Returns a dict with path, hash, byte_size, and duplicate status.
    """
    content_hash = compute_hash(content)

    # Determine file extension from content type
    ext_map = {
        "text/html": "html",
        "application/pdf": "pdf",
        "application/xml": "xml",
        "text/xml": "xml",
        "text/plain": "txt",
    }
    ext = ext_map.get(content_type, "bin")

    target_dir = STAGING_ROOT / manifest_id / source_id
    target_dir.mkdir(parents=True, exist_ok=True)

    content_path = target_dir / f"content.{ext}"
    provenance_path = target_dir / "provenance.yaml"

    # Check for duplicates across staging
    is_duplicate = _check_duplicate(content_hash)

    if not is_duplicate:
        content_path.write_bytes(content)

    # Always write provenance
    provenance["content_hash"] = content_hash
    provenance["content_type"] = content_type
    provenance["byte_size"] = len(content)
    with open(provenance_path, "w") as f:
        yaml.dump(provenance, f, default_flow_style=False)

    return {
        "raw_content_path": str(target_dir),
        "content_hash": content_hash,
        "byte_size": len(content),
        "is_duplicate": is_duplicate,
    }


def _check_duplicate(content_hash: str) -> bool:
    """Check if a document with this hash already exists in staging."""
    if not STAGING_ROOT.exists():
        return False
    for prov_file in STAGING_ROOT.rglob("provenance.yaml"):
        try:
            with open(prov_file) as f:
                prov = yaml.safe_load(f)
                if prov and prov.get("content_hash") == content_hash:
                    return True
        except Exception:
            continue
    return False
