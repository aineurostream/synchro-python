INPUT=${1:-samples/turkish_0_3.30.wav}

uv run python ./hydra_run.py \
    --config-name config \
    pipeline=dummy \
    settings.name=turkish \
    settings.limits.run_time_seconds=60 \
    pipeline.nodes.0.path=${INPUT} \
    +pipeline.nodes.0.start=0 \
    +pipeline.nodes.0.duration=5