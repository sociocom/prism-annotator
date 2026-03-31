"""Typer-based CLI for prism-annotator."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(
    help="PRISM annotation of medical texts using LLMs.",
    no_args_is_help=True,
)


def _setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ── extract ──────────────────────────────────────────────────────────────────


@app.command()
def extract(
    config: Annotated[Path, typer.Option(help="Path to YAML config")] = ...,
    entity_results: Annotated[
        Optional[Path], typer.Option(help="Entity-phase results.json (for relation phases)")
    ] = None,
    dry_run: Annotated[bool, typer.Option(help="Process only 1 document")] = False,
    resume: Annotated[
        Optional[Path], typer.Option(help="Resume a previous run directory")
    ] = None,
    reparse: Annotated[
        Optional[Path], typer.Option(help="Re-parse raw outputs (no LLM calls)")
    ] = None,
    debug: Annotated[bool, typer.Option(help="Enable debug logging")] = False,
) -> None:
    """Run entity or relation extraction."""
    _setup_logging(debug)

    from prism_annotator.config import load_config
    from prism_annotator.models import finalise_results, load_results, save_results
    from prism_annotator.output import write_xml
    from prism_annotator.pipeline import (
        reparse_tanl_entities,
        reparse_tanl_relations,
        run_tanl_entity_extraction,
        run_tanl_extraction,
    )
    from prism_annotator.postprocess import compute_statistics, correct_results, validate_results

    cfg = load_config(config)
    phase = cfg.phase
    logger = logging.getLogger("prism_annotator")
    logger.info("Configuration loaded: %s (phase=%s)", cfg.experiment_name, phase)

    is_entity_phase = phase == "entity"

    # Output directory
    if resume:
        run_dir = resume
        logger.info("Resuming run: %s", run_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = Path(cfg.output.output_dir) / f"{cfg.experiment_name}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    if reparse:
        reparse_dir = reparse
        if is_entity_phase:
            from prism_annotator.data_loader import load_documents

            documents = load_documents(cfg.data)
            original_texts = {doc.doc_id: doc.text for doc in documents}
            logger.info("Re-parsing entity raw outputs from %s (%d documents)", reparse_dir, len(original_texts))
            results = reparse_tanl_entities(reparse_dir, original_texts)
        else:
            if not entity_results:
                logger.error("--entity-results is required for relation --reparse")
                raise typer.Exit(1)
            entity_docs = load_results(entity_results)
            logger.info("Re-parsing relation raw outputs from %s (%d documents)", reparse_dir, len(entity_docs))
            results = reparse_tanl_relations(reparse_dir, entity_docs, phase)

    elif is_entity_phase:
        from prism_annotator.data_loader import load_documents

        documents = load_documents(cfg.data)
        logger.info("Loaded %d documents from %s", len(documents), cfg.data.input_path)

        if dry_run:
            documents = documents[:1]
            logger.info("Dry-run mode: processing 1 document only")

        results = run_tanl_entity_extraction(documents, cfg, output_dir=run_dir)
    else:
        if not entity_results:
            logger.error("--entity-results is required for relation phases")
            raise typer.Exit(1)

        entity_path = entity_results
        entity_docs = load_results(entity_path)
        logger.info("Loaded %d entity-annotated documents from %s", len(entity_docs), entity_path)

        if dry_run:
            entity_docs = entity_docs[:1]
            logger.info("Dry-run mode: processing 1 document only")

        results = run_tanl_extraction(
            entity_docs, cfg, output_dir=run_dir, phase=phase,
        )

    # When resuming, reload all results from incremental NDJSON
    ndjson_path = run_dir / "results.ndjson"
    if resume and ndjson_path.exists():
        all_results = finalise_results(ndjson_path)
    elif not results:
        logger.warning("No results produced")
        raise typer.Exit(1)
    else:
        all_results = results

    # Post-process
    n_corrections = correct_results(all_results)
    if n_corrections:
        logger.info("Applied %d correction(s)", n_corrections)
    warnings = validate_results(all_results)
    if warnings:
        logger.info("Validation warnings: %s", warnings)
    else:
        logger.info("All entities passed validation")

    # Write final outputs
    save_results(all_results, run_dir / "results.json")
    logger.info("Wrote results to %s", run_dir / "results.json")

    write_xml(all_results, run_dir / "results.xml")
    logger.info("XML output: %s", run_dir / "results.xml")

    stats = compute_statistics(all_results)
    stats_path = run_dir / "stats.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    logger.info("Extraction statistics: %s", json.dumps(stats, ensure_ascii=False))

    logger.info("Done. Output directory: %s", run_dir)


# ── merge ────────────────────────────────────────────────────────────────────


@app.command()
def merge(
    entity: Annotated[Path, typer.Option(help="Entity-phase results.json (base)")] = ...,
    medical_relation: Annotated[
        Optional[Path], typer.Option(help="Medical-relation-phase results.json")
    ] = None,
    time_relation: Annotated[
        Optional[Path], typer.Option(help="Time-relation-phase results.json")
    ] = None,
    output: Annotated[Path, typer.Option("-o", help="Output directory")] = ...,
    debug: Annotated[bool, typer.Option(help="Enable debug logging")] = False,
) -> None:
    """Merge entity + relation results into a single output."""
    _setup_logging(debug)

    from prism_annotator.merge import merge_relations
    from prism_annotator.models import AnnotatedDocument, load_results, save_results
    from prism_annotator.output import write_xml
    from prism_annotator.postprocess import compute_statistics, correct_results, validate_results

    logger = logging.getLogger("prism_annotator.merge")

    entity_docs = load_results(entity)
    logger.info("Loaded %d entity-base documents", len(entity_docs))

    rel_lists: list[list[AnnotatedDocument]] = []
    if medical_relation:
        med_docs = load_results(medical_relation)
        logger.info("Loaded %d medical-relation documents", len(med_docs))
        rel_lists.append(med_docs)
    if time_relation:
        time_docs = load_results(time_relation)
        logger.info("Loaded %d time-relation documents", len(time_docs))
        rel_lists.append(time_docs)

    all_results = merge_relations(entity_docs, *rel_lists)

    num_corrections = correct_results(all_results)
    if num_corrections:
        logger.info("Applied %d correction(s)", num_corrections)
    warning_counts = validate_results(all_results)
    if warning_counts:
        logger.warning("Validation warnings: %s", warning_counts)

    output.mkdir(parents=True, exist_ok=True)
    save_results(all_results, output / "results.json")
    write_xml(all_results, output / "results.xml")

    stats = compute_statistics(all_results)
    (output / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    logger.info("Done. Output: %s", output)


# ── visualise ────────────────────────────────────────────────────────────────


@app.command()
def visualise(
    run_dir: Annotated[Path, typer.Argument(help="Run output directory")] = ...,
    output: Annotated[
        Optional[Path], typer.Option("-o", help="Output HTML path")
    ] = None,
) -> None:
    """Generate an interactive HTML viewer for annotation results."""
    from prism_annotator.models import load_results
    from prism_annotator.visualize import build_html

    results_path = run_dir / "results.json"
    if not results_path.exists():
        typer.echo(f"Error: {results_path} not found", err=True)
        raise typer.Exit(1)

    docs = load_results(results_path)
    html = build_html(docs, run_dir.name)

    output_path = output or (run_dir / "viewer.html")
    output_path.write_text(html, encoding="utf-8")
    typer.echo(f"Viewer written to {output_path} ({len(html) / 1024:.0f} KB)")


# ── to-xml ───────────────────────────────────────────────────────────────────


@app.command(name="to-xml")
def to_xml(
    entity: Annotated[Path, typer.Option(help="Entity-phase results.json")] = ...,
    medical: Annotated[
        Optional[Path], typer.Option(help="Medical relation results.json")
    ] = None,
    time: Annotated[
        Optional[Path], typer.Option(help="Time relation results.json")
    ] = None,
    output: Annotated[Path, typer.Option("-o", help="Output directory")] = Path("output/xml"),
    corpus: Annotated[bool, typer.Option(help="Also generate a single corpus.xml")] = False,
) -> None:
    """Convert results to per-document PRISM inline XML files."""
    from prism_annotator.merge import merge_relations
    from prism_annotator.models import AnnotatedDocument, load_results
    from prism_annotator.output import document_to_inline_xml

    entity_docs = load_results(entity)
    rel_lists: list[list[AnnotatedDocument]] = []
    if medical:
        rel_lists.append(load_results(medical))
    if time:
        rel_lists.append(load_results(time))

    merged_docs = merge_relations(entity_docs, *rel_lists)
    output.mkdir(parents=True, exist_ok=True)

    corpus_parts: list[str] = []
    for doc in merged_docs:
        xml = document_to_inline_xml(doc)
        (output / f"{doc.doc_id}.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n{xml}\n',
            encoding="utf-8",
        )
        corpus_parts.append(xml)

    typer.echo(f"Wrote {len(merged_docs)} XML files to {output}/")

    if corpus:
        corpus_path = output / "corpus.xml"
        corpus_path.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<corpus>\n'
            + "\n".join(corpus_parts)
            + "\n</corpus>\n",
            encoding="utf-8",
        )
        typer.echo(f"Wrote corpus file: {corpus_path}")


# ── validate ─────────────────────────────────────────────────────────────────


@app.command()
def validate(
    results_json: Annotated[Path, typer.Argument(help="Path to results.json")] = ...,
) -> None:
    """Validate results.json against the PRISM schema."""
    from prism_annotator.models import load_results
    from prism_annotator.postprocess import compute_statistics, validate_results

    if not results_json.exists():
        typer.echo(f"Error: {results_json} not found", err=True)
        raise typer.Exit(1)

    docs = load_results(results_json)
    typer.echo(f"Loaded {len(docs)} documents")

    warnings = validate_results(docs)
    if warnings:
        typer.echo("Validation warnings:")
        for category, count in sorted(warnings.items()):
            typer.echo(f"  {category}: {count}")
    else:
        typer.echo("All entities passed validation.")

    stats = compute_statistics(docs)
    typer.echo(f"\nStatistics: {json.dumps(stats, ensure_ascii=False, indent=2)}")


# ── init ─────────────────────────────────────────────────────────────────────


@app.command()
def init(
    directory: Annotated[str, typer.Argument(help="Project directory to scaffold")] = ".",
    language: Annotated[str, typer.Option(help="Prompt language (ja or en)")] = "ja",
) -> None:
    """Scaffold a new prism-annotator project."""
    from prism_annotator.scaffold import scaffold_project

    project_dir = Path(directory)
    scaffold_project(project_dir, language=language)

    typer.echo(f"Project scaffolded in {project_dir.resolve()}")
    typer.echo()
    typer.echo("Next steps:")
    typer.echo(f"  1. cd {directory}")
    typer.echo("  2. Add your medical texts to data/")
    typer.echo("  3. Add few-shot examples to prompts/*.yaml")
    typer.echo("  4. Set your API key: export OPENROUTER_API_KEY=...")
    typer.echo("  5. Run: prism extract --config config.yaml")
