# ---- Stage 1: Builder ----
# This stage installs all dependencies and builds the application environment.
FROM python:3.13.3-slim as builder

# Set the working directory
WORKDIR /app

# 1. Install system dependencies and Rust in a single layer
# This includes build-essential for compiling code and curl for downloading Rust.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. Install the Rust toolchain for pydantic-core compilation
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
# Add the cargo bin directory to the PATH for subsequent commands
ENV PATH="/root/.cargo/bin:${PATH}"

# 3. Set CARGO_HOME to a local, writable directory to avoid filesystem errors
# This ensures Rust packages are cached within our app directory.
ENV CARGO_HOME="/app/.cargo"
RUN mkdir -p $CARGO_HOME

# 4. Copy and install Python requirements first to leverage Docker layer caching
# This step will build and install pydantic, playwright, and other dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Install Playwright browsers and their OS-level dependencies
# The '--with-deps' flag conveniently handles all necessary system packages.
RUN playwright install --with-deps

# ---- Stage 2: Final Production Image ----
# This stage creates a lean final image with only the necessary runtime files.
FROM python:3.13.3-slim

# Set the working directory
WORKDIR /app

# 1. Create a non-root user for enhanced security
RUN useradd --create-home --shell /bin/bash appuser

# 2. Install only the RUNTIME dependencies for Playwright browsers
# We copy the already installed system dependencies from the builder stage
# which is more efficient than reinstalling them.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fonts-liberation libnss3 libnspr4 libdbus-1-3 \
    libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcups2 libdrm2 libgbm1 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxshmfence1 libasound2 \
    libpangocairo-1.0-0 libpango-1.0-0 && \
    rm -rf /var/lib/apt/lists/*

# 3. Copy installed Python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# 4. Copy installed Playwright browser binaries from the builder stage
COPY --from=builder /root/.cache/ms-playwright /home/appuser/.cache/ms-playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

# 5. Copy your application code
COPY . .

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appuser /app /home/appuser/.cache

# Switch to the non-root user
USER appuser

# Expose the port the application will run on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "worker:app", "--host", "0.0.0.0", "--port", "8000"]
