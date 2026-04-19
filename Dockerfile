# ============================================================
# AI Radio Station — Dockerfile
# Platform: linux/amd64 (Ubuntu on VirtualBox compatible)
# Base: python:3.11-slim (Debian-based, amd64)
# ============================================================

FROM --platform=linux/amd64 python:3.11-slim

# ── System dependencies ───────────────────────────────────────
# ffmpeg: audio encoding/streaming to Icecast
# curl: healthcheck + yt-dlp updates
# ca-certificates: HTTPS for API calls
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Install yt-dlp (standalone binary — more reliable than pip version) ──────
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

# ── Create non-root user ──────────────────────────────────────
# Running as non-root is safer and avoids VirtualBox shared folder permission issues
RUN groupadd -r radio && useradd -r -g radio -m -d /app radio

WORKDIR /app

# ── Install Python dependencies ───────────────────────────────
# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Copy application code ─────────────────────────────────────
COPY --chown=radio:radio . .

# ── Create output directories ─────────────────────────────────
RUN mkdir -p outputs/audio_cache \
    && chown -R radio:radio outputs

# ── Switch to non-root user ───────────────────────────────────
USER radio

# ── Expose web player / API port ─────────────────────────────
EXPOSE 8080

# ── Health check ─────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# ── Entrypoint ────────────────────────────────────────────────
CMD ["python", "main.py"]
