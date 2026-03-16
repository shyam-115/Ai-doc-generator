"""
Repository ingestion module for AI Doc Generator.

Handles cloning remote GitHub repositories and loading local project folders,
then collecting all relevant source files while ignoring common non-source directories.
"""

import os
import shutil
from pathlib import Path

import git
from tqdm import tqdm

from logger import setup_logger

logger = setup_logger("repo_loader")

# Directories to skip during file collection
IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "dist",
        "build",
        "venv",
        ".venv",
        "env",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "target",       # Rust/Java build dir
        ".idea",
        ".vscode",
        "coverage",
        ".next",
        ".nuxt",
        "vendor",
    }
)

# File extensions considered as source code
SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".go", ".java", ".rs", ".c", ".cpp",
        ".h", ".hpp", ".cs", ".rb", ".php",
        ".swift", ".kt", ".scala", ".r",
        ".sh", ".bash", ".yaml", ".yml",
        ".json", ".toml", ".md", ".html",
        ".css", ".scss",
    }
)


def clone_repo(repo_url: str, destination_path: str | Path) -> Path:
    """
    Clone a remote Git repository to a local destination.

    Args:
        repo_url: HTTPS or SSH URL of the GitHub repository.
        destination_path: Local path where the repo will be cloned.

    Returns:
        Path to the cloned repository root.

    Raises:
        git.GitCommandError: If cloning fails (invalid URL, auth error, etc).
        ValueError: If destination_path already exists and is not empty.

    Example:
        >>> path = clone_repo("https://github.com/tiangolo/fastapi", "/tmp/fastapi")
        >>> print(path)
        /tmp/fastapi
    """
    dest = Path(destination_path)

    if dest.exists() and any(dest.iterdir()):
        logger.warning("Destination %s already exists. Removing before clone.", dest)
        shutil.rmtree(dest)

    dest.mkdir(parents=True, exist_ok=True)
    logger.info("Cloning %s → %s", repo_url, dest)

    git.Repo.clone_from(repo_url, dest, depth=1, progress=_GitProgressPrinter())

    logger.info("Clone complete: %s", dest)
    return dest


def load_local_repo(path: str | Path) -> Path:
    """
    Validate and return a Path object for a local repository.

    Args:
        path: Absolute or relative path to a local project folder.

    Returns:
        Resolved absolute Path to the repo.

    Raises:
        FileNotFoundError: If the path does not exist.
        NotADirectoryError: If the path is not a directory.

    Example:
        >>> repo = load_local_repo("/home/user/my-project")
        >>> print(repo)
        /home/user/my-project
    """
    repo_path = Path(path).expanduser().resolve()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {repo_path}")

    logger.info("Loaded local repo: %s", repo_path)
    return repo_path


def get_project_files(path: str | Path) -> list[Path]:
    """
    Recursively collect all source files in a project directory.

    Skips IGNORED_DIRS and returns only files whose extension is in SOURCE_EXTENSIONS.

    Args:
        path: Root directory of the project.

    Returns:
        Sorted list of Path objects for all discovered source files.

    Example:
        >>> files = get_project_files("/home/user/my-project")
        >>> print(files[0])
        /home/user/my-project/src/main.py
    """
    root = Path(path).expanduser().resolve()
    collected: list[Path] = []

    logger.info("Scanning project files in: %s", root)

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # Prune ignored directories in-place (modifies os.walk iteration)
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]

        for filename in filenames:
            file_path = Path(dirpath) / filename
            if file_path.suffix.lower() in SOURCE_EXTENSIONS:
                collected.append(file_path)

    collected.sort()
    logger.info("Discovered %d source files.", len(collected))
    return collected


def is_github_url(source: str) -> bool:
    """
    Check whether a source string looks like a GitHub/remote Git URL.

    Args:
        source: URL or local path string.

    Returns:
        True if source appears to be a remote Git URL.

    Example:
        >>> is_github_url("https://github.com/user/repo")
        True
        >>> is_github_url("/home/user/repo")
        False
    """
    return source.startswith(("https://", "http://", "git@", "ssh://"))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _GitProgressPrinter(git.RemoteProgress):
    """Prints clone progress to the logger."""

    def update(
        self,
        op_code: int,
        cur_count: str | float,
        max_count: str | float | None = None,
        message: str = "",
    ) -> None:
        if message:
            logger.debug("Git: %s", message)
