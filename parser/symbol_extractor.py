"""
Symbol extraction module for AI Doc Generator.

Parses source files using tree-sitter and extracts structured metadata about
functions, classes, methods, and imports. Supports Python, JavaScript,
TypeScript, Go, Java, and Rust.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tree_sitter import Node, Tree

from logger import setup_logger
from parser.tree_sitter_loader import get_parser, is_supported

logger = setup_logger("symbol_extractor")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Parameter:
    """Represents a function parameter."""
    name: str
    type_annotation: str | None = None


@dataclass
class FunctionSymbol:
    """Represents an extracted function or method."""
    name: str
    params: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0
    docstring: str | None = None
    is_async: bool = False
    is_method: bool = False


@dataclass
class ClassSymbol:
    """Represents an extracted class or interface."""
    name: str
    methods: list[FunctionSymbol] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0


@dataclass
class ImportSymbol:
    """Represents an import statement."""
    module: str
    names: list[str] = field(default_factory=list)
    alias: str | None = None


@dataclass
class FileSymbols:
    """Aggregated symbol information for a single file."""
    file: str
    language: str
    functions: list[FunctionSymbol] = field(default_factory=list)
    classes: list[ClassSymbol] = field(default_factory=list)
    imports: list[ImportSymbol] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict for JSON serialization."""
        return {
            "file": self.file,
            "language": self.language,
            "functions": [
                {
                    "name": f.name,
                    "params": f.params,
                    "calls": f.calls,
                    "decorators": f.decorators,
                    "start_line": f.start_line,
                    "end_line": f.end_line,
                    "docstring": f.docstring,
                    "is_async": f.is_async,
                    "is_method": f.is_method,
                }
                for f in self.functions
            ],
            "classes": [
                {
                    "name": c.name,
                    "bases": c.bases,
                    "decorators": c.decorators,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "methods": [
                        {
                            "name": m.name,
                            "params": m.params,
                            "calls": m.calls,
                            "start_line": m.start_line,
                            "end_line": m.end_line,
                        }
                        for m in c.methods
                    ],
                }
                for c in self.classes
            ],
            "imports": [
                {"module": i.module, "names": i.names, "alias": i.alias}
                for i in self.imports
            ],
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_file(file_path: str | Path, language: str) -> Tree | None:
    """
    Parse a source file and return the tree-sitter AST.

    Args:
        file_path: Path to the source file.
        language: Programming language identifier.

    Returns:
        A tree_sitter.Tree (root node accessible via .root_node),
        or None if parsing fails.

    Example:
        >>> tree = parse_file("main.py", "python")
        >>> print(tree.root_node.type)
        module
    """
    if not is_supported(language):
        logger.debug("Skipping unsupported language '%s' for file: %s", language, file_path)
        return None

    try:
        source = Path(file_path).read_bytes()
        parser = get_parser(language)
        tree = parser.parse(source)
        return tree
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", file_path, exc)
        return None


def extract_symbols(file_path: str | Path, language: str) -> FileSymbols:
    """
    Extract all symbols (functions, classes, imports) from a source file.

    Args:
        file_path: Path to the source file.
        language: Programming language identifier.

    Returns:
        A :class:`FileSymbols` dataclass with all extracted symbols.

    Example:
        >>> symbols = extract_symbols("auth.py", "python")
        >>> print(symbols.functions[0].name)
        login
    """
    symbols = FileSymbols(file=str(file_path), language=language)

    tree = parse_file(file_path, language)
    if tree is None:
        return symbols

    source = Path(file_path).read_bytes()
    root = tree.root_node

    extractor = _get_extractor(language)
    if extractor:
        extractor(root, source, symbols)
    else:
        logger.debug("No extractor for language '%s'", language)

    logger.debug(
        "%s — %d funcs, %d classes, %d imports",
        file_path,
        len(symbols.functions),
        len(symbols.classes),
        len(symbols.imports),
    )
    return symbols


# ---------------------------------------------------------------------------
# Language-specific extractors
# ---------------------------------------------------------------------------

def _get_extractor(language: str):
    """Return the extraction function for a given language."""
    return {
        "python": _extract_python,
        "javascript": _extract_javascript,
        "typescript": _extract_javascript,  # same grammar structure
        "go": _extract_go,
        "java": _extract_java,
        "rust": _extract_rust,
    }.get(language)


def _node_text(node: Node, source: bytes) -> str:
    """Extract raw text from a tree-sitter node."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _find_children_by_type(node: Node, *types: str) -> list[Node]:
    """Return all direct children matching any of the given node types."""
    return [c for c in node.children if c.type in types]


def _walk_calls(node: Node, source: bytes) -> list[str]:
    """Recursively collect all call expression names within a node."""
    calls: list[str] = []
    _collect_calls(node, source, calls)
    return list(dict.fromkeys(calls))  # deduplicate preserving order


def _collect_calls(node: Node, source: bytes, acc: list[str]) -> None:
    if node.type == "call" and node.children:
        func_node = node.children[0]
        name = _node_text(func_node, source).split("(")[0].strip()
        if name:
            acc.append(name)
    for child in node.children:
        _collect_calls(child, source, acc)


# ---- Python ---------------------------------------------------------------

def _extract_python(root: Node, source: bytes, symbols: FileSymbols) -> None:
    """Extract Python symbols from a tree-sitter AST."""
    for node in _iter_tree(root):
        if node.type == "import_statement":
            imp = _parse_python_import(node, source)
            if imp:
                symbols.imports.append(imp)

        elif node.type == "import_from_statement":
            imp = _parse_python_from_import(node, source)
            if imp:
                symbols.imports.append(imp)

        elif node.type in ("function_definition", "async_function_definition"):
            if node.parent and node.parent.type in ("block",):
                # Skip nested/method functions — handled by class extractor
                pass
            else:
                func = _parse_python_function(node, source)
                symbols.functions.append(func)

        elif node.type == "class_definition":
            cls = _parse_python_class(node, source)
            symbols.classes.append(cls)


def _iter_tree(node: Node):
    """Depth-first iteration over tree nodes."""
    yield node
    for child in node.children:
        yield from _iter_tree(child)


def _parse_python_function(node: Node, source: bytes, is_method: bool = False) -> FunctionSymbol:
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source) if name_node else "unknown"

    params: list[str] = []
    params_node = node.child_by_field_name("parameters")
    if params_node:
        for p in params_node.children:
            if p.type in ("identifier", "typed_parameter", "default_parameter",
                          "typed_default_parameter"):
                id_node = p if p.type == "identifier" else p.children[0] if p.children else None
                if id_node and id_node.type == "identifier":
                    param_name = _node_text(id_node, source)
                    if param_name not in ("self", "cls"):
                        params.append(param_name)

    body_node = node.child_by_field_name("body")
    calls = _walk_calls(body_node, source) if body_node else []

    docstring: str | None = None
    if body_node and body_node.children:
        first_stmt = body_node.children[0]
        if (first_stmt.type == "expression_statement" and
                first_stmt.children and first_stmt.children[0].type == "string"):
            docstring = _node_text(first_stmt.children[0], source).strip('"\' \n')

    return FunctionSymbol(
        name=name,
        params=params,
        calls=calls,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        docstring=docstring,
        is_async=node.type == "async_function_definition",
        is_method=is_method,
    )


def _parse_python_class(node: Node, source: bytes) -> ClassSymbol:
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source) if name_node else "unknown"

    bases: list[str] = []
    args_node = node.child_by_field_name("superclasses")
    if args_node:
        for child in args_node.children:
            if child.type == "identifier":
                bases.append(_node_text(child, source))

    methods: list[FunctionSymbol] = []
    body_node = node.child_by_field_name("body")
    if body_node:
        for child in body_node.children:
            if child.type in ("function_definition", "async_function_definition"):
                meth = _parse_python_function(child, source, is_method=True)
                methods.append(meth)

    return ClassSymbol(
        name=name,
        methods=methods,
        bases=bases,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
    )


def _parse_python_import(node: Node, source: bytes) -> ImportSymbol | None:
    names: list[str] = []
    for child in node.children:
        if child.type == "dotted_name":
            names.append(_node_text(child, source))
    if names:
        return ImportSymbol(module=names[0], names=names[1:])
    return None


def _parse_python_from_import(node: Node, source: bytes) -> ImportSymbol | None:
    module = ""
    names: list[str] = []
    for child in node.children:
        if child.type == "dotted_name" and not module:
            module = _node_text(child, source)
        elif child.type in ("import_statement", "wildcard_import"):
            pass
        elif child.type == "identifier":
            names.append(_node_text(child, source))
    return ImportSymbol(module=module, names=names) if module else None


# ---- JavaScript / TypeScript ----------------------------------------------

def _extract_javascript(root: Node, source: bytes, symbols: FileSymbols) -> None:
    """Extract JavaScript/TypeScript symbols from AST."""
    for node in _iter_tree(root):
        if node.type in ("function_declaration", "function_expression",
                          "arrow_function", "generator_function_declaration"):
            name = _get_js_function_name(node, source)
            if name:
                func = FunctionSymbol(
                    name=name,
                    params=_get_js_params(node, source),
                    calls=_walk_calls(node, source),
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                )
                symbols.functions.append(func)

        elif node.type == "class_declaration":
            cls_name_node = node.child_by_field_name("name")
            cls_name = _node_text(cls_name_node, source) if cls_name_node else "unknown"
            cls = ClassSymbol(
                name=cls_name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            )
            symbols.classes.append(cls)

        elif node.type == "import_statement":
            symbols.imports.append(_get_js_import(node, source))


def _get_js_function_name(node: Node, source: bytes) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node:
        return _node_text(name_node, source)
    # Arrow function assigned to variable
    if node.parent and node.parent.type == "variable_declarator":
        id_node = node.parent.child_by_field_name("name")
        if id_node:
            return _node_text(id_node, source)
    return None


def _get_js_params(node: Node, source: bytes) -> list[str]:
    params: list[str] = []
    params_node = node.child_by_field_name("parameters")
    if params_node:
        for p in params_node.children:
            if p.type == "identifier":
                params.append(_node_text(p, source))
    return params


def _get_js_import(node: Node, source: bytes) -> ImportSymbol:
    source_node = node.child_by_field_name("source")
    module = _node_text(source_node, source).strip("'\"") if source_node else ""
    return ImportSymbol(module=module)


# ---- Go -------------------------------------------------------------------

def _extract_go(root: Node, source: bytes, symbols: FileSymbols) -> None:
    """Extract Go symbols from AST."""
    for node in _iter_tree(root):
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source) if name_node else "unknown"
            body = node.child_by_field_name("body")
            func = FunctionSymbol(
                name=name,
                calls=_walk_calls(body, source) if body else [],
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            )
            symbols.functions.append(func)

        elif node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source) if name_node else "unknown"
            symbols.functions.append(
                FunctionSymbol(name=name, is_method=True,
                               start_line=node.start_point[0] + 1,
                               end_line=node.end_point[0] + 1)
            )

        elif node.type == "import_spec":
            path_node = node.child_by_field_name("path")
            if path_node:
                module = _node_text(path_node, source).strip('"')
                symbols.imports.append(ImportSymbol(module=module))


# ---- Java -----------------------------------------------------------------

def _extract_java(root: Node, source: bytes, symbols: FileSymbols) -> None:
    """Extract Java symbols from AST."""
    for node in _iter_tree(root):
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source) if name_node else "unknown"
            cls = ClassSymbol(
                name=name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            )
            symbols.classes.append(cls)

        elif node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source) if name_node else "unknown"
            body = node.child_by_field_name("body")
            func = FunctionSymbol(
                name=name,
                calls=_walk_calls(body, source) if body else [],
                is_method=True,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            )
            symbols.functions.append(func)

        elif node.type == "import_declaration":
            for child in node.children:
                if child.type in ("scoped_identifier", "identifier"):
                    symbols.imports.append(ImportSymbol(module=_node_text(child, source)))
                    break


# ---- Rust -----------------------------------------------------------------

def _extract_rust(root: Node, source: bytes, symbols: FileSymbols) -> None:
    """Extract Rust symbols from AST."""
    for node in _iter_tree(root):
        if node.type == "function_item":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source) if name_node else "unknown"
            body = node.child_by_field_name("body")
            func = FunctionSymbol(
                name=name,
                calls=_walk_calls(body, source) if body else [],
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            )
            symbols.functions.append(func)

        elif node.type == "struct_item":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, source) if name_node else "unknown"
            symbols.classes.append(
                ClassSymbol(name=name,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1)
            )

        elif node.type == "use_declaration":
            for child in node.children:
                if child.type in ("scoped_identifier", "identifier", "use_tree"):
                    symbols.imports.append(ImportSymbol(module=_node_text(child, source)))
                    break
