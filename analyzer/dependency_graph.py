"""
Dependency graph module for AI Doc Generator.

Builds a directed dependency graph from extracted symbol data using NetworkX.
Nodes represent modules, classes, and functions. Edges represent import
relationships and function calls between modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx

from logger import setup_logger
from parser.symbol_extractor import FileSymbols

logger = setup_logger("dependency_graph")


@dataclass
class GraphSummary:
    """Summary statistics for a dependency graph."""
    node_count: int
    edge_count: int
    top_hubs: list[str]      # nodes with highest in-degree
    isolated_nodes: list[str]
    has_cycles: bool
    strongly_connected_components: int


def build_dependency_graph(symbols_list: list[FileSymbols]) -> nx.DiGraph:
    """
    Build a directed dependency graph from a list of file symbols.

    Nodes
    -----
    - ``module::<file>`` — one node per source file
    - ``class::<file>::<classname>`` — one node per class
    - ``func::<file>::<funcname>`` — one node per top-level function

    Edges
    -----
    - ``module::A → module::B`` for import relationships
    - ``func::A::f → func::B::g`` for cross-module function calls

    Args:
        symbols_list: List of :class:`FileSymbols` from the symbol extractor.

    Returns:
        A ``networkx.DiGraph`` with typed nodes and weighted edges.

    Example:
        >>> graph = build_dependency_graph(symbols_list)
        >>> print(graph.number_of_nodes())
        42
    """
    graph = nx.DiGraph()
    # Map: module_stem → full module node id
    stem_to_node: dict[str, str] = {}

    # ---- Pass 1: add nodes ------------------------------------------------
    for file_syms in symbols_list:
        file_path = file_syms.file
        stem = Path(file_path).stem
        mod_node = f"module::{file_path}"
        stem_to_node[stem] = mod_node

        graph.add_node(
            mod_node,
            node_type="module",
            file=file_path,
            label=stem,
        )

        for cls in file_syms.classes:
            cls_node = f"class::{file_path}::{cls.name}"
            graph.add_node(
                cls_node,
                node_type="class",
                file=file_path,
                label=cls.name,
                start_line=cls.start_line,
                end_line=cls.end_line,
            )
            # Module → Class containment edge
            graph.add_edge(mod_node, cls_node, edge_type="contains")

        for func in file_syms.functions:
            func_node = f"func::{file_path}::{func.name}"
            graph.add_node(
                func_node,
                node_type="function",
                file=file_path,
                label=func.name,
                start_line=func.start_line,
                end_line=func.end_line,
            )
            graph.add_edge(mod_node, func_node, edge_type="contains")

    # ---- Pass 2: add import edges -----------------------------------------
    for file_syms in symbols_list:
        src_mod = f"module::{file_syms.file}"
        for imp in file_syms.imports:
            # Resolve import to a known module node
            target_stem = imp.module.split(".")[-1].split("/")[-1]
            if target_stem in stem_to_node:
                dst_mod = stem_to_node[target_stem]
                if not graph.has_edge(src_mod, dst_mod):
                    graph.add_edge(src_mod, dst_mod, edge_type="imports")

    # ---- Pass 3: add call edges -------------------------------------------
    # Build a map: function_name → node_id
    func_name_to_node: dict[str, list[str]] = {}
    for node_id, attrs in graph.nodes(data=True):
        if attrs.get("node_type") == "function":
            label = attrs.get("label", "")
            func_name_to_node.setdefault(label, []).append(node_id)

    for file_syms in symbols_list:
        for func in file_syms.functions:
            caller_node = f"func::{file_syms.file}::{func.name}"
            for call in func.calls:
                callee_candidates = func_name_to_node.get(call, [])
                for callee_node in callee_candidates:
                    if callee_node != caller_node:
                        if not graph.has_edge(caller_node, callee_node):
                            graph.add_edge(caller_node, callee_node, edge_type="calls")

    logger.info(
        "Dependency graph: %d nodes, %d edges",
        graph.number_of_nodes(),
        graph.number_of_edges(),
    )
    return graph


def get_graph_summary(graph: nx.DiGraph) -> GraphSummary:
    """
    Compute summary statistics for a dependency graph.

    Args:
        graph: Directed dependency graph from :func:`build_dependency_graph`.

    Returns:
        A :class:`GraphSummary` with key statistics.

    Example:
        >>> summary = get_graph_summary(graph)
        >>> print(summary.node_count)
        42
    """
    in_degrees = sorted(graph.in_degree(), key=lambda x: x[1], reverse=True)
    top_hubs = [
        graph.nodes[n].get("label", n)
        for n, _ in in_degrees[:10]
        if graph.nodes[n].get("node_type") == "module"
    ]

    isolated = [n for n in graph.nodes if graph.degree(n) == 0]
    has_cycles = not nx.is_directed_acyclic_graph(graph)
    scc_count = nx.number_strongly_connected_components(graph)

    return GraphSummary(
        node_count=graph.number_of_nodes(),
        edge_count=graph.number_of_edges(),
        top_hubs=top_hubs[:5],
        isolated_nodes=[graph.nodes[n].get("label", n) for n in isolated[:10]],
        has_cycles=has_cycles,
        strongly_connected_components=scc_count,
    )


def get_module_imports(graph: nx.DiGraph, module_file: str) -> list[str]:
    """
    Get the list of modules imported by a given module.

    Args:
        graph: Dependency graph.
        module_file: File path of the module.

    Returns:
        List of imported module file paths.
    """
    mod_node = f"module::{module_file}"
    if mod_node not in graph:
        return []
    return [
        graph.nodes[dst].get("file", dst)
        for _, dst, attrs in graph.out_edges(mod_node, data=True)
        if attrs.get("edge_type") == "imports"
    ]
