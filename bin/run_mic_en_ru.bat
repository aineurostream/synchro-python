set SERVER="http://127.0.0.1:50080"

// uv run python -m sounddevice
set DEVICE_IN=0
set DEVICE_OUT=5

uv run python hydra_run.py ^
    --config-name config ^
    pipeline=mic_en_ru ^
    settings.limits.run_time_seconds=0 ^
    pipeline.nodes.0.device=%DEVICE_IN% ^
    pipeline.nodes.6.device=%DEVICE_OUT% ^
    pipeline.nodes.3.server_url=%SERVER%
