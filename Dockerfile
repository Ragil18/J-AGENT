# ====================================================================
# Dockerfile: Autonomous Job Application & Recruitment Cloud Agent
# Optimized for Render, Railway, Fly.io, GCP Cloud Run, and Docker VPS
# ====================================================================

FROM python:3.12-slim-bookworm

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Install system dependencies required for Playwright Chromium & headless execution
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gnupg \
    ca-certificates \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    fonts-liberation \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser binary
RUN python -m playwright install chromium

# Copy application files
COPY . .

# Create output directory for generated PDFs
RUN mkdir -p output

# Expose HTTP port for cloud health-checks and webhooks
EXPOSE 8000

# Run cloud scheduler daemon and API
CMD ["python", "scheduler.py"]
