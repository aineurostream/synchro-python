set SERVER="http://127.0.0.1:50080"

uv run python ./hydra_run.py ^
    --config-name config ^
    pipeline=sample_en ^
    settings.name=turkish ^
    pipeline.nodes.0.path=samples\turkish_0_3.30.wav ^
    pipeline.nodes.3.server_url=%SERVER% ^
    settings.limits.run_time_seconds=200 ^
    settings.metrics.quality.0.expected_transcription='${file:samples\turkish_0_3.30.txt}' ^
    settings.metrics.quality.0.expected_translation='${file:samples\turkish_0_3.30_translated.txt}'
