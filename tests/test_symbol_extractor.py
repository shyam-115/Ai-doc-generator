"""Tests for parser/symbol_extractor.py"""

from pathlib import Path
import pytest

from parser.symbol_extractor import extract_symbols, parse_file, FileSymbols


class TestParseFile:
    def test_parses_python_file(self, temp_python_file: Path) -> None:
        tree = parse_file(temp_python_file, "python")
        assert tree is not None
        assert tree.root_node.type == "module"

    def test_returns_none_for_unsupported_language(self, temp_python_file: Path) -> None:
        result = parse_file(temp_python_file, "cobol")
        assert result is None

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        result = parse_file(tmp_path / "nonexistent.py", "python")
        assert result is None


class TestExtractSymbols:
    def test_extracts_python_functions(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        func_names = [f.name for f in symbols.functions]
        assert "get_user" in func_names
        assert "delete_user" in func_names

    def test_extracts_python_class(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        class_names = [c.name for c in symbols.classes]
        assert "AuthService" in class_names

    def test_extracts_class_methods(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        auth_cls = next((c for c in symbols.classes if c.name == "AuthService"), None)
        assert auth_cls is not None
        method_names = [m.name for m in auth_cls.methods]
        assert "login" in method_names
        assert "__init__" in method_names

    def test_extracts_imports(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        modules = [i.module for i in symbols.imports]
        assert "os" in modules

    def test_returns_empty_symbols_for_unsupported_language(
        self, temp_python_file: Path
    ) -> None:
        symbols = extract_symbols(temp_python_file, "brainfuck")
        assert symbols.functions == []
        assert symbols.classes == []

    def test_file_and_language_in_result(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        assert symbols.file == str(temp_python_file)
        assert symbols.language == "python"

    def test_function_has_line_numbers(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        for func in symbols.functions:
            assert func.start_line > 0
            assert func.end_line >= func.start_line

    def test_to_dict_serialization(self, temp_python_file: Path) -> None:
        symbols = extract_symbols(temp_python_file, "python")
        d = symbols.to_dict()
        assert d["file"] == str(temp_python_file)
        assert isinstance(d["functions"], list)
        assert isinstance(d["classes"], list)
        assert isinstance(d["imports"], list)

    def test_javascript_extraction(self, tmp_path: Path) -> None:
        js_file = tmp_path / "app.js"
        js_file.write_text(
            "function greet(name) { return 'Hello ' + name; }\n"
            "const add = (a, b) => a + b;\n"
        )
        symbols = extract_symbols(js_file, "javascript")
        # greet should be found; arrow functions may vary by assignment detection
        assert len(symbols.functions) >= 1
