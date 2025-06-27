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
    # Add other common build dependencies if needed, e.g., git
    # git \
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
# Add a verification step immediately after installation.
RUN playwright install --with-deps && \
    echo "--- Playwright install verification in Builder stage ---" && \
    ls -lR /root/.cache/ms-playwright/ || true && \
    echo "--- End Playwright install verification ---"

# ---- Stage 2: Final Production Image ----
# This stage creates a lean final image with only the necessary runtime files.
FROM python:3.13.3-slim

# Set the working directory
WORKDIR /app

# 1. Create a non-root user for enhanced security
RUN useradd --create-home --shell /bin/bash appuser

# 2. Install only the RUNTIME dependencies for Playwright browsers
# These are needed for the browser executables to run correctly.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fonts-liberation libnss3 libnspr4 libdbus-1-3 \
    libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcups2 libdrm2 libgbm1 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxshmfence1 libasound2 \
    libpangocairo-1.0-0 libpango-1.0-0 \
    # Ensure all necessary runtime dependencies are here. Consider adding libstdc++6 if not present.
    # libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# 3. Copy installed Python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# 4. **FIX:** Create the directory structure Render expects and copy Playwright browsers there.
# We'll be more cautious about the source path and ensure permissions.
RUN mkdir -p /opt/render/.cache/ms-playwright

# Copy the entire ms-playwright directory. The *exact* path within this directory
# (e.g., chromium-1179) is handled by Playwright internally if the base path is correct.
COPY --from=builder /root/.cache/ms-playwright /opt/render/.cache/ms-playwright

# Set permissions for the copied browsers
RUN chmod -R +x /opt/render/.cache/ms-playwright

# 5. Point the environment variable to the correct path used by Render.
# This ENV must be set for Playwright to look in the right place.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/render/.cache/ms-playwright

# 6. Copy your application code
COPY . .

# 7. Change ownership of all necessary directories to the non-root user.
# This includes the app code and the new cache directory, ensuring appuser can read/execute everything.
RUN chown -R appuser:appuser /app /opt/render/.cache

# Switch to the non-root user
USER appuser

# Expose the port the application will run on
EXPOSE 8000

# Command to run the application
# Ensure your worker.py is directly in /app or adjust the path.
CMD ["uvicorn", "worker:app", "--host", "0.0.0.0", "--port", "8000"]
