#!/bin/sh

SERVER="http://127.0.0.1:50080" \
DEVICE_IN=0 \
DEVICE_OUT=1 \
uv run python hydra_run.py \
    --config-name config \
    pipeline=mic_ru_en \
    settings.limits.run_time_seconds=0 \
    pipeline.nodes.0.device=$DEVICE_IN \
    pipeline.nodes.6.device=$DEVICE_OUT \
    pipeline.nodes.3.server_url=$SERVER
