# ============================================================
# Radio Free Gonzo - Dockerfile
# ============================================================
FROM python:3.11-slim

LABEL maintainer="Radio Free Gonzo"
LABEL description="AI-powered internet radio station"

# System deps: ffmpeg (audio), curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
        curl \
            ca-certificates \
                && rm -rf /var/lib/apt/lists/*

                WORKDIR /app

                # Copy and install Python dependencies first (layer caching)
                COPY requirements.txt .
                RUN pip install --no-cache-dir -r requirements.txt

                # Copy application code
                COPY . .

                # Create necessary directories
                RUN mkdir -p outputs/audio_cache

                # Non-root user for security
                RUN useradd -r -s /bin/false radio && \
                    chown -R radio:radio /app
                    USER radio

                    # Expose web API port
                    EXPOSE 8080

                    # Health check
                    HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
                      CMD curl -f http://localhost:8080/health || exit 1

                      # Start the station
                      CMD ["python", "main.py"]
                      
