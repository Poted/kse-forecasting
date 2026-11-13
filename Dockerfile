# Obraz aplikacji (dashboard + polecenia kse-data / kse-p2). Baza: usługa `db` w docker-compose.yml.
FROM python:3.12-slim

# libgomp1 — wymagane przez LightGBM
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.11.32

WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md .python-version ./
COPY common ./common
COPY p2 ./p2
COPY inz ./inz
COPY app ./app
COPY config ./config
COPY .streamlit ./.streamlit
RUN uv sync --frozen --no-dev

EXPOSE 8501
CMD ["uv", "run", "--no-sync", "kse-app", "--server.port", "8501", "--server.address", "0.0.0.0"]
