"""Tests for the CLI generate command (dry-run mode, no LLM calls)."""

from pathlib import Path
import pytest
from click.testing import CliRunner
from cli.generate_docs import cli


class TestCLIGenerateCommand:
    def test_help_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "generate" in result.output

    def test_generate_dry_run_local_path(self, temp_project_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["generate", str(temp_project_dir), "--dry-run",
             "--output-dir", str(temp_project_dir / "docs")],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        docs_dir = temp_project_dir / "docs"
        assert (docs_dir / "README.md").exists()
        assert (docs_dir / "architecture.md").exists()
        assert (docs_dir / "api_docs.md").exists()
        assert (docs_dir / "project_structure.md").exists()

    def test_dry_run_readme_contains_project_name(self, temp_project_dir: Path) -> None:
        runner = CliRunner()
        out_dir = temp_project_dir / "docs2"
        runner.invoke(
            cli,
            ["generate", str(temp_project_dir), "--dry-run",
             "--output-dir", str(out_dir)],
        )
        readme = (out_dir / "README.md").read_text()
        assert temp_project_dir.name in readme

    def test_generate_with_skip_embeddings(self, temp_project_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["generate", str(temp_project_dir), "--dry-run",
             "--skip-embeddings",
             "--output-dir", str(temp_project_dir / "docs3")],
        )
        assert result.exit_code == 0

    def test_invalid_path_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "/nonexistent/path/to/repo"])
        assert result.exit_code != 0
