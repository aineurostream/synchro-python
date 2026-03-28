# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Synchro is a real-time speech-to-speech translation application. It captures audio, sends it to a remote server for transcription/translation/synthesis, and plays back the translated audio. The project has two main packages:

- **`synchro`** — The core audio processing pipeline (graph-based architecture)
- **`synchroagent`** — A FastAPI management server for running and monitoring Synchro instances

## Workflow Rules

- After any code change, run `pre-commit run --all-files` to lint and format. Do not run ruff, mypy, or other formatters/linters directly.
- Always run `python -m pytest ./pytests` after changes to verify nothing is broken.

## Common Commands

```bash
# Setup
pip install uv
uv venv && uv pip install -e .

# Run pipeline (Hydra mode, from file)
python hydra_run.py --config-name config

# Run pipeline (microphone mode) — see bin/ for ready-made scripts
python hydra_run.py --config-name config pipeline=default_mic ...

# Run agent management server
uv run python -m synchroagent.main

# Run CLI
python run.py

# Tests
python -m pytest ./pytests              # all tests
python -m pytest ./pytests/test_foo.py  # single file
python -m pytest -k "test_name"         # single test by name

# Lint (pre-commit: ruff + mypy + absolufy-imports)
pre-commit run --all-files
```

## Architecture

### Processing Graph (`synchro/`)

The core is a directed graph where each node runs in its own thread. Data flows between nodes via thread-safe queues.

**Key abstractions:**
- `GraphNode` — base class; uses context manager protocol (`__enter__`/`__exit__`) for resource lifecycle
- `EmittingNodeMixin` — node produces `FrameContainer` data via `get_data()`
- `ReceivingNodeMixin` — node consumes `FrameContainer` data via `put_data()`
- `GraphEdge` — named connection between two nodes (source → target)
- `GraphManager` — builds edge queues, starts a `NodeExecutor` thread per node, handles shutdown and exception propagation
- `GraphInitializer` — maps Pydantic config schemas to concrete node instances via `BUILD_METHODS` dispatch table

**Node types** (in `synchro/graph/nodes/`):
- `inputs/` — audio sources (microphone channel, WAV file)
- `outputs/` — audio sinks (speaker channel, WAV file, terminal metrics TUI)
- `processors/` — in-pipeline transforms (mixer, resampler, VAD, normalizer, denoiser, format validator, whisper prep)
- `models/` — `SeamlessConnectorNode` connects to a remote Socket.IO server for transcription + translation + synthesis

**Configuration:**
- Pipeline topology is defined in Hydra YAML configs under `config/pipeline/` (lists of typed nodes + edges)
- Node schemas in `synchro/config/schemas.py` use Pydantic discriminated unions (`node_type` field)
- AI/neuro config (`config/ai/`) supports `file://` paths for prompt templates — resolved at runtime by `CoreManager.preprocess_neuro_config()`
- Settings (`config/settings/`) control timing intervals and quality metrics
- Hydra entry point: `hydra_run.py`; CLI entry point: `run.py` (Click-based)

### Agent Server (`synchroagent/`)

FastAPI app that manages multiple Synchro pipeline instances:
- **API routes** (`api/`): `/api/clients`, `/api/configs`, `/api/events`
- **Business logic** (`logic/`): process management, log collection, report generation, event bus
- **Database** (`database/`): SQLite with WAL mode; tables for clients, configs, runs, reports, logs
- **Config**: env vars prefixed `AGNT_` or `.env` file (see `synchroagent/config.py`)

## Tech Stack

- Python 3.13, managed with `uv`
- Pydantic v2 for all config/schema validation
- Hydra for experiment configuration and sweeps
- Socket.IO client for real-time server communication
- FastAPI + Uvicorn for the agent server
- SQLite for agent persistence
- pytest (asyncio_mode=strict) for testing
- Linting: ruff (format + lint, ALL rules enabled except `D`), mypy, absolufy-imports
- Pre-commit hooks enforced

## Code Conventions

- All imports must be absolute (enforced by absolufy-imports)
- ruff `ALL` rules enabled with docstring rules (`D`) disabled; test files additionally ignore `S101`, `ANN`, `ARG`, `PTH`, `PLR2004`
- Comments in the codebase are sometimes in Russian
