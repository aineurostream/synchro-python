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

## How to setup
```bash
pip3 install poetry
poetry install
```
Poetry will install all dependencies from `pyproject.toml`.

## How to use
### Start application
```bash
poetry run python run.py instance start -i 0 0 ru -i 0 1 en -o 1 0 en -o 1 1 ru
```
This will start an application with 2 input and 2 output devices.

### Get devices info
```bash
poetry run python run.py info devices
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