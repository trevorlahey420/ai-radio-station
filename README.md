# Radio Free Gonzo

> Broadcasting from the edge of reason

A fully autonomous AI-powered internet radio station with multi-LLM architecture.
Streams music from YouTube, uses multiple LLMs for different roles, generates a Gonzo DJ voice,
delivers news and weather, accepts Discord requests, and serves a web player.
Everything controlled by config/preferences.yaml.

## Quick Start

    git clone https://github.com/trevorlahey420/ai-radio-station.git
    cd ai-radio-station
    cp .env.example .env
    docker compose up -d

Open http://localhost:8080 to listen.

## Architecture

main.py -> orchestration/scheduler (broadcast loop)
        -> services/llm_router (multi-LLM routing)
        -> services/playlist_engine (AI playlist generation)
        -> services/dj_script_generator (Gonzo DJ scripts)
        -> services/news_weather (news + weather segments)
        -> services/audio_pipeline (YouTube + TTS + Icecast)
        -> services/discord_bot (Discord integration)
        -> web/api_server.py (Flask REST API)
        -> web/player/index.html (web player)

## Multi-LLM Routing

PLAYLIST  -> OpenAI gpt-4o          (structured track selection)
DJ_SCRIPT -> Anthropic claude-3-5   (creative Gonzo persona)
NEWS      -> OpenAI gpt-4o-mini     (news summarization)

Override via env: LLM_DJ_PROVIDER, LLM_DJ_MODEL, LLM_PLAYLIST_PROVIDER etc.

## Configuration

Edit config/preferences.yaml to control music taste, moods, discovery level, DJ persona.
Changes are live-reloaded every 60 seconds.

Edit config/schedule.yaml for news timing, rotation blocks, maintenance settings.

## Required Keys

OPENAI_API_KEY, ANTHROPIC_API_KEY, ELEVENLABS_API_KEY/VOICE_ID, ICECAST_PASSWORD

Optional: NEWSAPI_KEY, OPENWEATHER_KEY, DISCORD_BOT_TOKEN

## Discord Commands

!request Artist - Title | !nowplaying | !queue | !skip (admin)

## API Endpoints

GET /now_playing | GET /queue | POST /request | GET /health

## Outputs

outputs/now_playing.json, outputs/current_queue.json, outputs/station.log, outputs/audio_cache/
