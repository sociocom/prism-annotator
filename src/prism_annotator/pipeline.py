"""TANL extraction pipeline: entity and relation extraction orchestration."""

from __future__ import annotations

import logging
from pathlib import Path

from openai import OpenAI

from prism_annotator.config import Config
from prism_annotator.models import AnnotatedDocument, append_result, load_results_ndjson
from prism_annotator.prompts import (
    build_few_shot_messages,
    load_system_prompt,
)
from prism_annotator.relations import parse_relations
from prism_annotator.tanl_format import document_to_tanl
from prism_annotator.tanl_parser import parse_tanl_entities

logger = logging.getLogger("prism_annotator.pipeline")


def _create_client(cfg: Config) -> OpenAI:
    return OpenAI(api_key=cfg.model.api_key, base_url=cfg.model.base_url)


def load_completed_ids(ndjson_path: Path) -> set[str]:
    """Return set of doc_ids already written to the incremental NDJSON file."""
    if not ndjson_path.exists():
        return set()
    return {doc.doc_id for doc in load_results_ndjson(ndjson_path)}


# ── Entity extraction ───────────────────────────────────────────────────────


def _extract_entities_single(
    doc_id: str,
    text: str,
    client: OpenAI,
    cfg: Config,
    system_prompt: str,
    few_shot: list[dict[str, str]],
    raw_dir: Path,
) -> tuple[AnnotatedDocument, list[str]]:
    """Run TANL entity extraction for one document."""
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(few_shot)
    messages.append({"role": "user", "content": text})

    response = client.chat.completions.create(
        model=cfg.model.model_id,
        messages=messages,
        temperature=cfg.extraction.temperature,
        timeout=cfg.extraction.timeout_per_doc,
    )
    raw_output = response.choices[0].message.content or ""

    # Save raw output
    raw_path = raw_dir / f"{doc_id}.txt"
    raw_path.write_text(raw_output, encoding="utf-8")

    entities, warnings = parse_tanl_entities(raw_output, text)

    return AnnotatedDocument(
        doc_id=doc_id,
        text=text,
        entities=entities,
        raw_output=raw_output,
    ), warnings


def reparse_tanl_entities(
    run_dir: Path,
    original_texts: dict[str, str],
) -> list[AnnotatedDocument]:
    """Re-parse raw LLM outputs from a previous entity extraction run."""
    raw_dir = run_dir / "raw"
    if not raw_dir.exists():
        raise FileNotFoundError(f"No raw/ directory in {run_dir}")

    results: list[AnnotatedDocument] = []
    raw_files = sorted(raw_dir.glob("*.txt"))
    total = len(raw_files)

    for i, raw_path in enumerate(raw_files):
        doc_id = raw_path.stem
        doc_label = f"[{i + 1}/{total}] {doc_id}"

        original_text = original_texts.get(doc_id)
        if original_text is None:
            logger.warning("%s: no original text found — skipping", doc_label)
            continue

        raw_output = raw_path.read_text(encoding="utf-8")
        entities, warnings = parse_tanl_entities(raw_output, original_text)

        for w in warnings:
            logger.warning("%s: %s", doc_label, w)
        logger.info(
            "%s: %d entities re-parsed (%d warnings)",
            doc_label, len(entities), len(warnings),
        )

        results.append(AnnotatedDocument(
            doc_id=doc_id,
            text=original_text,
            entities=entities,
            raw_output=raw_output,
        ))

    logger.info("Re-parse complete: %d documents", len(results))
    return results


def reparse_tanl_relations(
    run_dir: Path,
    entity_docs: list[AnnotatedDocument],
    phase: str,
) -> list[AnnotatedDocument]:
    """Re-parse raw LLM outputs from a previous relation extraction run."""
    raw_dir = run_dir / "raw"
    if not raw_dir.exists():
        raise FileNotFoundError(f"No raw/ directory in {run_dir}")

    entity_by_id = {doc.doc_id: doc for doc in entity_docs}

    results: list[AnnotatedDocument] = []
    raw_files = sorted(raw_dir.glob("*.txt"))
    total = len(raw_files)

    for i, raw_path in enumerate(raw_files):
        doc_id = raw_path.stem
        doc_label = f"[{i + 1}/{total}] {doc_id}"

        edoc = entity_by_id.get(doc_id)
        if edoc is None:
            logger.warning("%s: no entity document found — skipping", doc_label)
            continue

        raw_output = raw_path.read_text(encoding="utf-8")

        # Build validation context from entity doc
        eid_to_index = {f"e{j + 1}": j for j in range(len(edoc.entities))}
        valid_eids = set(eid_to_index.keys())
        entity_labels = {eid: edoc.entities[idx].label for eid, idx in eid_to_index.items()}

        relations, warnings = parse_relations(raw_output, valid_eids, phase, entity_labels)
        for w in warnings:
            logger.warning("%s: %s", doc_label, w)
        logger.info(
            "%s: %d relations re-parsed (%d warnings)",
            doc_label, len(relations), len(warnings),
        )

        results.append(AnnotatedDocument(
            doc_id=doc_id,
            text=edoc.text,
            entities=list(edoc.entities),
            relations=relations,
            raw_output=raw_output,
        ))

    logger.info("Re-parse complete: %d documents", len(results))
    return results


def run_tanl_entity_extraction(
    documents: list,
    cfg: Config,
    output_dir: Path,
) -> list[AnnotatedDocument]:
    """Run TANL entity extraction for all documents."""
    client = _create_client(cfg)
    system_prompt = load_system_prompt("entity", cfg.prompts)
    few_shot = build_few_shot_messages("entity", cfg.prompts)

    ndjson_path = output_dir / "results.ndjson"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    completed = load_completed_ids(ndjson_path)
    if completed:
        logger.info("Resuming: %d documents already completed", len(completed))

    results: list[AnnotatedDocument] = []
    total = len(documents)

    for i, doc in enumerate(documents):
        doc_id = doc.doc_id
        doc_label = f"[{i + 1}/{total}] {doc_id}"

        if doc_id in completed:
            logger.info("%s skipped (already completed)", doc_label)
            continue

        logger.info("%s (%d chars)", doc_label, len(doc.text))

        max_attempts = 1 + cfg.extraction.max_retries
        result = None
        for attempt in range(max_attempts):
            try:
                result, warnings = _extract_entities_single(
                    doc_id, doc.text, client, cfg,
                    system_prompt, few_shot, raw_dir,
                )
                for w in warnings:
                    logger.warning("%s: %s", doc_label, w)
                logger.info(
                    "%s: %d entities extracted (%d warnings)",
                    doc_label, len(result.entities), len(warnings),
                )
                break
            except Exception as e:
                logger.error(
                    "%s attempt %d/%d failed: %s",
                    doc_label, attempt + 1, max_attempts, e,
                )
                if attempt < max_attempts - 1:
                    logger.info("%s retrying", doc_label)

        if result is not None:
            results.append(result)
            append_result(result, ndjson_path)
        else:
            logger.error("%s all attempts failed — skipping", doc_label)

    logger.info("Entity extraction complete: %d/%d documents", len(results), total)
    return results


# ── Relation extraction ─────────────────────────────────────────────────────


def _extract_relations_single(
    doc: AnnotatedDocument,
    client: OpenAI,
    cfg: Config,
    phase: str,
    system_prompt: str,
    few_shot: list[dict[str, str]],
    raw_dir: Path,
) -> AnnotatedDocument:
    """Run TANL relation extraction for one document."""
    tanl_text, eid_to_index = document_to_tanl(doc)

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(few_shot)
    messages.append({"role": "user", "content": tanl_text})

    logger.debug("TANL input for %s (%d chars):\n%s", doc.doc_id, len(tanl_text), tanl_text)

    response = client.chat.completions.create(
        model=cfg.model.model_id,
        messages=messages,
        temperature=cfg.extraction.temperature,
        timeout=cfg.extraction.timeout_per_doc,
    )
    raw_output = response.choices[0].message.content or ""

    raw_path = raw_dir / f"{doc.doc_id}.txt"
    raw_path.write_text(raw_output, encoding="utf-8")

    logger.debug("Raw output for %s:\n%s", doc.doc_id, raw_output)

    valid_eids = set(eid_to_index.keys())
    entity_labels = {
        eid: doc.entities[idx].label
        for eid, idx in eid_to_index.items()
    }

    relations, warnings = parse_relations(raw_output, valid_eids, phase, entity_labels)
    for w in warnings:
        logger.warning("%s: %s", doc.doc_id, w)

    # Build result: same entities, with relations attached
    result = AnnotatedDocument(
        doc_id=doc.doc_id,
        text=doc.text,
        entities=doc.entities,
        relations=relations,
        raw_output=raw_output,
    )
    logger.info(
        "%s: %d relations parsed (%d warnings)",
        doc.doc_id, len(relations), len(warnings),
    )
    return result


def run_tanl_extraction(
    entity_results: list[AnnotatedDocument],
    cfg: Config,
    output_dir: Path,
    phase: str,
) -> list[AnnotatedDocument]:
    """Run TANL relation extraction for all documents."""
    client = _create_client(cfg)
    system_prompt = load_system_prompt(phase, cfg.prompts)
    few_shot = build_few_shot_messages(phase, cfg.prompts)

    ndjson_path = output_dir / "results.ndjson"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    completed = load_completed_ids(ndjson_path)
    if completed:
        logger.info("Resuming: %d documents already completed", len(completed))

    results: list[AnnotatedDocument] = []
    total = len(entity_results)

    for i, doc in enumerate(entity_results):
        doc_label = f"[{i + 1}/{total}] {doc.doc_id}"

        if doc.doc_id in completed:
            logger.info("%s skipped (already completed)", doc_label)
            continue

        logger.info("%s (%d entities)", doc_label, len(doc.entities))

        max_attempts = 1 + cfg.extraction.max_retries
        result = None
        for attempt in range(max_attempts):
            try:
                result = _extract_relations_single(
                    doc, client, cfg, phase, system_prompt, few_shot, raw_dir,
                )
                break
            except Exception as e:
                logger.error(
                    "%s attempt %d/%d failed: %s",
                    doc_label, attempt + 1, max_attempts, e,
                )
                if attempt < max_attempts - 1:
                    logger.info("%s retrying", doc_label)

        if result is not None:
            results.append(result)
            append_result(result, ndjson_path)
        else:
            logger.error("%s all attempts failed — skipping", doc_label)

    logger.info("Extraction complete: %d/%d documents", len(results), total)
    return results
