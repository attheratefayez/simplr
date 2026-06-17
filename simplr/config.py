from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "simplr"
CONFIG_PATH = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG: dict[str, Any] = {
    "provider": {
        "name": "ollama",
    },
    "ollama": {
        "model": "qwen2.5-coder:7b",
        "host": "http://localhost:11434",
    },
    "huggingface": {
        "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "quantize": "4bit",
        "device": "auto",
    },
    "huggingface-api": {
        "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
    },
    "inference": {
        "max_new_tokens": 512,
        "temperature": 0.1,
    },
    "cache": {
        "ttl_days": 30,
    },
    "build": {
        "command": "",
    },
}


def load() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG

    with open(CONFIG_PATH, "rb") as f:
        try:
            user_config = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            print(f"warning: invalid config at {CONFIG_PATH}: {e}")
            return DEFAULT_CONFIG

    merged = DEFAULT_CONFIG.copy()
    for section, values in user_config.items():
        if section in merged and isinstance(merged[section], dict):
            merged[section].update(values)
        else:
            merged[section] = values

    return merged


def ensure_default_config() -> None:
    if CONFIG_PATH.exists():
        return
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        f.write(
            f"""# simplr configuration

# Provider: "ollama", "huggingface", or "huggingface-api"
[provider]
name = "{DEFAULT_CONFIG['provider']['name']}"

# Ollama — local LLM via Ollama server
[ollama]
model = "{DEFAULT_CONFIG['ollama']['model']}"
host = "{DEFAULT_CONFIG['ollama']['host']}"

# HuggingFace Transformers — run models locally (requires --extra local)
[huggingface]
model = "{DEFAULT_CONFIG['huggingface']['model']}"
quantize = "{DEFAULT_CONFIG['huggingface']['quantize']}"
device = "{DEFAULT_CONFIG['huggingface']['device']}"

# HuggingFace Inference API — remote inference (uses HF_TOKEN env or configured token)
[huggingface-api]
model = "{DEFAULT_CONFIG['huggingface-api']['model']}"

[inference]
max_new_tokens = {DEFAULT_CONFIG['inference']['max_new_tokens']}
temperature = {DEFAULT_CONFIG['inference']['temperature']}

# Build command for `simplr build` and `--watch`
[build]
command = "{DEFAULT_CONFIG['build']['command']}"

# LLM response cache
[cache]
ttl_days = {DEFAULT_CONFIG['cache']['ttl_days']}
"""
        )
