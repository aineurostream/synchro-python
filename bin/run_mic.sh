#!/bin/sh

export SERVER="http://127.0.0.1:50080"
export DEVICE_IN=17
export DEVICE_OUT=17

export LANG_FROM="en"
export LANG_TO="ru"
# Английский (en)
# Испанский (es)
# Французский (fr)
# Немецкий (de)
# Итальянский (it)
# Португальский (pt)
# Польский (pl)
# Турецкий (tr)
# Русский (ru)
# Нидерландский (nl)
# Чешский (cs)
# Арабский (ar)
# Китайский, упрощённый (zh-CN)
# Японский (ja)
# Венгерский (hu)
# Корейский (ko)
# Хинди (hi)

uv run python hydra_run.py \
    --config-name config \
    pipeline=mic_en_ru \
    settings.limits.run_time_seconds=0 \
    pipeline.nodes.0.device=${DEVICE_IN} \
    pipeline.nodes.6.device=${DEVICE_OUT} \
    pipeline.nodes.3.server_url=${SERVER} \
    pipeline.nodes.3.lang_from=${LANG_FROM} \
    pipeline.nodes.3.lang_to=${LANG_FROM}