"""Tests for core/language_detector.py"""

import pytest
from core.language_detector import (
    detect_language,
    detect_languages,
    filter_parseable,
    group_by_language,
    EXTENSION_MAP,
    PARSEABLE_LANGUAGES,
)


class TestDetectLanguage:
    @pytest.mark.parametrize("filename,expected_lang", [
        ("main.py",         "python"),
        ("app.js",          "javascript"),
        ("index.ts",        "typescript"),
        ("main.go",         "go"),
        ("Main.java",       "java"),
        ("lib.rs",          "rust"),
        ("handler.cpp",     "cpp"),
        ("header.h",        "c"),
        ("script.sh",       "bash"),
        ("config.yaml",     "yaml"),
        ("config.yml",      "yaml"),
        ("README.md",       "markdown"),
        ("style.css",       "css"),
        ("Makefile",        None),
        ("binary.exe",      None),
        ("file",            None),
    ])
    def test_extension_mapping(self, filename: str, expected_lang) -> None:
        result = detect_language(filename)
        assert result["file"] == filename
        assert result["language"] == expected_lang

    def test_returns_dict_with_correct_keys(self) -> None:
        result = detect_language("test.py")
        assert "file" in result
        assert "language" in result

    def test_case_insensitive_extension(self) -> None:
        # .PY should also map to python
        result = detect_language("MAIN.PY")
        assert result["language"] == "python"


class TestDetectLanguages:
    def test_batch_detection(self) -> None:
        files = ["a.py", "b.js", "c.go", "Makefile"]
        results = detect_languages(files)
        assert len(results) == 4
        langs = [r["language"] for r in results]
        assert langs == ["python", "javascript", "go", None]

    def test_empty_list(self) -> None:
        assert detect_languages([]) == []


class TestFilterParseable:
    def test_filters_to_parseable_only(self) -> None:
        detected = detect_languages(["a.py", "b.md", "c.go", "d.css"])
        parseable = filter_parseable(detected)
        langs = {r["language"] for r in parseable}
        assert langs.issubset(PARSEABLE_LANGUAGES)

    def test_excludes_unknown(self) -> None:
        detected = detect_languages(["Makefile", "foo"])
        assert filter_parseable(detected) == []


class TestGroupByLanguage:
    def test_groups_correctly(self) -> None:
        detected = detect_languages(["a.py", "b.py", "c.js"])
        groups = group_by_language(detected)
        assert len(groups["python"]) == 2
        assert len(groups["javascript"]) == 1

    def test_unknown_extension_goes_to_unknown(self) -> None:
        detected = detect_languages(["Makefile"])
        groups = group_by_language(detected)
        assert "unknown" in groups
