"""
main.py - Radio Free Gonzo Entry Point

Starts three concurrent services:
  1. RadioScheduler   - Main broadcast loop (music + DJ + news)
    2. Flask API Server - REST API + web player backend
      3. Discord Bot      - Listener requests via Discord

      All services run as daemon threads except the scheduler
      which blocks the main thread.

      Usage:
        python main.py

        Environment variables required (see .env.example):
          OPENAI_API_KEY, ANTHROPIC_API_KEY,
            ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID,
              ICECAST_HOST, ICECAST_PORT, ICECAST_PASSWORD, ICECAST_MOUNT,
                NEWSAPI_KEY, OPENWEATHER_KEY,
                  DISCORD_BOT_TOKEN (optional)
                  """

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

# ── LOGGING SETUP ─────────────────────────────────────────────────────────────
logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
      handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("outputs/station.log", encoding="utf-8"),
      ],
)
logger = logging.getLogger("main")

# Ensure output dirs exist
Path("outputs/audio_cache").mkdir(parents=True, exist_ok=True)
Path("outputs").mkdir(exist_ok=True)

# ── LOAD .env IF PRESENT ──────────────────────────────────────────────────────
try:
      from dotenv import load_dotenv
      load_dotenv()
      logger.info("Loaded .env")
except ImportError:
      pass


def start_api_server():
      """Run Flask API server in a daemon thread."""
      from web.api_server import run_server
      host = os.getenv("API_HOST", "0.0.0.0")
      port = int(os.getenv("API_PORT", "8080"))
      logger.info("Starting API server on %s:%s", host, port)
      run_server(host=host, port=port)


def start_discord_bot():
      """Run Discord bot in a daemon thread (optional)."""
      token = os.getenv("DISCORD_BOT_TOKEN")
      if not token:
                logger.info("DISCORD_BOT_TOKEN not set — Discord bot disabled")
                return
            from services.discord_bot import run_bot
    logger.info("Starting Discord bot")
    run_bot()


def main():
      logger.info("=" * 60)
    logger.info("  RADIO FREE GONZO — AI RADIO STATION")
    logger.info("  Broadcasting from the edge of reason")
    logger.info("=" * 60)

    # Check critical env vars
    missing = []
    for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
              if not os.getenv(key):
                            missing.append(key)
                    if missing:
                              logger.warning("Missing env vars: %s — some features may fail", missing)

    # Start API server thread
    api_thread = threading.Thread(target=start_api_server, daemon=True, name="api-server")
    api_thread.start()

    # Start Discord bot thread
    discord_thread = threading.Thread(target=start_discord_bot, daemon=True, name="discord-bot")
    discord_thread.start()

    # Start main scheduler (blocks)
    from orchestration.scheduler import RadioScheduler
    scheduler = RadioScheduler()
    try:
              scheduler.run()
except KeyboardInterrupt:
        logger.info("Shutting down Radio Free Gonzo...")
        scheduler.stop()
finally:
        logger.info("Station offline. Good night.")


if __name__ == "__main__":
      main()
