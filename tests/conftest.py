"""
Shared test fixtures for AI Doc Generator.

Provides reusable temporary files, sample Python code, and symbol
dictionaries for use across all test modules.
"""

import tempfile
from pathlib import Path

import pytest

from parser.symbol_extractor import FileSymbols, FunctionSymbol, ClassSymbol, ImportSymbol


# ---------------------------------------------------------------------------
# Sample source code fixtures
# ---------------------------------------------------------------------------

SAMPLE_PYTHON_CODE = '''\
"""Sample module for testing."""

import os
from pathlib import Path


class AuthService:
    """Handles authentication."""

    def __init__(self, db_url: str) -> None:
        self.db_url = db_url

    def login(self, user: str, password: str) -> bool:
        """Authenticate a user."""
        result = self.authenticate(user, password)
        return result

    def authenticate(self, user: str, password: str) -> bool:
        return user == "admin" and password == "secret"


def get_user(user_id: int) -> dict:
    """Fetch user by ID."""
    return {"id": user_id, "name": "test"}


def delete_user(user_id: int) -> None:
    """Remove a user."""
    get_user(user_id)
'''

SAMPLE_JS_CODE = """\
import express from 'express';

const router = express.Router();

router.get('/users/:id', (req, res) => {
    res.json({ id: req.params.id });
});

router.post('/users', async (req, res) => {
    const user = await createUser(req.body);
    res.status(201).json(user);
});

async function createUser(data) {
    return { ...data, id: Date.now() };
}
"""


@pytest.fixture
def temp_python_file(tmp_path: Path) -> Path:
    """Create a temporary Python file with sample code."""
    f = tmp_path / "auth.py"
    f.write_text(SAMPLE_PYTHON_CODE)
    return f


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """Create a minimal project directory with several source files."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(SAMPLE_PYTHON_CODE)
    (tmp_path / "src" / "utils.py").write_text("def helper(): pass\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_noop(): pass\n")
    (tmp_path / "node_modules" / "lib").mkdir(parents=True)
    (tmp_path / "node_modules" / "lib" / "index.js").write_text("// should be ignored")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "main.cpython-311.pyc").write_bytes(b"\x00" * 4)
    (tmp_path / "README.md").write_text("# Test Project\n")
    return tmp_path


@pytest.fixture
def sample_function_symbol() -> FunctionSymbol:
    """Sample FunctionSymbol instance."""
    return FunctionSymbol(
        name="login",
        params=["user", "password"],
        calls=["authenticate"],
        start_line=12,
        end_line=16,
    )


@pytest.fixture
def sample_class_symbol(sample_function_symbol) -> ClassSymbol:
    """Sample ClassSymbol instance."""
    return ClassSymbol(
        name="AuthService",
        methods=[sample_function_symbol],
        bases=["BaseService"],
        start_line=6,
        end_line=20,
    )


@pytest.fixture
def sample_file_symbols(
    sample_function_symbol, sample_class_symbol, temp_python_file
) -> FileSymbols:
    """Sample FileSymbols wrapping function and class symbols."""
    return FileSymbols(
        file=str(temp_python_file),
        language="python",
        functions=[sample_function_symbol],
        classes=[sample_class_symbol],
        imports=[ImportSymbol(module="os"), ImportSymbol(module="pathlib", names=["Path"])],
    )
