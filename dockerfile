# Use official Python slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    ca-certificates \
    wget \
    build-essential \
    libffi-dev \
    libssl-dev \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libxss1 \
    libxcb1 \
    libxfixes3 \
    libxshmfence1 \
    libdrm2 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install Rust toolchain for pydantic-core
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
# Set CARGO_HOME to a writable directory
ENV CARGO_HOME=/tmp/cargo
RUN mkdir -p /tmp/cargo

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Playwright browsers with dependencies
RUN playwright install --with-deps

# Copy all files, including worker.py from project root
COPY . /app

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "worker:app", "--host", "0.0.0.0", "--port", "8000"]
