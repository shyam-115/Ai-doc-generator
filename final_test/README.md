# Ai-doc-generator

## Project Overview

The Ai-doc-generator is an advanced tool designed to automate the generation of comprehensive documentation for software projects. Leveraging static code analysis, dependency graphing, and AI-driven insights, it produces various documentation artifacts, including READMEs, API references, architectural overviews, and project structure descriptions. This project aims to streamline the documentation process, ensuring up-to-date and accurate project insights with minimal manual effort.

**Key Features:**
*   **Code Analysis**: Extracts symbols, builds dependency and call graphs, and identifies project entry points.
*   **Code Chunking**: Divides source files into manageable, semantically relevant chunks for efficient processing.
*   **Language Detection**: Automatically identifies programming languages within a repository.
*   **AI-Powered Generation**: Utilizes AI models (via embeddings and vector stores) to generate high-quality, context-aware documentation.
*   **Modular Documentation**: Generates specific documentation types such as READMEs, API documentation, architecture diagrams, and project structure outlines.
*   **CLI & API Interfaces**: Provides both a command-line interface for direct use and a RESTful API for integration into CI/CD pipelines or other systems.

## Tech Stack

*   **Languages**: Python
*   **Package Management**: Poetry
*   **Code Parsing**: Tree-sitter (via `tree_sitter_loader`)
*   **Web Framework**: Likely FastAPI (inferred from `api/main.py` and `APIEndpoint` class)
*   **AI/ML**: Embeddings and Vector Stores (for RAG-based documentation generation)
*   **Graphing**: NetworkX or similar (inferred from `dependency_graph.py`, `call_graph.py`, `build_dependency_graph`, `build_call_graph`)
*   **Logging**: Standard Python `logging` module (via `logger.py`)

## Prerequisites

Before you begin, ensure you have the following installed:

*   **Python**: Version 3.8 or higher.
*   **Poetry**: For dependency management. Install it via `pip install poetry` or refer to the [official Poetry documentation](https://python-poetry.org/docs/#installation).
*   **Git**: Required for cloning repositories.

## Installation

Follow these steps to set up the project locally:

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-org/Ai-doc-generator.git
    cd Ai-doc-generator
    ```

2.  **Install dependencies using Poetry**:
    ```bash
    poetry install
    ```

3.  **Activate the Poetry shell**:
    ```bash
    poetry shell
    ```

    You are now in the project's virtual environment.

## Usage

The Ai-doc-generator can be used via its Command Line Interface (CLI) or its RESTful API.

### Command Line Interface (CLI)

Generate documentation for a local or remote repository using the CLI.

**Generate documentation for a local repository:**
```bash
poetry run python -m cli.generate_docs generate --path /path/to/your/local/repo --output-dir ./docs
```

**Generate documentation for a remote Git repository:**
```bash
poetry run python -m cli.generate_docs generate --repo-url https://github.com/owner/repo.git --output-dir ./docs
```

**Available CLI Options:**
*   `--path <path>`: Path to a local repository.
*   `--repo-url <url>`: URL of a remote Git repository.
*   `--output-dir <dir>`: Directory to save the generated documentation. (Default: `./generated_docs`)
*   `--doc-types <type1,type2>`: Comma-separated list of documentation types to generate (e.g., `readme,api,architecture`). (Default: `all`)

### RESTful API

The project exposes a RESTful API for programmatic interaction.

1.  **Start the API server**:
    Ensure you are in the Poetry shell (`poetry shell`).
    ```bash
    poetry run python -m api.main
    ```
    The API will typically run on `http://127.0.0.1:8000`.

2.  **Access API Documentation**:
    Once the server is running, you can access the interactive API documentation (Swagger UI) at `http://127.0.0.1:8000/docs`.

## Project Structure

```
Ai-doc-generator/
├── analyzer/                     # Modules for code analysis (dependency, call graphs)
│   ├── __init__.py
│   ├── call_graph.py             # Builds the call graph of functions/methods
│   └── dependency_graph.py       # Builds the module-level dependency graph
├── api/                          # RESTful API implementation
│   ├── __init__.py
│   └── main.py                   # Main FastAPI application entry point
├── chunking/                     # Code chunking utilities
│   ├── __init__.py
│   └── code_chunker.py           # Splits code files into semantic chunks
├── cli/                          # Command Line Interface tools
│   ├── __init__.py
│   └── generate_docs.py          # CLI entry point for documentation generation
├── core/                         # Core utilities and helpers
│   ├── __init__.py
│   ├── language_detector.py      # Detects programming languages in files/repositories
│   └── repo_loader.py            # Handles cloning and loading of local/remote repositories
├── final_test/                   # (Potentially integration or end-to-end tests)
├── generator/                    # Modules responsible for generating different documentation types
│   ├── __init__.py
│   ├── api_doc_generator.py      # Generates API reference documentation
│   ├── architecture_generator.py # Generates project architecture overview
│   ├── project_structure_generator.py # Generates project directory structure documentation
│   └── readme_generator.py       # Generates README.md files
├── parser/                       # Code parsing and symbol extraction
│   ├── __init__.py
│   ├── symbol_extractor.py       # Extracts functions, classes, and other symbols from code
│   └── tree_sitter_loader.py     # Loads Tree-sitter grammars for various languages
├── tests/                        # Unit and integration tests
│   ├── __init__.py
│   ├── conftest.py               # Pytest configuration and fixtures
│   ├── test_cli.py
│   ├── test_code_chunker.py
│   ├── test_dependency_graph.py
│   ├── test_language_detector.py
│   ├── test_repo_loader.py
│   └── test_symbol_extractor.py
├── vector_store/                 # Modules for managing embeddings and vector databases
│   ├── __init__.py
│   └── embeddings.py             # Handles creation and storage of code embeddings
├── README_PROJECT.md             # Example or template README
├── config.py                     # Project configuration settings
├── logger.py                     # Centralized logging configuration
├── poetry.lock                   # Poetry lock file for deterministic dependencies
└── pyproject.toml                # Poetry project definition and dependencies
```

## API Reference

The following are key API endpoints and public functions available for programmatic use.

### `POST /generate`

Initiates the documentation generation process for a given repository.

*   **Description**: Submits a request to generate documentation. The process runs asynchronously.
*   **Request Body (`GenerateRequest`)**:
    *   `repo_path` (string, optional): Local path to the repository.
    *   `repo_url` (string, optional): URL of a remote Git repository.
    *   `output_dir` (string, optional): Directory to save generated documentation.
    *   `doc_types` (list of strings, optional): Specific documentation types to generate (e.g., `["readme", "api"]`).
*   **Response Body (`GenerateResponse`)**:
    *   `job_id` (string): Unique identifier for the generation job.
    *   `status` (string): Initial status of the job (e.g., "PENDING").

### `GET /status/{job_id}`

Retrieves the status of a documentation generation job.

*   **Description**: Checks the current progress and outcome of a previously initiated generation job.
*   **Path Parameter**:
    *   `job_id` (string): The ID of the job to query.
*   **Response Body (`GenerateResponse`)**:
    *   `job_id` (string): The ID of the job.
    *   `status` (string): Current status (e.g., "PENDING", "IN_PROGRESS", "COMPLETED", "FAILED").
    *   `result` (string, optional): Path to generated documentation or error message if failed.

### Core Functions

These functions represent key entry points or utilities within the project's logic, accessible if integrating directly with the Python modules.

*   `generate_docs(repo_path: str = None, repo_url: str = None, output_dir: str = None, doc_types: list[str] = None) -> str`:
    *   **Description**: Main function to orchestrate documentation generation. Accepts either a local path or a remote URL.
    *   **Returns**: A job ID or path to generated documentation.

