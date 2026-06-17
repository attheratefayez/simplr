# simplr

CMake build log error explainer using local LLMs.

Pipe your build log in, get a plain-English explanation of the first error
and how to fix it.

```bash
cmake --build build 2>&1 | simplr
simplr < build.log
```

## Features

- **First-error focus** — explains the root cause, lists other unrelated errors
- **System header filtering** — skips template noise from `/usr/include/...`
- **Warning explainer** — `--warnings` flag to also explain compiler warnings
- **LLM response cache** — caches explanations to avoid re-querying (configurable TTL)
- **Error stats** — tracks errors over time via `simplr stats`
- **Build wrapper** — `simplr build` runs cmake and pipes through simplr
- **Exec wrapper** — `simplr exec -- <command>` runs any command and pipes through simplr
- **Watch mode** — `--watch` auto-rebuilds on source file changes
- **Linker error parsing** — parses `undefined reference`, `collect2`, and linker detail errors

## Providers

| Provider | Config value | Setup |
|---|---|---|
| **Ollama** (default) | `ollama` | `ollama pull qwen2.5-coder:7b` |
| **HuggingFace API** | `huggingface-api` | Set `HF_TOKEN` env var |
| **HF Transformers** (local) | `huggingface` | `uv sync --extra local --extra gpu` |

## CLI

### Pipe mode (default)

```bash
cmake --build build 2>&1 | simplr
simplr < build.log

simplr --model qwen2.5-coder:7b < build.log
simplr --warnings < build.log          # also explain warnings
simplr --no-cache < build.log          # bypass cache
```

### Build wrapper

```bash
simplr build                           # uses [build] command from config
simplr build -C out                    # override build directory
simplr build -- -j8                    # pass extra cmake args
simplr build --warnings                # with warning explanations
```

Set up the build command in config:

```toml
[build]
command = "cmake --build build"
```

### Exec wrapper

```bash
simplr exec -- make -j4
simplr exec -- cargo build
simplr exec --no-cache -- ninja
```

### Stats

```bash
simplr stats                           # show top errors, errors by file, today's count
```

### Watch mode

```bash
simplr --watch < build.log             # re-run analysis on file changes
simplr build --watch                   # rebuild + re-analyze on changes
```

Requires: `uv sync --extra watch` (installs watchdog).

## Configuration

Config file at `~/.config/simplr/config.toml` — created automatically on first run.

### Ollama (default)

```toml
[provider]
name = "ollama"

[ollama]
model = "qwen2.5-coder:7b"
host = "http://localhost:11434"
```

Requires: `ollama pull qwen2.5-coder:7b` and `ollama serve` running.

### HuggingFace Transformers (local)

```toml
[provider]
name = "huggingface"

[huggingface]
model = "Qwen/Qwen2.5-Coder-7B-Instruct"
quantize = "4bit"
device = "auto"
```

Install deps: `uv sync --extra local --extra gpu` (PyTorch, transformers, accelerate, bitsandbytes).

### HuggingFace Inference API (remote)

```toml
[provider]
name = "huggingface-api"

[huggingface-api]
model = "Qwen/Qwen2.5-Coder-7B-Instruct"
```

Requires: `HF_TOKEN` environment variable (or `.env` file with `HF_TOKEN=...`). No extra deps.

### Build command

```toml
[build]
command = "cmake --build build"
```

Used by `simplr build` and `--watch`. If empty, these commands prompt you to set it.

### Cache

```toml
[cache]
ttl_days = 30
```

LLM responses are cached to avoid re-querying the same error. Set `ttl_days = 0` to disable.

## Example

```bash
g++ -std=c++17 examples/broken.cpp -o /dev/null 2>&1 | simplr --warnings
```

This produces:

```
  Analyzing...
╭─ Error (compiler) in examples/broken.cpp:18 ────────────────────────╮
│                                                                     │
│  The error "taking address of rvalue" occurs because ...            │
│                                                                     │
╰─────────────────────────────────────────────────────────────────────╯

Other unrelated errors:
  [compiler] examples/broken.cpp:49: cannot convert 'int*' to 'char*'
  [compiler] examples/broken.cpp:56: 'sort' is not a member of 'std'

  Explaining first warning...
╭─ Warning in examples/broken.cpp:27 ─────────────────────────────────╮
│                                                                     │
│  The warning "reference to local variable returned" occurs when...  │
│                                                                     │
╰─────────────────────────────────────────────────────────────────────╯
```
