"""Scaffold a new prism-annotator project directory."""

from __future__ import annotations

import importlib.resources
import shutil
from pathlib import Path


def scaffold_project(directory: Path, language: str = "ja") -> None:
    """Create a new project directory with config and prompt stubs."""
    directory.mkdir(parents=True, exist_ok=True)

    # Copy config template
    defaults = importlib.resources.files("prism_annotator.defaults")
    config_src = defaults / "config_template.yaml"
    config_dst = directory / "config.yaml"
    if not config_dst.exists():
        config_dst.write_text(
            Path(str(config_src)).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    # Copy language-appropriate prompt files
    prompts_dir = directory / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    pkg_prompts = defaults / "prompts" / language
    if pkg_prompts.is_dir():
        for resource in pkg_prompts.iterdir():
            if resource.is_file():
                dst = prompts_dir / resource.name
                if not dst.exists():
                    dst.write_text(
                        Path(str(resource)).read_text(encoding="utf-8"),
                        encoding="utf-8",
                    )

    # Create data directory
    (directory / "data").mkdir(exist_ok=True)

    # Create .env.example
    env_example = directory / ".env.example"
    if not env_example.exists():
        env_example.write_text(
            "# API key for LLM provider (OpenRouter, OpenAI, etc.)\n"
            "OPENROUTER_API_KEY=\n",
            encoding="utf-8",
        )
