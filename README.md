# REPO: Synchro_python

## Local application Speech-to-Speech

Application for **real-time** translation.

## Prerequisites

- Python 3.13
- uv
- pyaudio (based on portaudio)

## Step 1. Setup

```bash
pip install uv
uv venv
uv pip install -e .
```

UV will install all dependencies from `pyproject.toml`.

### Environment Variables and Configuration

The application supports configuration through environment variables. You can set these variables directly in your environment or use a `.env` file.

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit the `.env` file to customize your configuration:

```
# Database configuration
AGNT_DB_PATH=synchroagent.db

# Directory configurations
AGNT_REPORTS_DIR=reports
AGNT_OUTPUTS_DIR=outputs

# Script paths
AGNT_HYDRA_SCRIPT=hydra_run.py
AGNT_SYNCHRO_REPORT_SCRIPT=../synchro_reporter.git/report.py
```

### Step 2. Get devices info

```bash
python -m sounddevice
```

Devices with `out` channels can be used in `input_channel` node type.
Devices with `in` channels can be used in `output_channel` node type.

## How to use

### Step 3.A Start application

```bash
python run.py instance start -p ./samples/config_leo_file.json -n ./samples/ai_config.json
```

This will start an application using the provided pipeline and neural networks configuration files.

### Step 3.B Start application in HYDRA mode

```bash
python hydra_run.py
```

In that case all configs are taken from the HYDRA's `config` folder. See [HYDRA](https://hydra.cc)
documentation for launch options.

You can try multirun on many threads for grid search:

```bash
python hydra_run.py --multirun --config-name optuna_01
```

You can try run using microphone with russian-to-english translation:

```bash
python hydra_run.py --config-name mic_01
```

## Docker Usage

### Build Docker Image

```bash
docker build -t synchro-client .
```

### Run with Default Settings

```bash
docker run --device /dev/snd synchro-client
```

**Note**: The `--device /dev/snd` flag is required to give the container access to the host's audio devices.

### Run with Custom Configuration

```bash
docker run --device /dev/snd \
  -e LANG_FROM=ru \
  -e LANG_TO=en \
  -e INPUT_DEVICE=1 \
  -e OUTPUT_DEVICE=2 \
  -e CONVERTER_SERVER=http://my-server:8000 \
  synchro-client
```

### Additional Hydra Arguments

You can pass additional Hydra configuration overrides as arguments:

```bash
docker run --device /dev/snd synchro-client \
  hydra.run.dir=/app/custom_output \
  hydra.job.name=my_translation_job
```

## How to test

```bash
python -m pytest ./pytests
```

## How to lint

```bash
pre-commit run --all-files
```

Used linters:

- ruff - formatting and most of the static checking
- mypy - static type checking
