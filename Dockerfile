FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV SCRATCH_DIR=/tmp/shotlist

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/cache/huggingface \
    OUTPUT_DIR=/app/output

COPY pyproject.toml README.md ./
COPY shotlist ./shotlist

RUN pip install --upgrade pip \
    && pip install .

RUN mkdir -p /app/output

CMD ["python", "-m", "shotlist", "serve"]
