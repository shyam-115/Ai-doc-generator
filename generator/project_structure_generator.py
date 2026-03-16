"""
Project structure documentation generator for AI Doc Generator.

Generates a project_structure.md with an annotated directory tree
and per-file descriptions derived from extracted symbols.
"""

from __future__ import annotations

from pathlib import Path

from google import genai

from clients import get_gemini_client, gemini_retry
from config import settings
from logger import setup_logger
from parser.symbol_extractor import FileSymbols
from core.language_detector import detect_language

logger = setup_logger("project_structure_generator")


def generate_project_structure(
    project_name: str,
    project_root: str | Path,
    files: list[str | Path],
    symbols_list: list[FileSymbols],
) -> str:
    """
    Generate a project_structure.md with an annotated file tree.

    Args:
        project_name: Name of the project.
        project_root: Root directory of the project.
        files: All source file paths.
        symbols_list: Extracted symbols for per-file context.

    Returns:
        Markdown content for project_structure.md.

    Example:
        >>> md = generate_project_structure("my-app", "/path/to/repo", files, symbols)
        >>> print("## Directory Structure" in md)
        True
    """
    root = Path(project_root)
    tree = _build_annotated_tree(root, files, symbols_list, max_depth=3)
    file_inventory = _build_file_inventory(files, symbols_list)
    prompt = _build_prompt(project_name, root, tree, file_inventory)

    logger.info("Generating project_structure.md for project: %s", project_name)

    @gemini_retry
    def _call_llm() -> str:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "You are a senior software engineer writing developer documentation. "
                                "Generate a precise, helpful project structure guide in Markdown.\n\n"
                                f"{prompt}"
                            )
                        }
                    ],
                }
            ],
            config=genai.types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=2500,
            ),
        )
        return response.text or ""

    content = _call_llm()
    logger.info("Project structure generation complete (%d chars)", len(content))
    return content


def _build_annotated_tree(
    root: Path,
    files: list[str | Path],
    symbols_list: list[FileSymbols],
    max_depth: int = 3,
) -> str:
    """Build a directory tree with inline annotations."""
    IGNORE = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build",
              ".mypy_cache", ".pytest_cache", ".idea", ".vscode"}

    # Map file path → quick summary
    sym_map: dict[str, str] = {}
    for sym in symbols_list:
        parts = []
        if sym.classes:
            parts.append(f"{len(sym.classes)} class(es)")
        if sym.functions:
            parts.append(f"{len(sym.functions)} function(s)")
        if parts:
            sym_map[str(sym.file)] = ", ".join(parts)

    lines: list[str] = [f"{root.name}/"]

    def _walk(path: Path, depth: int, pfx: str) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name))
        except PermissionError:
            return
        filtered = [e for e in entries if e.name not in IGNORE and not e.name.startswith(".")]
        for i, entry in enumerate(filtered):
            connector = "└── " if i == len(filtered) - 1 else "├── "
            ext_pfx = "    " if i == len(filtered) - 1 else "│   "
            annotation = ""
            if entry.is_file():
                sym_note = sym_map.get(str(entry), "")
                if sym_note:
                    annotation = f"  # {sym_note}"
            lines.append(pfx + connector + entry.name + ("/" if entry.is_dir() else "") + annotation)
            if entry.is_dir():
                _walk(entry, depth + 1, pfx + ext_pfx)

    _walk(root, 1, "")
    return "\n".join(lines[:80])


def _build_file_inventory(
    files: list[str | Path],
    symbols_list: list[FileSymbols],
) -> str:
    """Build a compact per-file inventory string."""
    sym_map = {sym.file: sym for sym in symbols_list}
    lines: list[str] = []

    for file_path in sorted(str(f) for f in files)[:60]:
        sym = sym_map.get(file_path)
        lang = detect_language(file_path).get("language", "unknown")
        if sym and (sym.functions or sym.classes):
            func_names = [f.name for f in sym.functions[:3]]
            class_names = [c.name for c in sym.classes[:3]]
            desc_parts = []
            if class_names:
                desc_parts.append(f"classes: {', '.join(class_names)}")
            if func_names:
                desc_parts.append(f"funcs: {', '.join(func_names)}")
            desc = "; ".join(desc_parts)
        else:
            desc = lang or "data/config"
        rel_path = file_path.replace(str(files[0]).split("/")[0], "").lstrip("/") if files else file_path
        lines.append(f"- `{Path(file_path).name}` ({lang}): {desc}")

    return "\n".join(lines)


def _build_prompt(
    project_name: str,
    root: Path,
    tree: str,
    file_inventory: str,
) -> str:
    return f"""Generate a project_structure.md for "{project_name}".

## Directory Tree
```
{tree}
```

## File Inventory
{file_inventory}

## Required Sections

1. **Overview** — Purpose of the directory structure and organization strategy.
2. **Directory Structure** — Embed the annotated tree above using a code block.
3. **Module Descriptions** — For each top-level directory/module, explain:
   - Its responsibility
   - Key files within it
   - How it interacts with other modules
4. **Key Files** — Table with filename | purpose | key exports/functions.
5. **Configuration Files** — List and explain config files (pyproject.toml, .env, etc.).
6. **Adding New Features** — Where to put new code based on the project organization.

Use clean GitHub-flavored Markdown. Be specific and developer-friendly.
"""

