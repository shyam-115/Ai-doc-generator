"""
API documentation generator for AI Doc Generator.

Detects API endpoints across FastAPI, Flask, Express, and Django frameworks
using AST analysis combined with regex patterns, then generates api_docs.md
via LLM with full endpoint descriptions, parameters, and response schemas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google import genai

from clients import get_gemini_client, gemini_retry
from config import settings
from logger import setup_logger
from parser.symbol_extractor import FileSymbols

logger = setup_logger("api_doc_generator")


@dataclass
class APIEndpoint:
    """Represents a detected API endpoint."""
    method: str         # GET, POST, PUT, DELETE, PATCH
    path: str           # URL path pattern
    function_name: str  # Handler function name
    file: str           # Source file
    framework: str      # fastapi, flask, express, django
    params: list[str] = field(default_factory=list)
    description: str | None = None
    line: int = 0


# ---- Regex patterns per framework -----------------------------------------

_PATTERNS: dict[str, list[re.Pattern]] = {
    "fastapi": [
        re.compile(
            r'@(?:app|router)\.(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
    ],
    "flask": [
        re.compile(
            r'@(?:app|blueprint|bp)\s*\.route\s*\(\s*["\']([^"\']+)["\'].*?methods\s*=\s*\[([^\]]+)\]',
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r'@(?:app|blueprint|bp)\s*\.(?:get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
    ],
    "express": [
        re.compile(
            r'(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
    ],
    "django": [
        re.compile(
            r'path\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
    ],
}


def detect_endpoints(
    files: list[str | Path],
    symbols_list: list[FileSymbols],
) -> list[APIEndpoint]:
    """
    Detect API endpoints from source files using regex pattern matching.

    Supports FastAPI, Flask, Express, and Django route patterns.

    Args:
        files: List of source file paths to scan.
        symbols_list: Extracted symbol data (used to get function names).

    Returns:
        List of detected :class:`APIEndpoint` objects.

    Example:
        >>> endpoints = detect_endpoints(files, symbols_list)
        >>> print(endpoints[0].method, endpoints[0].path)
        GET /users/{user_id}
    """
    endpoints: list[APIEndpoint] = []

    # Build function-name lookup from symbols
    func_by_file: dict[str, list[str]] = {}
    for sym in symbols_list:
        func_by_file[str(sym.file)] = [f.name for f in sym.functions]

    for file_path in files:
        path = Path(file_path)
        if path.suffix not in (".py", ".js", ".ts"):
            continue

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for framework, patterns in _PATTERNS.items():
            for pattern in patterns:
                for match in pattern.finditer(source):
                    ep = _parse_match(match, framework, str(file_path), source)
                    if ep:
                        endpoints.append(ep)

    # Deduplicate by (method, path)
    seen: set[tuple[str, str]] = set()
    unique: list[APIEndpoint] = []
    for ep in endpoints:
        key = (ep.method.upper(), ep.path)
        if key not in seen:
            seen.add(key)
            unique.append(ep)

    logger.info("Detected %d API endpoints across %d files", len(unique), len(files))
    return unique


def generate_api_docs(
    project_name: str,
    endpoints: list[APIEndpoint],
    symbols_list: list[FileSymbols],
) -> str:
    """
    Generate api_docs.md using an LLM with detected endpoint metadata.

    Args:
        project_name: Project name.
        endpoints: Detected API endpoints.
        symbols_list: Extracted symbols for additional context.

    Returns:
        Markdown content for api_docs.md.

    Example:
        >>> docs = generate_api_docs("my-api", endpoints, symbols)
        >>> print("## Endpoints" in docs)
        True
    """
    prompt = _build_api_prompt(project_name, endpoints, symbols_list)

    logger.info("Generating api_docs.md for %s (%d endpoints)", project_name, len(endpoints))

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
                                "You are a senior API documentation specialist. "
                                "Generate clear, accurate REST API documentation in GitHub-flavored Markdown. "
                                "Follow OpenAPI-style documentation conventions but in Markdown format.\n\n"
                                f"{prompt}"
                            )
                        }
                    ],
                }
            ],
            config=genai.types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=3000,
            ),
        )
        return response.text or ""

    content = _call_llm()
    logger.info("API docs generation complete (%d chars)", len(content))
    return content


def _parse_match(
    match: re.Match,
    framework: str,
    file_path: str,
    source: str,
) -> APIEndpoint | None:
    """Parse a regex match into an APIEndpoint."""
    groups = match.groups()
    line_num = source[: match.start()].count("\n") + 1

    if framework == "fastapi":
        method, path = groups[0].upper(), groups[1]
    elif framework == "express":
        method, path = groups[0].upper(), groups[1]
    elif framework == "flask":
        if len(groups) >= 2 and groups[1]:
            # route() with methods=
            path = groups[0]
            raw_methods = groups[1].replace('"', "").replace("'", "")
            method = raw_methods.split(",")[0].strip().upper()
        else:
            path = groups[0]
            method = "GET"
    elif framework == "django":
        path = groups[0]
        method = "GET"
    else:
        return None

    # Try to find the next function name after the decorator
    func_name = _find_next_function(source, match.end())

    return APIEndpoint(
        method=method,
        path=path,
        function_name=func_name or "unknown",
        file=file_path,
        framework=framework,
        line=line_num,
    )


def _find_next_function(source: str, start: int) -> str | None:
    """Find the name of the next function defined after position start."""
    snippet = source[start : start + 300]
    m = re.search(r"(?:async def|def|function)\s+([a-zA-Z_][a-zA-Z0-9_]*)", snippet)
    return m.group(1) if m else None


def _build_api_prompt(
    project_name: str,
    endpoints: list[APIEndpoint],
    symbols_list: list[FileSymbols],
) -> str:
    """Build the API documentation generation prompt."""
    if not endpoints:
        endpoint_section = "No API endpoints were auto-detected. Generate a placeholder documentation structure."
    else:
        ep_lines: list[str] = []
        for ep in endpoints[:50]:
            ep_lines.append(
                f"- [{ep.method}] `{ep.path}` — handler: `{ep.function_name}` "
                f"(file: {Path(ep.file).name}, framework: {ep.framework}, line: {ep.line})"
            )
        endpoint_section = "\n".join(ep_lines)

    frameworks_found = list({ep.framework for ep in endpoints})

    return f"""Generate comprehensive API documentation (api_docs.md) for "{project_name}".

## Detected Frameworks
{", ".join(frameworks_found) if frameworks_found else "None detected"}

## Detected Endpoints
{endpoint_section}

## Documentation Requirements

Generate api_docs.md with the following sections:

1. **Overview** — Purpose of the API, base URL, authentication method.
2. **Authentication** — Auth mechanism (Bearer token, API key, session, etc.).
3. **Endpoints** — For each endpoint include:
   - Method badge and path (e.g., `GET /users/{id}`)
   - Description of what it does
   - Request parameters (path, query, body)
   - Request body schema (JSON, if applicable)
   - Response schema with example
   - Error codes
4. **Error Codes** — Common error codes and their meanings.
5. **Rate Limiting** — Note rate limiting policy if applicable.
6. **Examples** — cURL and Python `requests` examples for key endpoints.

Use proper markdown with code blocks, tables for parameters, and clear structure.
"""

