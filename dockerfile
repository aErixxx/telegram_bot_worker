# Use official Python slim image as base
FROM python:3.13-slim

# ติดตั้ง dependencies ที่จำเป็น
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    ca-certificates \
    wget \
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
    libxfixes0 \
    libxshmfence1 \
    libdrm2 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# ติดตั้ง Rust toolchain (required สำหรับ build pydantic-core)
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# ติดตั้ง Playwright dependencies และติดตั้ง browser
RUN pip install --upgrade pip setuptools wheel
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
RUN playwright install

# Copy source code
WORKDIR /app
COPY . /app

# เปิดพอร์ตที่แอปใช้งาน
EXPOSE 8000

# คำสั่งรันแอป (ปรับตามของคุณ)
CMD ["uvicorn", "worker:app", "--host", "0.0.0.0", "--port", "8000"]
