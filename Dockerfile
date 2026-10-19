# InstaVerify API Dockerfile
# Multi-stage build with Playwright Chromium

FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright system dependencies
RUN pip3 install --no-cache-dir playwright && \
    playwright install --with-deps chromium

FROM python:3.11-slim

# Install runtime dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    libxshmfence1 \
    libx11-xcb1 \
    libxcb-dri2-0 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libpango-1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libxcb-glx0 \
    libxext6 \
    libexpat1 \
    libfontconfig1 \
    libfreetype6 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Playwright browsers from builder
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Set working directory
WORKDIR /app

# Copy application code
COPY pyproject.toml requirements.txt ./
COPY app ./app
COPY tests ./tests

# Install Python dependencies
RUN pip install --no-cache-dir .[dev]

# Change ownership
RUN chown -R appuser:appuser /app /root/.cache/ms-playwright

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health', timeout=5); exit(0 if r.status_code == 200 else 1)"

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
