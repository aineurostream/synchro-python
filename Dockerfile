FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libasound2-dev \
    portaudio19-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN pip install uv && \
    uv sync --frozen

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV LANG_FROM=en
ENV LANG_TO=ru
ENV INPUT_DEVICE=0
ENV OUTPUT_DEVICE=1
ENV CONVERTER_SERVER=http://127.0.0.1:8000

ENTRYPOINT ["/entrypoint.sh"]
