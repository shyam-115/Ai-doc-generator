"""Tests for analyzer/dependency_graph.py"""

from pathlib import Path
import pytest
import networkx as nx

from parser.symbol_extractor import extract_symbols
from analyzer.dependency_graph import (
    build_dependency_graph,
    get_graph_summary,
    get_module_imports,
)


@pytest.fixture
def two_file_symbols(tmp_path: Path):
    """Two Python files: one imports the other."""
    auth_file = tmp_path / "auth.py"
    auth_file.write_text(
        "from utils import helper\n\n"
        "class AuthService:\n"
        "    def login(self, u, p):\n"
        "        return helper(u)\n"
    )
    utils_file = tmp_path / "utils.py"
    utils_file.write_text("def helper(x):\n    return x\n")

    sym_auth = extract_symbols(auth_file, "python")
    sym_utils = extract_symbols(utils_file, "python")
    return [sym_auth, sym_utils]


class TestBuildDependencyGraph:
    def test_returns_digraph(self, two_file_symbols) -> None:
        g = build_dependency_graph(two_file_symbols)
        assert isinstance(g, nx.DiGraph)

    def test_has_module_nodes(self, two_file_symbols) -> None:
        g = build_dependency_graph(two_file_symbols)
        module_nodes = [n for n, d in g.nodes(data=True) if d.get("node_type") == "module"]
        assert len(module_nodes) == 2

    def test_has_function_nodes(self, two_file_symbols) -> None:
        g = build_dependency_graph(two_file_symbols)
        func_nodes = [n for n, d in g.nodes(data=True) if d.get("node_type") == "function"]
        assert len(func_nodes) >= 1

    def test_has_import_edge(self, two_file_symbols) -> None:
        g = build_dependency_graph(two_file_symbols)
        import_edges = [
            (u, v) for u, v, d in g.edges(data=True) if d.get("edge_type") == "imports"
        ]
        assert len(import_edges) >= 1

    def test_empty_symbols_returns_empty_graph(self) -> None:
        g = build_dependency_graph([])
        assert g.number_of_nodes() == 0

    def test_single_file(self, temp_python_file: Path) -> None:
        sym = extract_symbols(temp_python_file, "python")
        g = build_dependency_graph([sym])
        assert g.number_of_nodes() > 0


class TestGetGraphSummary:
    def test_summary_fields(self, two_file_symbols) -> None:
        g = build_dependency_graph(two_file_symbols)
        summary = get_graph_summary(g)
        assert summary.node_count == g.number_of_nodes()
        assert summary.edge_count == g.number_of_edges()
        assert isinstance(summary.has_cycles, bool)
        assert isinstance(summary.top_hubs, list)
