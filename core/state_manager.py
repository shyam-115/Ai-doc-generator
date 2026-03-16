"""
State Management module for AI Doc Generator.

Provides the `ProjectState` class to track file hashes and cached AST symbols
across docgen runs to enable fast, incremental documentation generation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from logger import setup_logger
from core.utils import save_json_locked
from parser.symbol_extractor import (
    FileSymbols,
    FunctionSymbol,
    ClassSymbol,
    ImportSymbol,
)

logger = setup_logger("state_manager")


class ProjectState:
    """
    Manages incremental generation state, mapping files to their hash
    and extracted AST symbols.
    """

    def __init__(self, state_file: str | Path):
        self.state_file = Path(state_file)
        self.file_hashes: dict[str, str] = {}
        self.file_symbols: dict[str, FileSymbols] = {}
        self._load()

    def _load(self) -> None:
        """Load state from disk."""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)

            self.file_hashes = data.get("file_hashes", {})
            symbols_data = data.get("file_symbols", {})

            for filepath, sym_dict in symbols_data.items():
                self.file_symbols[filepath] = _dict_to_file_symbols(sym_dict)

            logger.info("Loaded project state: %d files tracked", len(self.file_hashes))
        except Exception as exc:
            logger.warning("Failed to load project state from %s: %s", self.state_file, exc)
            self.file_hashes = {}
            self.file_symbols = {}

    def save(self) -> None:
        """Save the current state to disk."""
        data = {
            "file_hashes": self.file_hashes,
            "file_symbols": {
                filepath: sym.to_dict()
                for filepath, sym in self.file_symbols.items()
            },
        }
        try:
            save_json_locked(self.state_file, data)
            logger.debug("Saved project state to %s", self.state_file)
        except Exception as exc:
            logger.error("Failed to save project state: %s", exc)

    def get_file_hash(self, file_path: str | Path) -> str:
        """Compute the SHA-256 hash of a file's contents."""
        path = Path(file_path)
        try:
            content = path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except OSError:
            return ""

    def is_file_changed(self, file_path: str | Path) -> bool:
        """Check if a file has changed since the last run by comparing its hash."""
        current_hash = self.get_file_hash(file_path)
        if not current_hash:
            return True  # Treat unreadable/missing as changed to trigger re-parse or error
        cached_hash = self.file_hashes.get(str(file_path))
        return current_hash != cached_hash

    def update_file_state(self, file_path: str | Path, symbols: FileSymbols) -> None:
        """Update the stored hash and symbols for a file."""
        current_hash = self.get_file_hash(file_path)
        if current_hash:
            self.file_hashes[str(file_path)] = current_hash
            self.file_symbols[str(file_path)] = symbols

    def get_cached_symbols(self, file_path: str | Path) -> FileSymbols | None:
        """Retrieve cached symbols for a file."""
        return self.file_symbols.get(str(file_path))


def _dict_to_file_symbols(data: dict) -> FileSymbols:
    """Deserialize a dictionary back into a FileSymbols dataclass hierarchy."""
    funcs = []
    for f in data.get("functions", []):
        funcs.append(
            FunctionSymbol(
                name=f.get("name", ""),
                params=f.get("params", []),
                calls=f.get("calls", []),
                decorators=f.get("decorators", []),
                start_line=f.get("start_line", 0),
                end_line=f.get("end_line", 0),
                docstring=f.get("docstring"),
                is_async=f.get("is_async", False),
                is_method=f.get("is_method", False),
            )
        )

    classes = []
    for c in data.get("classes", []):
        methods = []
        for m in c.get("methods", []):
            methods.append(
                FunctionSymbol(
                    name=m.get("name", ""),
                    params=m.get("params", []),
                    calls=m.get("calls", []),
                    start_line=m.get("start_line", 0),
                    end_line=m.get("end_line", 0),
                    is_method=True,
                )
            )
        classes.append(
            ClassSymbol(
                name=c.get("name", ""),
                bases=c.get("bases", []),
                decorators=c.get("decorators", []),
                start_line=c.get("start_line", 0),
                end_line=c.get("end_line", 0),
                methods=methods,
            )
        )

    imports = []
    for i in data.get("imports", []):
        imports.append(
            ImportSymbol(
                module=i.get("module", ""),
                names=i.get("names", []),
                alias=i.get("alias"),
            )
        )

    return FileSymbols(
        file=data.get("file", ""),
        language=data.get("language", ""),
        functions=funcs,
        classes=classes,
        imports=imports,
    )
