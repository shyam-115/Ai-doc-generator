"""
CLI interface for AI Doc Generator.

Entry point: `docgen generate <repo_url_or_path>`

Orchestrates the full documentation pipeline:
  1. Repo ingestion (clone or local load)
  2. Language detection
  3. AST parsing and symbol extraction
  4. Dependency and call graph analysis
  5. Code chunking
  6. Embedding indexing
  7. LLM documentation generation
  8. Writing output files to docs/
"""

from __future__ import annotations

import concurrent.futures
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.theme import Theme

# ---------------------------------------------------------------------------
# Load environment variables from .env file
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Setup path so the CLI works both as a script and as an installed command
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.utils import write_atomic
from config import settings
from logger import setup_logger

logger = setup_logger("cli")

custom_theme = Theme(
    {
        "info": "dim cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "step": "bold magenta",
    }
)
console = Console(theme=custom_theme)


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

@click.group()
@click.version_option("0.1.0", prog_name="docgen")
def cli() -> None:
    """
    AI Doc Generator — automatically document any software repository.

    \b
    Examples:
      docgen generate https://github.com/user/repo
      docgen generate ./my-local-project
      docgen generate ./my-project --output-dir ./my-docs
    """


@cli.command()
@click.argument("source")
@click.option(
    "--output-dir",
    "-o",
    default=None,
    show_default=True,
    help="Output directory for generated docs (default: ./docs).",
)
@click.option(
    "--skip-embeddings",
    is_flag=True,
    default=False,
    help="Skip building the FAISS embedding index (faster, offline).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Run pipeline without calling the LLM (for testing).",
)
@click.option(
    "--incremental",
    "-i",
    is_flag=True,
    default=False,
    help="Only process files that have changed since the last run.",
)
@click.option(
    "--workers",
    type=int,
    default=None,
    help="Number of parallel workers (default: max_workers from config)",
)
def generate(
    source: str,
    output_dir: str | None,
    skip_embeddings: bool,
    dry_run: bool,
    incremental: bool,
    workers: int | None,
) -> None:
    """
    Generate documentation for a repository.

    SOURCE can be a GitHub URL or a local path:

    \b
      docgen generate https://github.com/tiangolo/fastapi
      docgen generate /home/user/my-project
    """
    out_dir = Path(output_dir or settings.output_dir)
    max_workers = workers or settings.max_workers

    console.print(
        Panel.fit(
            "[bold cyan]AI Doc Generator[/bold cyan] — generating documentation...\n"
            f"[dim]Source:[/dim] {source}\n"
            f"[dim]Output:[/dim] {out_dir}",
            border_style="cyan",
        )
    )

    start = time.time()

    try:
        run_pipeline(
            source=source,
            output_dir=str(out_dir),
            skip_embeddings=skip_embeddings,
            dry_run=dry_run,
            incremental=incremental,
            max_workers=max_workers,
        )
    except KeyboardInterrupt:
        console.print("\n[warning]Interrupted by user.[/warning]")
        sys.exit(1)
    except Exception as exc:
        console.print(f"\n[error]Pipeline failed:[/error] {exc}")
        logger.exception("Pipeline error")
        sys.exit(1)

    elapsed = time.time() - start
    _print_summary(out_dir, elapsed)


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(
    source: str,
    output_dir: str = "./docs",
    skip_embeddings: bool = False,
    dry_run: bool = False,
    incremental: bool = False,
    max_workers: int | None = None,
) -> None:
    """
    Execute the full documentation generation pipeline.

    This function is also callable from the FastAPI backend.

    Args:
        source: GitHub URL or local path string.
        output_dir: Directory to write output files.
        skip_embeddings: If True, skip FAISS indexing step.
        dry_run: If True, skip LLM calls and write placeholder files.
        incremental: If True, only re-parse files that have changed.
        max_workers: Number of parallel parsing workers.
    """
    workers = max_workers or settings.max_workers
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    state_file = out_dir / settings.docgen_state_file

    temp_clone_dir: str | None = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:

        # ------------------------------------------------------------------ #
        # STEP 1: Ingest repository
        # ------------------------------------------------------------------ #
        task = progress.add_task("[step]📥 Ingesting repository...[/step]", total=None)

        from core.repo_loader import clone_repo, load_local_repo, get_project_files, is_github_url

        if is_github_url(source):
            temp_clone_dir = tempfile.mkdtemp(prefix="ai-doc-gen-")
            repo_path = clone_repo(source, temp_clone_dir)
        else:
            repo_path = load_local_repo(source)

        project_name = repo_path.name
        files = get_project_files(repo_path)
        progress.update(task, description=f"[step]✅ Ingested — {len(files)} files found[/step]", completed=1, total=1)

        # ------------------------------------------------------------------ #
        # STEP 2: Language detection
        # ------------------------------------------------------------------ #
        task2 = progress.add_task("[step]🔍 Detecting languages...[/step]", total=None)
        from core.language_detector import detect_languages, filter_parseable, group_by_language

        detected = detect_languages(files)
        parseable = filter_parseable(detected)
        lang_groups = group_by_language(detected)
        progress.update(
            task2,
            description=f"[step]✅ Languages — {', '.join(list(lang_groups.keys())[:5])}[/step]",
            completed=1, total=1,
        )

        # ------------------------------------------------------------------ #
        # STEP 3: Symbol extraction (parallel)
        # ------------------------------------------------------------------ #
        task3 = progress.add_task(
            f"[step]🌲 Parsing AST ({len(parseable)} files)...[/step]",
            total=len(parseable),
        )
        from parser.symbol_extractor import extract_symbols, FileSymbols
        from core.state_manager import ProjectState
        
        state = ProjectState(state_file)
        
        # Determine which files actually need parsing
        files_to_parse = []
        for entry in parseable:
            if incremental and not state.is_file_changed(entry["file"]):
                continue
            files_to_parse.append(entry)

        if incremental and not files_to_parse:
            progress.update(task3, description="[step]✅ No files changed (Incremental)[/step]", completed=len(parseable))
            console.print("\n[success]✨ Incremental mode: No source files have changed since the last run. Skipping generation.[/success]")
            
            # Cleanup temp clone
            if temp_clone_dir and Path(temp_clone_dir).exists():
                shutil.rmtree(temp_clone_dir, ignore_errors=True)
            return

        symbols_map: dict[str, FileSymbols] = {}

        def _extract_one(entry: dict) -> FileSymbols:
            return extract_symbols(entry["file"], entry["language"])

        # First, load unchanged symbols from state buffer
        if incremental:
            for entry in parseable:
                if entry not in files_to_parse:
                    cached = state.get_cached_symbols(entry["file"])
                    if cached:
                        symbols_map[cached.file] = cached
                        progress.advance(task3)

        # Then, parse the changed files in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_extract_one, e): e for e in files_to_parse}
            for future in concurrent.futures.as_completed(futures):
                try:
                    sym = future.result()
                    symbols_map[sym.file] = sym
                    if incremental:
                        state.update_file_state(sym.file, sym)
                except Exception as exc:
                    logger.warning("Symbol extraction error: %s", exc)
                progress.advance(task3)
                
        if incremental:
            state.save()

        symbols_list = list(symbols_map.values())
        progress.update(task3, description=f"[step]✅ Extracted symbols from {len(symbols_list)} files ({len(files_to_parse)} re-parsed)[/step]")

        # ------------------------------------------------------------------ #
        # STEP 4: Dependency + Call graphs
        # ------------------------------------------------------------------ #
        task4 = progress.add_task("[step]🕸️  Building dependency graph...[/step]", total=None)
        from analyzer.dependency_graph import build_dependency_graph, get_graph_summary
        from analyzer.call_graph import build_call_graph, get_entry_points, get_execution_flows

        dep_graph = build_dependency_graph(symbols_list)
        graph_summary = get_graph_summary(dep_graph)
        call_graph = build_call_graph(symbols_list)
        entry_points = get_entry_points(call_graph)
        execution_flows = get_execution_flows(call_graph, entry_points)

        progress.update(
            task4,
            description=f"[step]✅ Graph — {graph_summary.node_count} nodes, {graph_summary.edge_count} edges[/step]",
            completed=1, total=1,
        )

        # ------------------------------------------------------------------ #
        # STEP 5: Code chunking
        # ------------------------------------------------------------------ #
        task5 = progress.add_task("[step]✂️  Chunking code...[/step]", total=None)
        from chunking.code_chunker import chunk_repository, get_chunk_stats

        all_chunks = chunk_repository(files, symbols_map, max_workers=workers)
        stats = get_chunk_stats(all_chunks)
        progress.update(
            task5,
            description=f"[step]✅ Chunked — {stats['total']} chunks[/step]",
            completed=1, total=1,
        )

        # ------------------------------------------------------------------ #
        # STEP 6: Embedding index (optional)
        # ------------------------------------------------------------------ #
        if not skip_embeddings and not dry_run and settings.gemini_api_key:
            task6 = progress.add_task(
                f"[step]🔢 Building embedding index ({len(all_chunks)} chunks)...[/step]",
                total=None,
            )
            from vector_store.embeddings import build_index

            build_index(all_chunks)
            progress.update(task6, description=f"[step]✅ Embedded {len(all_chunks)} chunks[/step]",
                            completed=1, total=1)
        else:
            console.print("[info]⏭  Skipping embedding index.[/info]")

        # ------------------------------------------------------------------ #
        # STEP 7: API endpoint detection
        # ------------------------------------------------------------------ #
        task7 = progress.add_task("[step]🔌 Detecting API endpoints...[/step]", total=None)
        
        if not dry_run:
            from generator.api_doc_generator import detect_endpoints
            endpoints = detect_endpoints(files, symbols_list)
        else:
            # Simple endpoint detection for dry-run mode (without LLM imports)
            endpoints = []
            for symbols in symbols_list:
                for func in symbols.functions:
                    if any(decorator.startswith(('@app.', '@router.', '@bp.')) for decorator in func.decorators):
                        endpoints.append(f"{symbols.file}::{func.name}")
        
        progress.update(
            task7,
            description=f"[step]✅ Detected {len(endpoints)} endpoints[/step]",
            completed=1, total=1,
        )

        # ------------------------------------------------------------------ #
        # STEP 8: Generate documentation
        # ------------------------------------------------------------------ #
        entry_names = [ep.split("::")[-1] for ep in entry_points[:5]]

        if dry_run:
            _write_dry_run_docs(out_dir, project_name, files, detected, stats, endpoints)
        else:
            _generate_docs(
                out_dir=out_dir,
                project_name=project_name,
                repo_path=repo_path,
                detected=detected,
                symbols_list=symbols_list,
                dep_graph=dep_graph,
                call_flows=execution_flows,
                graph_summary=graph_summary,
                endpoints=endpoints,
                entry_names=entry_names,
                progress=progress,
            )

    # Cleanup temp clone
    if temp_clone_dir and Path(temp_clone_dir).exists():
        shutil.rmtree(temp_clone_dir, ignore_errors=True)


def _generate_docs(
    out_dir: Path,
    project_name: str,
    repo_path: Path,
    detected: list[dict],
    symbols_list,
    dep_graph,
    call_flows,
    graph_summary,
    endpoints,
    entry_names: list[str],
    progress: Progress,
) -> None:
    """Generate all four documentation files via LLM."""
    from generator.readme_generator import generate_readme
    from generator.architecture_generator import generate_architecture
    from generator.api_doc_generator import generate_api_docs
    from generator.project_structure_generator import generate_project_structure

    docs = [
        ("📝 README.md", "README.md",
         lambda: generate_readme(project_name, repo_path, detected, symbols_list,
                                 graph_summary, entry_names)),
        ("🏗️  architecture.md", "architecture.md",
         lambda: generate_architecture(project_name, symbols_list, dep_graph,
                                       call_flows, graph_summary)),
        ("🔌 api_docs.md", "api_docs.md",
         lambda: generate_api_docs(project_name, endpoints, symbols_list)),
        ("📁 project_structure.md", "project_structure.md",
         lambda: generate_project_structure(project_name, repo_path,
                                             [d["file"] for d in detected], symbols_list)),
    ]

    for label, filename, generator_fn in docs:
        t = progress.add_task(f"[step]{label}...[/step]", total=None)
        try:
            content = generator_fn()
            write_atomic(out_dir / filename, content)
            progress.update(t, description=f"[step]✅ {filename}[/step]", completed=1, total=1)
        except Exception as exc:
            logger.error("Failed to generate %s: %s", filename, exc)
            progress.update(t, description=f"[error]❌ {filename}: {exc}[/error]", completed=1, total=1)


def _write_dry_run_docs(
    out_dir: Path,
    project_name: str,
    files: list[Path],
    detected: list[dict],
    stats: dict,
    endpoints: list,
) -> None:
    """Write placeholder docs for dry-run mode (no LLM calls)."""
    from core.language_detector import group_by_language
    lang_groups = group_by_language(detected)

    langs = ", ".join(
        f"{k} ({len(v)})" for k, v in sorted(lang_groups.items(), key=lambda x: -len(x[1]))
        if k not in ("unknown",)
    )

    readme = f"""# {project_name}

> **[DRY RUN]** This README was generated without LLM calls.

## Project Stats
- **Files**: {len(files)}
- **Languages**: {langs}
- **Code Chunks**: {stats['total']}
- **APIs detected**: {len(endpoints)}

## Usage
Set `GEMINI_API_KEY` and run:
```bash
docgen generate <source>
```
"""
    for fname, content in [
        ("README.md", readme),
        ("architecture.md", f"# Architecture\n\n> [DRY RUN] Set GEMINI_API_KEY to generate.\n"),
        ("api_docs.md", f"# API Docs\n\n> [DRY RUN] {len(endpoints)} endpoints detected.\n"),
        ("project_structure.md", f"# Project Structure\n\n> [DRY RUN] {len(files)} files scanned.\n"),
    ]:
        write_atomic(out_dir / fname, content)

    console.print("[info]Dry run complete — placeholder files written.[/info]")


def _print_summary(out_dir: Path, elapsed: float) -> None:
    """Print a rich summary table of generated files."""
    table = Table(title="Generated Documentation", show_header=True, header_style="bold cyan")
    table.add_column("File", style="green")
    table.add_column("Size", justify="right")
    table.add_column("Status")

    for fname in ["README.md", "architecture.md", "api_docs.md", "project_structure.md"]:
        fpath = out_dir / fname
        if fpath.exists():
            size = f"{fpath.stat().st_size / 1024:.1f} KB"
            status = "✅"
        else:
            size = "—"
            status = "❌"
        table.add_row(str(out_dir / fname), size, status)

    console.print()
    console.print(table)
    console.print(
        f"\n[success]✅ Documentation generated in {elapsed:.1f}s → {out_dir}[/success]"
    )


# ---------------------------------------------------------------------------
# Script entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
