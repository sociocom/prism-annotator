"""Load system prompts and few-shot examples from files.

Fallback chain for each prompt file:
1. User-specified path in config (prompts_dir)
2. prompts/ directory in working directory
3. Built-in package defaults (via importlib.resources)
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import yaml

from prism_annotator.config import PromptSettings

# ── Phase-to-filename mapping ────────────────────────────────────────────────

_SYSTEM_PROMPT_FILES = {
    "entity": "entity_system.md",
    "medical_relation": "medical_relation_system.md",
    "time_relation": "time_relation_system.md",
}

_EXAMPLE_FILES = {
    "entity": "entity_examples.yaml",
    "medical_relation": "medical_relation_examples.yaml",
    "time_relation": "time_relation_examples.yaml",
}


def _resolve_prompt_file(
    filename: str, prompt_cfg: PromptSettings,
) -> Path | None:
    """Find a prompt file using the fallback chain."""
    # 1. User-specified prompts_dir
    if prompt_cfg.prompts_dir:
        user_path = Path(prompt_cfg.prompts_dir) / filename
        if user_path.exists():
            return user_path

    # 2. prompts/ in working directory
    local_path = Path("prompts") / filename
    if local_path.exists():
        return local_path

    # 3. Built-in defaults
    lang = prompt_cfg.language
    pkg_files = importlib.resources.files("prism_annotator.defaults.prompts") / lang
    resource = pkg_files / filename
    if resource.is_file():
        return Path(str(resource))

    return None


def load_system_prompt(phase: str, prompt_cfg: PromptSettings) -> str:
    """Load the system prompt for the given phase."""
    filename = _SYSTEM_PROMPT_FILES.get(phase)
    if filename is None:
        raise ValueError(f"Unknown phase: {phase}")

    path = _resolve_prompt_file(filename, prompt_cfg)
    if path is None:
        raise FileNotFoundError(
            f"System prompt not found for phase={phase}, "
            f"language={prompt_cfg.language}. "
            f"Looked for: {filename}"
        )
    return path.read_text(encoding="utf-8").strip()


def load_few_shot_examples(phase: str, prompt_cfg: PromptSettings) -> list[dict]:
    """Load few-shot examples as [{input, output}] from YAML."""
    filename = _EXAMPLE_FILES.get(phase)
    if filename is None:
        raise ValueError(f"Unknown phase: {phase}")

    path = _resolve_prompt_file(filename, prompt_cfg)
    if path is None:
        return []

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw or not isinstance(raw, list):
        return []
    return raw


def build_few_shot_messages(
    phase: str, prompt_cfg: PromptSettings,
) -> list[dict[str, str]]:
    """Build user/assistant message pairs from few-shot examples."""
    examples = load_few_shot_examples(phase, prompt_cfg)
    messages: list[dict[str, str]] = []
    for ex in examples:
        messages.append({"role": "user", "content": ex["input"]})
        messages.append({"role": "assistant", "content": ex["output"]})
    return messages


# ── Backward-compatible constants ────────────────────────────────────────────
# pipeline.py still imports these; they load the Japanese defaults.

_DEFAULT_CFG = PromptSettings(language="ja")

ENTITY_SYSTEM_PROMPT = load_system_prompt("entity", _DEFAULT_CFG)


def build_entity_few_shot_messages() -> list[dict[str, str]]:
    """Return entity extraction few-shot examples as message pairs."""
    return build_few_shot_messages("entity", _DEFAULT_CFG)
