# ---- Stage 1: Builder ----
FROM python:3.13.3-slim as builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

ENV CARGO_HOME="/app/.cargo"
RUN mkdir -p $CARGO_HOME

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ติดตั้งแค่ chromium พร้อม dependencies
RUN playwright install chromium --with-deps && \
    echo "--- Playwright chromium install verification ---" && \
    ls -lR /root/.cache/ms-playwright/ || true && \
    echo "--- End verification ---"

# ---- Stage 2: Final Production Image ----
FROM python:3.13.3-slim

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fonts-liberation libnss3 libnspr4 libdbus-1-3 \
    libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcups2 libdrm2 libgbm1 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxshmfence1 libasound2 \
    libpangocairo-1.0-0 libpango-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

RUN mkdir -p /opt/render/.cache/ms-playwright
COPY --from=builder /root/.cache/ms-playwright /opt/render/.cache/ms-playwright
RUN chmod -R +x /opt/render/.cache/ms-playwright

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/render/.cache/ms-playwright

COPY . .

RUN chown -R appuser:appuser /app /opt/render/.cache
USER appuser

EXPOSE 8000

CMD ["uvicorn", "worker:app", "--host", "0.0.0.0", "--port", "8000"]
