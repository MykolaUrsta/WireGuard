
FROM python:3.11-slim as base
# Додаємо PYTHONPATH для коректного імпорту wg_portal
ENV PYTHONPATH=/app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies (cached layer)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    wireguard-tools \
    iptables \
    qrencode \
    netcat-traditional \
    cron \
    curl \
    docker.io \
    sudo \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app user early (cached layer)
RUN useradd --create-home --shell /bin/bash app

# Add app user to docker group for Docker socket access
RUN usermod -aG docker app

# Allow app user to run commands as root without password for stats sync
RUN echo "app ALL=(root) NOPASSWD: /usr/bin/python" >> /etc/sudoers

# Copy requirements first (cached layer if unchanged)
COPY requirements.txt .

# Install Python dependencies (cached layer if requirements unchanged)
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/assets /app/media /app/wireguard_configs /app/staticfiles \
    && chown -R app:app /app

# Copy application code (this will change most often)
COPY --chown=app:app . .

# Set permissions for entrypoint
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

USER app

ENTRYPOINT ["/app/entrypoint.sh"]
