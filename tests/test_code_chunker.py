"""Tests for chunking/code_chunker.py"""

from pathlib import Path
import pytest

from chunking.code_chunker import chunk_file, chunk_repository, get_chunk_stats, CodeChunk
from parser.symbol_extractor import extract_symbols


class TestChunkFile:
    def test_chunks_python_functions(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        chunks = chunk_file(temp_python_file, symbols)
        types = {c.type for c in chunks}
        assert "function" in types or "class" in types

    def test_chunk_contains_code(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        chunks = chunk_file(temp_python_file, symbols)
        for chunk in chunks:
            assert len(chunk.code) > 0

    def test_chunk_has_correct_file(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        chunks = chunk_file(temp_python_file, symbols)
        for chunk in chunks:
            assert chunk.file == str(temp_python_file)

    def test_class_chunk_created(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        chunks = chunk_file(temp_python_file, symbols)
        class_chunks = [c for c in chunks if c.type == "class"]
        assert len(class_chunks) >= 1
        assert class_chunks[0].name == "AuthService"

    def test_method_chunk_has_parent_class(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        chunks = chunk_file(temp_python_file, symbols)
        method_chunks = [c for c in chunks if c.type == "method"]
        for mc in method_chunks:
            assert mc.parent_class is not None

    def test_returns_file_chunk_when_no_symbols(self, tmp_path: Path) -> None:
        f = tmp_path / "plain.py"
        f.write_text("x = 1\ny = 2\n")
        from parser.symbol_extractor import FileSymbols
        empty_syms = FileSymbols(file=str(f), language="python")
        chunks = chunk_file(f, empty_syms)
        assert len(chunks) == 1
        assert chunks[0].type == "file"

    def test_chunk_id_is_unique(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        chunks = chunk_file(temp_python_file, symbols)
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_to_dict(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        chunks = chunk_file(temp_python_file, symbols)
        for c in chunks:
            d = c.to_dict()
            assert "type" in d
            assert "name" in d
            assert "code" in d


class TestGetChunkStats:
    def test_stats_keys(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        chunks = chunk_file(temp_python_file, symbols)
        stats = get_chunk_stats(chunks)
        assert "total" in stats
        assert "by_type" in stats
        assert "by_language" in stats
        assert "total_chars" in stats

    def test_total_matches_chunk_count(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        chunks = chunk_file(temp_python_file, symbols)
        stats = get_chunk_stats(chunks)
        assert stats["total"] == len(chunks)
