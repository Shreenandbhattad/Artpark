FROM python:3.11-slim AS builder
WORKDIR /build
COPY app/requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS runtime
ARG IMAGE_TAG=dev
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV IMAGE_TAG=${IMAGE_TAG}

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY app/ .
COPY data/ /data/

ENV DATA_ROOT=/data
ENV DOMAIN=environment
ENV PROVIDER=mock
ENV LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
