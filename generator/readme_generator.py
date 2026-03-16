"""
README generator module for AI Doc Generator.

Uses Gemini's LLM to synthesize a professional README.md from
extracted project metadata, symbols, and dependency information.
"""

from __future__ import annotations

from pathlib import Path

from google import genai

from clients import get_gemini_client, gemini_retry
from config import settings
from logger import setup_logger
from parser.symbol_extractor import FileSymbols
from analyzer.dependency_graph import GraphSummary
from core.language_detector import group_by_language

logger = setup_logger("readme_generator")


def generate_readme(
    project_name: str,
    project_root: str | Path,
    detected_files: list[dict],
    symbols_list: list[FileSymbols],
    graph_summary: GraphSummary,
    entry_points: list[str] | None = None,
) -> str:
    """
    Generate a comprehensive README.md using an LLM.

    Args:
        project_name: Name of the project.
        project_root: Root directory path of the project.
        detected_files: Output of language detection (list of file+language dicts).
        symbols_list: Extracted symbols from the codebase.
        graph_summary: Summary stats from the dependency graph.
        entry_points: Optional list of detected CLI/API entry point names.

    Returns:
        Markdown-formatted README content as a string.

    Example:
        >>> readme = generate_readme("my-app", "/path/to/repo", ...)
        >>> print(readme[:100])
        # my-app
        > AI-generated README ...
    """
    prompt = _build_readme_prompt(
        project_name=project_name,
        project_root=project_root,
        detected_files=detected_files,
        symbols_list=symbols_list,
        graph_summary=graph_summary,
        entry_points=entry_points or [],
    )

    logger.info("Generating README.md via LLM for project: %s", project_name)

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
                                "You are a senior software engineer and technical writer. "
                                "Generate production-quality documentation in clean GitHub-flavored Markdown. "
                                "Be precise, informative, and concise. "
                                "Do not use filler phrases like 'certainly' or 'of course'.\n\n"
                                f"{prompt}"
                            )
                        }
                    ],
                }
            ],
            config=genai.types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=3000,
            ),
        )
        return response.text or ""

    readme = _call_llm()
    logger.info("README generation complete (%d chars)", len(readme))
    return readme


def _build_readme_prompt(
    project_name: str,
    project_root: str | Path,
    detected_files: list[dict],
    symbols_list: list[FileSymbols],
    graph_summary: GraphSummary,
    entry_points: list[str],
) -> str:
    """Construct the README generation prompt from project metadata."""
    lang_groups = group_by_language(detected_files)
    primary_langs = sorted(lang_groups.items(), key=lambda x: len(x[1]), reverse=True)[:5]

    # Collect top-level functions and classes for context
    top_funcs: list[str] = []
    top_classes: list[str] = []
    for sym in symbols_list[:30]:
        top_funcs.extend(f.name for f in sym.functions[:3])
        top_classes.extend(c.name for c in sym.classes[:3])

    # Build directory structure (top 2 levels only)
    dir_tree = _get_dir_tree(Path(project_root), max_depth=2)

    lang_summary = ", ".join(f"{lang} ({len(files)} files)"
                             for lang, files in primary_langs if lang != "unknown")

    return f"""Generate a comprehensive, production-quality README.md for the following project.

## Project Metadata
- **Project Name**: {project_name}
- **Root Path**: {project_root}
- **Languages**: {lang_summary}
- **Total Source Files**: {len(detected_files)}
- **Modules**: {graph_summary.node_count} nodes, {graph_summary.edge_count} relationships
- **Has Circular Dependencies**: {graph_summary.has_cycles}
- **Key Modules**: {", ".join(graph_summary.top_hubs[:8]) or "N/A"}

## Key Functions Detected
{chr(10).join(f"- {f}" for f in list(dict.fromkeys(top_funcs))[:20]) or "None detected"}

## Key Classes Detected
{chr(10).join(f"- {c}" for c in list(dict.fromkeys(top_classes))[:15]) or "None detected"}

## Entry Points
{chr(10).join(f"- {e}" for e in entry_points[:5]) or "Not detected"}

## Directory Structure (top 2 levels)
```
{dir_tree}
```

## Required README Sections
Generate all of the following:

1. **Project Overview** — What this project does, its purpose and value.
2. **Tech Stack** — Key technologies, frameworks, and languages used.
3. **Prerequisites** — System requirements and dependencies.
4. **Installation** — Step-by-step instructions to set up the project.
5. **Usage** — How to run the project, including CLI commands and API endpoints if applicable.
6. **Project Structure** — Annotated directory tree.
7. **API Reference** — Summary of main API endpoints or public functions.
8. **Contributing** — How to contribute (branch naming, PR process, tests).
9. **License** — MIT License placeholder.

Use GitHub-flavored Markdown. Include code blocks for commands. Be specific and technical.
"""


def _get_dir_tree(root: Path, max_depth: int = 2, prefix: str = "") -> str:
    """Generate a simple directory tree string."""
    lines: list[str] = []
    IGNORE = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}

    def _walk(path: Path, depth: int, pfx: str) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name))
        except PermissionError:
            return
        for i, entry in enumerate(entries):
            if entry.name.startswith(".") or entry.name in IGNORE:
                continue
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(pfx + connector + entry.name + ("/" if entry.is_dir() else ""))
            if entry.is_dir():
                extension = "    " if i == len(entries) - 1 else "│   "
                _walk(entry, depth + 1, pfx + extension)

    lines.append(str(root.name) + "/")
    _walk(root, 1, prefix)
    return "\n".join(lines[:60])  # cap output length

