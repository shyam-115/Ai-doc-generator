# AI Doc Generator

> An AI-powered system that automatically generates comprehensive documentation for any software repository.

## Quick Start

```bash
# Clone and install
cd /home/shyam/Ai-doc-generator
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

poetry install

# Generate docs for a GitHub repo
poetry run docgen generate https://github.com/user/repo

# Generate docs for a local project
poetry run docgen generate ./my-project

# Dry run (no LLM calls)
poetry run docgen generate ./my-project --dry-run

# Run the API server
poetry run uvicorn api.main:app --reload --port 8000
```

## Output

All generated docs are written to `./docs/`:
- `docs/README.md`
- `docs/architecture.md`
- `docs/api_docs.md`
- `docs/project_structure.md`
