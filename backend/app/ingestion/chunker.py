"""Semantic chunker — section-aware splitting with overlap and hierarchy preservation."""

from dataclasses import dataclass

import tiktoken

from app.config import settings
from app.ingestion.base import ExtractedSection

_enc = tiktoken.encoding_for_model("gpt-4o")


@dataclass
class ChunkResult:
    section_id: str
    section_path: str
    text: str
    token_count: int
    position: int


def chunk_document(
    sections: list[ExtractedSection],
    doc_id: str,
    min_tokens: int | None = None,
    max_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[ChunkResult]:
    """Split sections into chunks respecting structure and token limits.

    Each section is split independently. Chunks retain their section path
    for hierarchy preservation.
    """
    min_tok = min_tokens or settings.chunk_min_tokens
    max_tok = max_tokens or settings.chunk_max_tokens
    overlap = overlap_tokens or settings.chunk_overlap_tokens

    chunks: list[ChunkResult] = []
    position = 0

    def _process_section(section: ExtractedSection, path_parts: list[str]) -> None:
        nonlocal position

        if section.heading:
            current_path = " > ".join(path_parts + [section.heading])
        else:
            current_path = " > ".join(path_parts)

        if section.text.strip():
            section_chunks = _split_text(
                section.text.strip(),
                section.id,
                current_path,
                max_tok,
                overlap,
                position,
            )
            for c in section_chunks:
                chunks.append(c)
                position += 1

        for child in section.children:
            _process_section(child, path_parts + [section.heading])

    for section in sections:
        _process_section(section, [])

    # Merge tiny trailing chunks
    chunks = _merge_small_chunks(chunks, min_tok)

    return chunks


def _split_text(
    text: str,
    section_id: str,
    section_path: str,
    max_tokens: int,
    overlap: int,
    start_position: int,
) -> list[ChunkResult]:
    """Split text into token-bounded chunks with overlap."""
    tokens = _enc.encode(text)
    total = len(tokens)

    if total <= max_tokens:
        return [ChunkResult(
            section_id=section_id,
            section_path=section_path,
            text=text,
            token_count=total,
            position=start_position,
        )]

    results: list[ChunkResult] = []
    start = 0
    pos = start_position

    while start < total:
        end = min(start + max_tokens, total)
        chunk_tokens = tokens[start:end]
        chunk_text = _enc.decode(chunk_tokens)

        # Try to break at a sentence or paragraph boundary
        chunk_text = _snap_to_boundary(chunk_text)
        actual_tokens = len(_enc.encode(chunk_text))

        results.append(ChunkResult(
            section_id=section_id,
            section_path=section_path,
            text=chunk_text,
            token_count=actual_tokens,
            position=pos,
        ))
        pos += 1

        # Advance with overlap
        advance = len(_enc.encode(chunk_text)) - overlap
        if advance <= 0:
            advance = max_tokens // 2
        start += advance

    return results


def _snap_to_boundary(text: str) -> str:
    """Try to end the chunk at a sentence or paragraph boundary."""
    # Look for the last sentence-ending punctuation in the last 20% of text
    cutoff = int(len(text) * 0.8)
    tail = text[cutoff:]

    # Try paragraph break first
    last_para = tail.rfind("\n\n")
    if last_para > 0:
        return text[: cutoff + last_para].strip()

    # Try sentence end
    for marker in (". ", ".\n", ";\n", ".\t"):
        last_sent = tail.rfind(marker)
        if last_sent > 0:
            return text[: cutoff + last_sent + 1].strip()

    return text.strip()


def _merge_small_chunks(chunks: list[ChunkResult], min_tokens: int) -> list[ChunkResult]:
    """Merge chunks that are too small into their predecessor."""
    if len(chunks) <= 1:
        return chunks

    merged: list[ChunkResult] = [chunks[0]]

    for c in chunks[1:]:
        prev = merged[-1]
        if c.token_count < min_tokens and prev.section_id == c.section_id:
            # Merge into previous
            merged[-1] = ChunkResult(
                section_id=prev.section_id,
                section_path=prev.section_path,
                text=prev.text + "\n\n" + c.text,
                token_count=prev.token_count + c.token_count,
                position=prev.position,
            )
        else:
            merged.append(c)

    return merged


def count_tokens(text: str) -> int:
    """Count tokens in text using the tiktoken encoder."""
    return len(_enc.encode(text))
