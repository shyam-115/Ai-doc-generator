# Ai-doc-generator

## Project Overview

`Ai-doc-generator` is an intelligent documentation generation tool that leverages AI to automatically create comprehensive and accurate documentation for software projects. It analyzes source code, extracts key architectural components, dependencies, and execution flows, and then synthesizes this information into human-readable documentation, including READMEs, API references, and architectural overviews. This project aims to streamline the documentation process, enhance developer productivity, and improve code maintainability by keeping documentation up-to-date with the codebase.

## Tech Stack

*   **Languages**: Python (primary), JSON, YAML, Markdown, TOML
*   **Dependency Management**: [Poetry](https://python-poetry.org/)
*   **Code Analysis**: [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) for robust syntax parsing and symbol extraction.
*   **AI/LLM Integration**: Gemini API for advanced text generation and understanding.
*   **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/) for building a high-performance API.
*   **Vector Database**: Custom vector store implementation for embeddings and semantic search.
*   **Logging**: Standard Python `logging` module.

## Prerequisites

Before you begin, ensure you have the following installed:

*   **Python**: Version 3.8 or higher.
*   **Poetry**: For dependency management. Install it via `pip install poetry`.
*   **Git**: For cloning the repository.
*   **Gemini API Key**: An API key for the Gemini model, required for documentation generation.

## Installation

Follow these steps to set up the project locally:

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/Ai-doc-generator.git
    cd Ai-doc-generator
    ```

2.  **Install dependencies**:
    ```bash
    poetry install
    ```

3.  **Set up environment variables**:
    Create a `.env` file in the project root or set the `GEMINI_API_KEY` environment variable directly.
    ```bash
    # .env file example
    GEMINI_API_KEY="your_gemini_api_key_here"
    ```

## Usage

`Ai-doc-generator` can be used via its Command Line Interface (CLI) or as a RESTful API.

### Command Line Interface (CLI)

Generate documentation for a project using the CLI:

```bash
poetry run python -m cli.generate_docs <path_to_repository> --output <output_directory>
```

**Example**:
To generate documentation for the current directory and save it to a `docs` folder:

```bash
poetry run python -m cli.generate_docs . --output docs
```

### RESTful API

The project exposes a RESTful API for programmatic documentation generation.

1.  **Start the API server**:
    ```bash
    poetry run uvicorn api.main:app --reload
    ```
    The API will be available at `http://127.0.0.1:8000`.

2.  **API Endpoint**:
    The primary endpoint for documentation generation is typically `/generate`. You can send a `POST` request with details about the repository to be documented.

    **Example Request (using `curl`)**:
    ```bash
    curl -X POST "http://127.0.0.1:8000/generate" \
         -H "Content-Type: application/json" \
         -d '{
               "repository_path": "/path/to/your/project",
               "output_directory": "/path/to/output/docs",
               "doc_types": ["readme", "api_reference", "architecture"]
             }'
    ```

    Replace `/path/to/your/project` and `/path/to/output/docs` with the actual paths.

## Project Structure

```
Ai-doc-generator/
├── analyzer/                     # Code analysis modules (dependency, call graphs)
│   ├── __init__.py
│   ├── call_graph.py             # Builds call graphs
│   └── dependency_graph.py       # Builds module dependency graphs
├── api/                          # RESTful API implementation
│   ├── __init__.py
│   └── main.py                   # FastAPI application entry point
├── chunking/                     # Code chunking and splitting utilities for LLM processing
│   ├── __init__.py
│   └── code_chunker.py           # Handles breaking down code into manageable chunks
├── cli/                          # Command Line Interface
│   ├── __init__.py
│   └── generate_docs.py          # CLI entry point for documentation generation
├── core/                         # Core utilities and foundational modules
│   ├── __init__.py
│   ├── language_detector.py      # Detects programming languages in files
│   ├── repo_loader.py            # Loads and manages repository files
│   ├── state_manager.py          # Manages project state during generation
│   └── utils.py                  # General utility functions
├── generator/                    # AI-driven documentation generation logic
│   ├── __init__.py
│   ├── api_doc_generator.py      # Generates API reference documentation
│   ├── architecture_generator.py # Generates architectural overviews
│   ├── project_structure_generator.py # Generates project structure documentation
│   └── readme_generator.py       # Generates README.md files
├── parser/                       # Source code parsing and symbol extraction
│   ├── __init__.py
│   ├── symbol_extractor.py       # Extracts functions, classes, and variables
│   └── tree_sitter_loader.py     # Loads Tree-sitter grammars
├── test_llm/                     # (Potentially) LLM-specific tests or experiments
├── tests/                        # Unit and integration tests
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_cli.py
│   ├── test_code_chunker.py
│   ├── test_dependency_graph.py
│   ├── test_language_detector.py
│   ├── test_repo_loader.py
│   └── test_symbol_extractor.py
├── vector_store/                 # Embeddings and vector database interaction
│   ├── __init__.py
│   └── embeddings.py             # Handles embedding generation and storage
├── README.md                     # Project README file
├── clients.py                    # LLM client integrations (e.g., Gemini)
├── config.py                     # Project configuration settings
├── logger.py                     # Centralized logging configuration
├── poetry.lock                   # Poetry lock file for deterministic dependencies
└── pyproject.toml                # Poetry project definition and dependencies
```

## API Reference

The `Ai-doc-generator` provides both a CLI entry point and a programmatic API.

### CLI Entry Point

*   **`cli.generate_docs