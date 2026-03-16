"""
Call graph module for AI Doc Generator.

Builds and analyzes the function-level call graph extracted from parsed
symbols, enabling discovery of execution flows and entry points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx

from logger import setup_logger
from parser.symbol_extractor import FileSymbols

logger = setup_logger("call_graph")


@dataclass
class ExecutionFlow:
    """Represents a traced execution path through the codebase."""
    entry_point: str
    path: list[str]
    depth: int


def build_call_graph(symbols_list: list[FileSymbols]) -> nx.DiGraph:
    """
    Build a directed function call graph from symbol data.

    Each node is a function (format: ``<file>::<function_name>``).
    Each edge ``A → B`` means function A calls function B.

    Args:
        symbols_list: List of :class:`FileSymbols` from the symbol extractor.

    Returns:
        A directed call graph as a ``networkx.DiGraph``.

    Example:
        >>> cg = build_call_graph(symbols_list)
        >>> print(cg.number_of_nodes())
        18
    """
    graph = nx.DiGraph()

    # Collect all functions keyed by name for cross-file resolution
    func_index: dict[str, list[str]] = {}  # name → list of node_ids

    # ---- Add nodes --------------------------------------------------------
    for file_syms in symbols_list:
        file_stem = Path(file_syms.file).stem
        all_funcs = list(file_syms.functions)
        for cls in file_syms.classes:
            all_funcs.extend(cls.methods)

        for func in all_funcs:
            node_id = f"{file_syms.file}::{func.name}"
            graph.add_node(
                node_id,
                label=func.name,
                file=file_syms.file,
                module=file_stem,
                start_line=func.start_line,
                end_line=func.end_line,
                is_async=func.is_async,
                is_method=func.is_method,
            )
            func_index.setdefault(func.name, []).append(node_id)

    # ---- Add call edges ---------------------------------------------------
    for file_syms in symbols_list:
        all_funcs = list(file_syms.functions)
        for cls in file_syms.classes:
            all_funcs.extend(cls.methods)

        for func in all_funcs:
            caller_id = f"{file_syms.file}::{func.name}"
            for called_name in func.calls:
                if called_name not in func_index:
                    # External/stdlib call — add as external node
                    ext_id = f"external::{called_name}"
                    if ext_id not in graph:
                        graph.add_node(ext_id, label=called_name, file="external",
                                       module="external")
                    if not graph.has_edge(caller_id, ext_id):
                        graph.add_edge(caller_id, ext_id, edge_type="calls")
                else:
                    for callee_id in func_index[called_name]:
                        if callee_id != caller_id and not graph.has_edge(caller_id, callee_id):
                            graph.add_edge(caller_id, callee_id, edge_type="calls")

    logger.info(
        "Call graph: %d functions, %d call edges",
        graph.number_of_nodes(),
        graph.number_of_edges(),
    )
    return graph


def get_entry_points(graph: nx.DiGraph) -> list[str]:
    """
    Identify likely entry points (functions with no callers within the project).

    Args:
        graph: Call graph from :func:`build_call_graph`.

    Returns:
        List of node IDs for functions that are never called by other project functions.

    Example:
        >>> entries = get_entry_points(cg)
        >>> print(entries[0])
        api/main.py::create_app
    """
    return [
        n for n in graph.nodes
        if graph.in_degree(n) == 0
        and graph.nodes[n].get("file", "external") != "external"
        and graph.out_degree(n) > 0
    ]


def get_execution_flows(
    graph: nx.DiGraph,
    entry_points: list[str] | None = None,
    max_depth: int = 8,
    max_flows: int = 20,
) -> list[ExecutionFlow]:
    """
    Trace execution flows from entry points through the call graph.

    Uses DFS to find the deepest call chains starting from entry points.

    Args:
        graph: Call graph from :func:`build_call_graph`.
        entry_points: List of starting node IDs. Auto-detected if None.
        max_depth: Maximum depth to trace.
        max_flows: Maximum number of flows to return.

    Returns:
        List of :class:`ExecutionFlow` objects, sorted by depth descending.

    Example:
        >>> flows = get_execution_flows(cg)
        >>> print(flows[0].path)
        ['main.py::main', 'router.py::handle', 'service.py::process']
    """
    if entry_points is None:
        entry_points = get_entry_points(graph)

    flows: list[ExecutionFlow] = []
    visited_global: set[str] = set()

    def dfs(node: str, path: list[str], depth: int) -> None:
        if depth >= max_depth or node in visited_global:
            if len(path) > 1:
                flows.append(
                    ExecutionFlow(
                        entry_point=path[0],
                        path=list(path),
                        depth=len(path) - 1,
                    )
                )
            return

        successors = [
            s for s in graph.successors(node)
            if graph.nodes[s].get("file", "external") != "external"
        ]

        if not successors:
            if len(path) > 1:
                flows.append(
                    ExecutionFlow(entry_point=path[0], path=list(path), depth=len(path) - 1)
                )
            return

        visited_global.add(node)
        for succ in successors[:3]:  # limit branching factor
            dfs(succ, path + [succ], depth + 1)
        visited_global.discard(node)

    for entry in entry_points[:max_flows]:
        dfs(entry, [entry], 0)

    flows.sort(key=lambda f: f.depth, reverse=True)
    return flows[:max_flows]


def get_flow_descriptions(flows: list[ExecutionFlow]) -> list[str]:
    """
    Generate human-readable descriptions of execution flows.

    Args:
        flows: List of :class:`ExecutionFlow` objects.

    Returns:
        List of strings like "main → handle_request → validate → respond".
    """
    descriptions = []
    for flow in flows:
        parts = []
        for node_id in flow.path:
            # Extract just function name for readability
            label = node_id.split("::")[-1]
            parts.append(label)
        descriptions.append(" → ".join(parts))
    return descriptions
