"""
Tree-sitter parser loader for AI Doc Generator.

Provides cached parser instances for multiple programming languages using
the pre-built grammars from the tree-sitter-languages package. This avoids
the need to compile grammars from source at runtime.
"""

from functools import lru_cache

from tree_sitter import Language, Parser
from tree_sitter_languages import get_language, get_parser as _get_ts_parser

from logger import setup_logger

logger = setup_logger("tree_sitter_loader")

# Languages supported for full AST parsing
SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {
        "python",
        "javascript",
        "typescript",
        "go",
        "java",
        "rust",
        "cpp",
        "c",
        "ruby",
        "php",
    }
)


@lru_cache(maxsize=32)
def get_language_grammar(language: str) -> Language:
    """
    Return the compiled tree-sitter Language grammar for a given language.

    Uses the pre-built grammars shipped with tree-sitter-languages.

    Args:
        language: Language name (e.g. "python", "javascript").

    Returns:
        A tree_sitter.Language object for the requested grammar.

    Raises:
        ValueError: If the language is not supported.
        RuntimeError: If the grammar cannot be loaded.

    Example:
        >>> lang = get_language_grammar("python")
        >>> print(lang)
        <Language python>
    """
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language: '{language}'. "
            f"Supported: {sorted(SUPPORTED_LANGUAGES)}"
        )
    try:
        lang = get_language(language)
        logger.debug("Loaded grammar for: %s", language)
        return lang
    except Exception as exc:
        raise RuntimeError(f"Failed to load grammar for '{language}': {exc}") from exc


@lru_cache(maxsize=32)
def get_parser(language: str) -> Parser:
    """
    Return a configured tree-sitter Parser for the given language.

    Results are cached so each language parser is only instantiated once.

    Args:
        language: Language name (e.g. "python", "go").

    Returns:
        A tree_sitter.Parser instance ready to parse source code.

    Raises:
        ValueError: If the language is not supported.

    Example:
        >>> parser = get_parser("python")
        >>> tree = parser.parse(b"def hello(): pass")
        >>> print(tree.root_node.type)
        module
    """
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language: '{language}'. "
            f"Supported: {sorted(SUPPORTED_LANGUAGES)}"
        )
    try:
        parser = _get_ts_parser(language)
        logger.debug("Parser ready for: %s", language)
        return parser
    except Exception as exc:
        raise RuntimeError(f"Failed to create parser for '{language}': {exc}") from exc


def is_supported(language: str) -> bool:
    """
    Check whether a language has a tree-sitter parser available.

    Args:
        language: Language name string.

    Returns:
        True if parsing is supported for this language.

    Example:
        >>> is_supported("python")
        True
        >>> is_supported("cobol")
        False
    """
    return language in SUPPORTED_LANGUAGES
