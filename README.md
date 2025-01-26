# REPO: Synchro_python

## Local application Speech-to-Speech

Application for **real-time** translation.

## Prerequisites
- Python 3.11
- poetry
- pyaudio (based on portaudio)

## TODOs:
- Separate node for VAD
- Separate node for buffers
- Support dynamic node management

## Step 1. Setup
```bash
pip3 install poetry
poetry install
```
Poetry will install all dependencies from `pyproject.toml`.

### Step 2. Get devices info
```bash
poetry run python3 -m sounddevice
```
Devices with `out` channels can be used in `input_channel` node type.
Devices with `in` channels can be used in `output_channel` node type.

## How to use
### Step 3.A Start application
```bash
poetry run python run.py instance start -p ./samples/config_leo_file.json -n ./samples/ai_config.json
```
This will start an application using the provided pipeline and neural networks configuration files.

### Step 3.B Start application in HYDRA mode
```bash
poetry run python hydra_run.py
```
In that case all configs are taken from the HYDRA's `config` folder. See [HYDRA](https://hydra.cc)
documentation for launch options.

You can try multirun on many threads for grid search:
```bash
poetry run python hydra_run.py --multirun --config-name optuna_01
```

## How to test
```bash
poetry run pytest ./pytests
```

## How to lint
```bash
pre-commit run --all-files
```

Used linters:
- ruff - formatting and most of the static checking
- mypy - static type checking