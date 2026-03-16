"""
Architecture documentation generator for AI Doc Generator.

Generates architecture.md with system overview, module relationships,
and Mermaid diagrams derived from the dependency and call graphs.
"""

from __future__ import annotations

from pathlib import Path

from google import genai

from clients import get_gemini_client, gemini_retry
from config import settings
from logger import setup_logger
from parser.symbol_extractor import FileSymbols
from analyzer.dependency_graph import GraphSummary, get_module_imports
from analyzer.call_graph import ExecutionFlow, get_flow_descriptions

import networkx as nx

logger = setup_logger("architecture_generator")


def generate_architecture(
    project_name: str,
    symbols_list: list[FileSymbols],
    dep_graph: nx.DiGraph,
    call_flows: list[ExecutionFlow],
    graph_summary: GraphSummary,
) -> str:
    """
    Generate a comprehensive architecture.md document.

    Args:
        project_name: Name of the project.
        symbols_list: Extracted symbols.
        dep_graph: Dependency graph from build_dependency_graph().
        call_flows: Execution flows from get_execution_flows().
        graph_summary: Graph summary statistics.

    Returns:
        Markdown string for architecture.md.

    Example:
        >>> arch = generate_architecture("my-app", symbols, dep_graph, flows, summary)
        >>> print("## Architecture" in arch)
        True
    """
    mermaid_dep = _build_dependency_mermaid(dep_graph, max_nodes=20)
    mermaid_flow = _build_flow_mermaid(call_flows)
    flow_descriptions = get_flow_descriptions(call_flows[:10])

    prompt = _build_arch_prompt(
        project_name=project_name,
        symbols_list=symbols_list,
        graph_summary=graph_summary,
        flow_descriptions=flow_descriptions,
        mermaid_dep=mermaid_dep,
        mermaid_flow=mermaid_flow,
    )

    logger.info("Generating architecture.md via LLM for project: %s", project_name)

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
                                "You are a senior software architect and technical writer. "
                                "Generate clear, accurate architecture documentation. "
                                "Use the provided Mermaid diagrams as-is. "
                                "Be precise and avoid filler text.\n\n"
                                f"{prompt}"
                            )
                        }
                    ],
                }
            ],
            config=genai.types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=3500,
            ),
        )
        return response.text or ""

    content = _call_llm()
    logger.info("Architecture generation complete (%d chars)", len(content))
    return content


def _build_arch_prompt(
    project_name: str,
    symbols_list: list[FileSymbols],
    graph_summary: GraphSummary,
    flow_descriptions: list[str],
    mermaid_dep: str,
    mermaid_flow: str,
) -> str:
    """Build the architecture generation prompt."""
    # Aggregate module summaries
    module_summaries: list[str] = []
    for sym in symbols_list[:40]:
        if sym.functions or sym.classes:
            file_name = Path(sym.file).name
            func_names = [f.name for f in sym.functions[:5]]
            class_names = [c.name for c in sym.classes[:5]]
            parts = []
            if func_names:
                parts.append(f"functions: {', '.join(func_names)}")
            if class_names:
                parts.append(f"classes: {', '.join(class_names)}")
            module_summaries.append(f"- **{file_name}**: {'; '.join(parts)}")

    return f"""Generate a comprehensive architecture.md for the project "{project_name}".

## Graph Statistics
- Total graph nodes: {graph_summary.node_count}
- Total relationships: {graph_summary.edge_count}
- Core modules (high connectivity): {", ".join(graph_summary.top_hubs[:8]) or "N/A"}
- Circular dependencies: {graph_summary.has_cycles}
- Strongly Connected Components: {graph_summary.strongly_connected_components}

## Module Inventory
{chr(10).join(module_summaries[:30]) or "No modules extracted."}

## Execution Flows Detected
{chr(10).join(f"- {f}" for f in flow_descriptions) or "No flows detected."}

## Dependency Graph (Mermaid — include this diagram as-is)
```mermaid
{mermaid_dep}
```

## Call Flow (Mermaid — include this diagram as-is)
```mermaid
{mermaid_flow}
```

## Required Sections in architecture.md

1. **System Overview** — High-level purpose, architecture style (monolith, microservices, layered, etc.)
2. **Architecture Diagram** — Include the Mermaid dependency graph above.
3. **Module Breakdown** — Description of each module and its responsibility.
4. **Data Flow** — How data moves through the system from input to output.
5. **Execution Flow** — Include the call flow Mermaid diagram and describe key paths.
6. **Design Patterns** — Patterns detected (e.g., repository, factory, observer, MVC).
7. **Scalability Considerations** — Bottlenecks, threading model, async patterns.
8. **Technology Decisions** — Rationale for key technical choices.

Generate production-quality, accurate markdown documentation.
"""


def _build_dependency_mermaid(graph: nx.DiGraph, max_nodes: int = 20) -> str:
    """Build a Mermaid graph diagram from the dependency graph."""
    lines = ["graph TD"]

    # Only show module-level nodes to keep the diagram readable
    module_nodes = [
        (n, d) for n, d in graph.nodes(data=True)
        if d.get("node_type") == "module"
    ][:max_nodes]

    node_ids: dict[str, str] = {}
    for i, (node, data) in enumerate(module_nodes):
        safe_id = f"M{i}"
        label = data.get("label", node)[:30]
        node_ids[node] = safe_id
        lines.append(f'    {safe_id}["{label}"]')

    # Add import edges between modules
    for src, dst, attrs in graph.edges(data=True):
        if (attrs.get("edge_type") == "imports"
                and src in node_ids
                and dst in node_ids):
            lines.append(f"    {node_ids[src]} --> {node_ids[dst]}")

    return "\n".join(lines)


def _build_flow_mermaid(flows: list[ExecutionFlow], max_flows: int = 5) -> str:
    """Build a Mermaid sequence or flowchart from the top execution flows."""
    if not flows:
        return "graph LR\n    A[No flows detected]"

    lines = ["graph LR"]
    seen_edges: set[tuple[str, str]] = set()

    for flow in flows[:max_flows]:
        path_labels = [node_id.split("::")[-1][:20] for node_id in flow.path]
        for a, b in zip(path_labels, path_labels[1:]):
            edge = (a, b)
            if edge not in seen_edges:
                # Sanitize labels for Mermaid
                a_safe = a.replace("-", "_").replace(".", "_")
                b_safe = b.replace("-", "_").replace(".", "_")
                lines.append(f'    {a_safe}["{a}"] --> {b_safe}["{b}"]')
                seen_edges.add(edge)

    return "\n".join(lines)

