# simplr

CMake build log error explainer using local LLMs.

Pipe your build log in, get a plain-English explanation of the first error
and how to fix it.

```bash
cmake --build build 2>&1 | simplr
simplr < build.log
```

## Providers

| Provider | Config value | Setup |
|---|---|---|
| **Ollama** (default) | `ollama` | `ollama pull qwen2.5-coder:7b` |
| **HuggingFace API** | `huggingface-api` | Set `HF_TOKEN` env var |
| **HF Transformers** (local) | `huggingface` | `uv sync --extra local --extra gpu` |

## Configuration

```toml
# ~/.config/simplr/config.toml
[provider]
name = "ollama"

[ollama]
model = "qwen2.5-coder:7b"
host = "http://localhost:11434"
```

Create it automatically on first run, or manually.

## CLI

```bash
simplr --model qwen2.5-coder:7b < build.log
```
