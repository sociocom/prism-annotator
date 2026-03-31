"""YAML configuration loader."""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any

import yaml


@dataclasses.dataclass
class ModelSettings:
    model_id: str = "anthropic/claude-sonnet-4"
    base_url: str = "https://openrouter.ai/api/v1"
    api_key_env: str = "OPENROUTER_API_KEY"

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise EnvironmentError(
                f"Environment variable {self.api_key_env} is not set"
            )
        return key


@dataclasses.dataclass
class ExtractionSettings:
    temperature: float = 0.0
    timeout_per_doc: int = 120
    max_retries: int = 2


@dataclasses.dataclass
class OutputSettings:
    output_dir: str = "output/runs"


@dataclasses.dataclass
class DataSettings:
    input_path: str = ""
    input_format: str | None = None  # "txt" or "csv"; auto-detect if None
    text_column: str = "text"  # CSV column for document text
    id_column: str | None = None  # CSV column for doc ID (default: row index)
    max_documents: int | None = None


@dataclasses.dataclass
class PromptSettings:
    language: str = "ja"
    prompts_dir: str | None = None  # override: custom prompts directory


@dataclasses.dataclass
class Config:
    experiment_name: str = "prism_v1"
    phase: str = "entity"  # "entity", "medical_relation", or "time_relation"
    data: DataSettings = dataclasses.field(default_factory=DataSettings)
    model: ModelSettings = dataclasses.field(default_factory=ModelSettings)
    extraction: ExtractionSettings = dataclasses.field(
        default_factory=ExtractionSettings
    )
    output: OutputSettings = dataclasses.field(default_factory=OutputSettings)
    prompts: PromptSettings = dataclasses.field(default_factory=PromptSettings)


def load_config(path: str | Path) -> Config:
    """Load configuration from a YAML file."""
    with open(path) as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    cfg = Config()
    cfg.experiment_name = raw.get("experiment_name", cfg.experiment_name)
    cfg.phase = raw.get("phase", cfg.phase)

    if "data" in raw:
        d = raw["data"]
        cfg.data = DataSettings(
            input_path=d.get("input_path", cfg.data.input_path),
            input_format=d.get("input_format"),
            text_column=d.get("text_column", cfg.data.text_column),
            id_column=d.get("id_column"),
            max_documents=d.get("max_documents"),
        )

    if "model" in raw:
        m = raw["model"]
        cfg.model = ModelSettings(
            model_id=m.get("model_id", cfg.model.model_id),
            base_url=m.get("base_url", cfg.model.base_url),
            api_key_env=m.get("api_key_env", cfg.model.api_key_env),
        )

    if "extraction" in raw:
        e = raw["extraction"]
        cfg.extraction = ExtractionSettings(
            temperature=e.get("temperature", cfg.extraction.temperature),
            timeout_per_doc=e.get("timeout_per_doc", cfg.extraction.timeout_per_doc),
            max_retries=e.get("max_retries", cfg.extraction.max_retries),
        )

    if "output" in raw:
        o = raw["output"]
        cfg.output = OutputSettings(
            output_dir=o.get("output_dir", cfg.output.output_dir),
        )

    if "prompts" in raw:
        p = raw["prompts"]
        cfg.prompts = PromptSettings(
            language=p.get("language", cfg.prompts.language),
            prompts_dir=p.get("prompts_dir"),
        )

    return cfg
