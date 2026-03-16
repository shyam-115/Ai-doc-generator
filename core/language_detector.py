"""
Language detection module for AI Doc Generator.

Maps file extensions to their corresponding programming language strings.
Supports all major languages processed by the AST parsing pipeline.
"""

from pathlib import Path
from logger import setup_logger

logger = setup_logger("language_detector")

# Extension → language mapping
EXTENSION_MAP: dict[str, str] = {
    # Python
    ".py": "python",
    ".pyw": "python",
    ".pyi": "python",
    # JavaScript
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    # TypeScript
    ".ts": "typescript",
    ".tsx": "typescript",
    # Go
    ".go": "go",
    # Java
    ".java": "java",
    # Rust
    ".rs": "rust",
    # C / C++
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    # C#
    ".cs": "csharp",
    # Ruby
    ".rb": "ruby",
    # PHP
    ".php": "php",
    # Swift
    ".swift": "swift",
    # Kotlin
    ".kt": "kotlin",
    ".kts": "kotlin",
    # Scala
    ".scala": "scala",
    # Shell
    ".sh": "bash",
    ".bash": "bash",
    # Data / Config formats
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    # Web
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    # Docs
    ".md": "markdown",
    ".rst": "rst",
}

# Languages for which tree-sitter-based AST parsing is available
PARSEABLE_LANGUAGES: frozenset[str] = frozenset(
    {"python", "javascript", "typescript", "go", "java", "rust", "cpp", "c"}
)


def detect_language(file_path: str | Path) -> dict:
    """
    Detect the programming language of a single file based on its extension.

    Args:
        file_path: Path to the source file.

    Returns:
        Dict with keys ``file`` (str) and ``language`` (str | None).

    Example:
        >>> detect_language("src/auth.py")
        {'file': 'src/auth.py', 'language': 'python'}
        >>> detect_language("README.md")
        {'file': 'README.md', 'language': 'markdown'}
        >>> detect_language("Makefile")
        {'file': 'Makefile', 'language': None}
    """
    path = Path(file_path)
    language = EXTENSION_MAP.get(path.suffix.lower())

    return {
        "file": str(file_path),
        "language": language,
    }


def detect_languages(files: list[str | Path]) -> list[dict]:
    """
    Detect the language for a list of files.

    Args:
        files: List of file paths.

    Returns:
        List of dicts, each with ``file`` and ``language`` keys.
        Files with unknown extensions have ``language=None``.

    Example:
        >>> results = detect_languages(["main.py", "app.js", "Dockerfile"])
        >>> [r["language"] for r in results]
        ['python', 'javascript', None]
    """
    results = [detect_language(f) for f in files]
    unknown = sum(1 for r in results if r["language"] is None)
    if unknown:
        logger.debug("%d files have unknown/unsupported extensions.", unknown)
    return results


def filter_parseable(detected: list[dict]) -> list[dict]:
    """
    Filter detected files to those with AST-parseable languages.

    Args:
        detected: Output from :func:`detect_languages`.

    Returns:
        Subset where ``language`` is in PARSEABLE_LANGUAGES.

    Example:
        >>> parseable = filter_parseable(detect_languages(["a.py", "b.md"]))
        >>> [r["language"] for r in parseable]
        ['python']
    """
    return [r for r in detected if r.get("language") in PARSEABLE_LANGUAGES]


def group_by_language(detected: list[dict]) -> dict[str, list[str]]:
    """
    Group file paths by detected language.

    Args:
        detected: Output from :func:`detect_languages`.

    Returns:
        Dict mapping language name → list of file paths.

    Example:
        >>> groups = group_by_language(detect_languages(["a.py", "b.py", "c.js"]))
        >>> groups["python"]
        ['a.py', 'b.py']
    """
    groups: dict[str, list[str]] = {}
    for entry in detected:
        lang = entry.get("language") or "unknown"
        groups.setdefault(lang, []).append(entry["file"])
    return groups
