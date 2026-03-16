"""
Code chunking module for AI Doc Generator.

Splits source files into semantic, LLM-friendly chunks keyed by
function, class, or file granularity. Chunks are the primary input
to the embedding index and documentation generators.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from logger import setup_logger
from parser.symbol_extractor import FileSymbols, FunctionSymbol, ClassSymbol
from config import settings

logger = setup_logger("code_chunker")

ChunkType = Literal["function", "class", "method", "file"]

MAX_CHUNK_CHARS = 8_000  # ~2k tokens; stay within embedding model limits


@dataclass
class CodeChunk:
    """A logical chunk of source code with metadata."""

    type: ChunkType
    name: str
    file: str
    language: str
    code: str
    start_line: int = 0
    end_line: int = 0
    parent_class: str | None = None   # set for method chunks
    summary: str | None = None        # optional LLM-generated summary

    def to_dict(self) -> dict:
        """Serialize to plain dict."""
        return {
            "type": self.type,
            "name": self.name,
            "file": self.file,
            "language": self.language,
            "code": self.code,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "parent_class": self.parent_class,
            "summary": self.summary,
        }

    @property
    def id(self) -> str:
        """Unique identifier for the chunk."""
        parts = [self.file, self.type, self.name]
        if self.parent_class:
            parts.insert(2, self.parent_class)
        return "::".join(parts)


def chunk_file(file_path: str | Path, symbols: FileSymbols) -> list[CodeChunk]:
    """
    Chunk a source file into semantic code units.

    Strategy:
    1. One chunk per top-level function.
    2. One chunk per class (including its full body).
    3. One chunk per class method.
    4. If no symbols found, one file-level chunk.

    Args:
        file_path: Path to the source file.
        symbols: Pre-extracted symbols for this file.

    Returns:
        List of :class:`CodeChunk` objects.

    Example:
        >>> chunks = chunk_file("auth.py", symbols)
        >>> print(chunks[0].type)
        function
        >>> print(chunks[0].name)
        login
    """
    path = Path(file_path)
    try:
        source_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        logger.warning("Cannot read %s: %s", file_path, exc)
        return []

    chunks: list[CodeChunk] = []
    language = symbols.language

    # ---- Function chunks --------------------------------------------------
    for func in symbols.functions:
        code = _extract_lines(source_lines, func.start_line, func.end_line)
        chunks.append(
            CodeChunk(
                type="function",
                name=func.name,
                file=str(file_path),
                language=language,
                code=code,
                start_line=func.start_line,
                end_line=func.end_line,
            )
        )

    # ---- Class + method chunks --------------------------------------------
    for cls in symbols.classes:
        class_code = _extract_lines(source_lines, cls.start_line, cls.end_line)
        chunks.append(
            CodeChunk(
                type="class",
                name=cls.name,
                file=str(file_path),
                language=language,
                code=class_code,
                start_line=cls.start_line,
                end_line=cls.end_line,
            )
        )
        for method in cls.methods:
            method_code = _extract_lines(source_lines, method.start_line, method.end_line)
            chunks.append(
                CodeChunk(
                    type="method",
                    name=method.name,
                    file=str(file_path),
                    language=language,
                    code=method_code,
                    start_line=method.start_line,
                    end_line=method.end_line,
                    parent_class=cls.name,
                )
            )

    # ---- Fallback: file-level chunk ---------------------------------------
    if not chunks:
        full_code = "\n".join(source_lines)
        chunks.append(
            CodeChunk(
                type="file",
                name=path.name,
                file=str(file_path),
                language=language,
                code=full_code[:MAX_CHUNK_CHARS],
                start_line=1,
                end_line=len(source_lines),
            )
        )

    logger.debug("Chunked %s → %d chunks", file_path, len(chunks))
    return chunks


def chunk_repository(
    files: list[str | Path],
    symbols_map: dict[str, FileSymbols],
    max_workers: int | None = None,
) -> list[CodeChunk]:
    """
    Chunk all files in a repository in parallel.

    Args:
        files: List of source file paths.
        symbols_map: Map of file_path → FileSymbols from the symbol extractor.
        max_workers: Number of parallel workers (defaults to settings.max_workers).

    Returns:
        Flat list of all :class:`CodeChunk` objects across the repository.

    Example:
        >>> chunks = chunk_repository(files, symbols_map)
        >>> print(f"Total chunks: {len(chunks)}")
        Total chunks: 284
    """
    workers = max_workers or settings.max_workers
    all_chunks: list[CodeChunk] = []

    def _chunk_one(file_path: str | Path) -> list[CodeChunk]:
        key = str(file_path)
        syms = symbols_map.get(key)
        if syms is None:
            return []
        return chunk_file(file_path, syms)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_chunk_one, f): f for f in files}
        for future in concurrent.futures.as_completed(futures):
            try:
                all_chunks.extend(future.result())
            except Exception as exc:
                logger.warning("Chunking failed for %s: %s", futures[future], exc)

    logger.info("Repository chunking complete: %d total chunks", len(all_chunks))
    return all_chunks


def get_chunk_stats(chunks: list[CodeChunk]) -> dict:
    """
    Compute statistics about a list of chunks.

    Args:
        chunks: List of CodeChunk objects.

    Returns:
        Dict with counts broken down by type and language.
    """
    by_type: dict[str, int] = {}
    by_lang: dict[str, int] = {}
    total_chars = 0

    for chunk in chunks:
        by_type[chunk.type] = by_type.get(chunk.type, 0) + 1
        by_lang[chunk.language] = by_lang.get(chunk.language, 0) + 1
        total_chars += len(chunk.code)

    return {
        "total": len(chunks),
        "by_type": by_type,
        "by_language": by_lang,
        "total_chars": total_chars,
        "avg_chars": total_chars // len(chunks) if chunks else 0,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_lines(lines: list[str], start: int, end: int) -> str:
    """
    Extract a range of source lines (1-indexed, inclusive).

    Truncates to MAX_CHUNK_CHARS to stay within embedding model limits.
    """
    start_idx = max(0, start - 1)
    end_idx = min(len(lines), end)
    code = "\n".join(lines[start_idx:end_idx])
    if len(code) > MAX_CHUNK_CHARS:
        code = code[:MAX_CHUNK_CHARS] + "\n# ... [truncated]"
    return code
