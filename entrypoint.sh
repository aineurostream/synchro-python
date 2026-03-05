#!/bin/bash

cd /app

exec uv run python hydra_run.py \
  pipeline=default_mic \
  pipeline.nodes.0.device=${INPUT_DEVICE} \
  pipeline.nodes.3.lang_from=${LANG_FROM} \
  pipeline.nodes.3.lang_to=${LANG_TO} \
  pipeline.nodes.3.server_url=${CONVERTER_SERVER} \
  pipeline.nodes.5.device=${OUTPUT_DEVICE} \
  "$@"
