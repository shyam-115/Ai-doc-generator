"""Tests for core/repo_loader.py"""

from pathlib import Path
import pytest

from core.repo_loader import (
    get_project_files,
    load_local_repo,
    is_github_url,
    IGNORED_DIRS,
)


class TestLoadLocalRepo:
    def test_loads_existing_directory(self, temp_project_dir: Path) -> None:
        result = load_local_repo(temp_project_dir)
        assert result == temp_project_dir.resolve()

    def test_raises_for_missing_path(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_local_repo(tmp_path / "no_such_dir")

    def test_raises_for_file_path(self, tmp_path: Path) -> None:
        f = tmp_path / "somefile.txt"
        f.write_text("hi")
        with pytest.raises(NotADirectoryError):
            load_local_repo(f)


class TestGetProjectFiles:
    def test_returns_source_files(self, temp_project_dir: Path) -> None:
        files = get_project_files(temp_project_dir)
        names = [f.name for f in files]
        assert "main.py" in names
        assert "utils.py" in names
        assert "test_main.py" in names

    def test_ignores_node_modules(self, temp_project_dir: Path) -> None:
        files = get_project_files(temp_project_dir)
        for f in files:
            assert "node_modules" not in f.parts, f"Should not include node_modules: {f}"

    def test_ignores_pycache(self, temp_project_dir: Path) -> None:
        files = get_project_files(temp_project_dir)
        for f in files:
            assert "__pycache__" not in f.parts, f"Should not include __pycache__: {f}"

    def test_returns_sorted_list(self, temp_project_dir: Path) -> None:
        files = get_project_files(temp_project_dir)
        assert files == sorted(files)

    def test_ignores_all_declared_dirs(self, tmp_path: Path) -> None:
        for d in list(IGNORED_DIRS)[:3]:
            (tmp_path / d).mkdir()
            (tmp_path / d / "file.py").write_text("x = 1")
        (tmp_path / "valid.py").write_text("x = 1")
        files = get_project_files(tmp_path)
        assert all(f.name == "valid.py" for f in files)

    def test_empty_dir_returns_empty_list(self, tmp_path: Path) -> None:
        files = get_project_files(tmp_path)
        assert files == []


class TestIsGithubUrl:
    def test_https_url(self) -> None:
        assert is_github_url("https://github.com/user/repo") is True

    def test_git_ssh_url(self) -> None:
        assert is_github_url("git@github.com:user/repo.git") is True

    def test_local_path(self) -> None:
        assert is_github_url("/home/user/project") is False

    def test_relative_path(self) -> None:
        assert is_github_url("./my-project") is False
