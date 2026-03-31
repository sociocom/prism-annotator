"""Load input data into AnnotatedDocument objects.

Supported formats:
- txt: one file per document, or a directory of .txt files
- csv: one row per document, with configurable column names
"""

from __future__ import annotations

import csv
from pathlib import Path

from prism_annotator.config import DataSettings
from prism_annotator.models import AnnotatedDocument


def _detect_format(path: Path) -> str:
    """Auto-detect input format from file extension or directory."""
    if path.is_dir():
        return "txt"
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".txt":
        return "txt"
    raise ValueError(
        f"Cannot auto-detect format for '{path}'. "
        "Set input_format explicitly in config (txt or csv)."
    )


def _load_txt(path: Path) -> list[AnnotatedDocument]:
    """Load plain text files as documents."""
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return []
        return [AnnotatedDocument(doc_id=path.stem, text=text)]

    # Directory: each .txt file is a document
    documents: list[AnnotatedDocument] = []
    for txt_path in sorted(path.glob("*.txt")):
        text = txt_path.read_text(encoding="utf-8").strip()
        if text:
            documents.append(AnnotatedDocument(doc_id=txt_path.stem, text=text))
    return documents


def _load_csv(path: Path, settings: DataSettings) -> list[AnnotatedDocument]:
    """Load CSV file: one row per document."""
    documents: list[AnnotatedDocument] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            text = row.get(settings.text_column, "").strip()
            if not text:
                continue
            if settings.id_column and settings.id_column in row:
                doc_id = row[settings.id_column]
            else:
                doc_id = str(i)
            documents.append(AnnotatedDocument(doc_id=doc_id, text=text))
    return documents


def load_documents(settings: DataSettings) -> list[AnnotatedDocument]:
    """Load documents from the configured input path."""
    path = Path(settings.input_path)
    fmt = settings.input_format or _detect_format(path)

    match fmt:
        case "txt":
            documents = _load_txt(path)
        case "csv":
            documents = _load_csv(path, settings)
        case _:
            raise ValueError(f"Unsupported input format: {fmt}")

    if settings.max_documents is not None:
        documents = documents[: settings.max_documents]

    return documents
