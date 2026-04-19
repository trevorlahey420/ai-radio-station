# Radio Free Gonzo
### Broadcasting from the edge of reason

> An autonomous AI-powered internet radio station with multi-LLM architecture, Gonzo DJ persona, YouTube audio streaming, news/weather segments, Discord integration, and a live web player.

---

## Budget Mode (Default ON)

This station runs in **budget mode by default** — designed to minimize API costs while staying fully functional.

| Component | Budget Choice | Est. Cost |
|---|---|---|
| LLM (all roles) | GPT-4o-mini | ~$0.15/1M tokens |
| DJ Voice (TTS) | OpenAI TTS tts-1, onyx voice | ~$15/1M chars |
| Music | YouTube via yt-dlp | Free |
| News API | NewsAPI free tier | Free |
| Weather API | OpenWeatherMap free tier | Free |

**Estimated total: ~$15–25/month running 24/7.**

To disable budget mode and use higher quality models, set `budget_mode: false` in `config/preferences.yaml`.

---

## Quick Start (Ubuntu on VirtualBox)

### 1. Install Docker inside Ubuntu (VirtualBox)

```bash
# Inside your Ubuntu VirtualBox VM:
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Clone the repo

```bash
git clone https://github.com/trevorlahey420/ai-radio-station.git
cd ai-radio-station
```

### 3. Set up your API keys

```bash
cp .env.example .env
nano .env   # or use any text editor
```

Minimum required (budget mode):
```
OPENAI_API_KEY=sk-...
ICECAST_PASSWORD=your-password-here
```

Optional (for news, weather, Discord):
```
NEWS_API_KEY=...
OPENWEATHER_API_KEY=...
DISCORD_TOKEN=...
```

### 4. Edit your music taste

```bash
nano config/preferences.yaml
```

Add your favorite artists and genres — the station will use these to build playlists dynamically.

### 5. Launch

```bash
docker compose up -d
```

### 6. Listen

- **Web player:** http://localhost:8080
- **Raw stream:** http://localhost:8000/radio
- **Now playing API:** http://localhost:8080/now_playing

> **VirtualBox tip:** To access the web player from your Mac host, either use the VM's IP address, or set up port forwarding in VirtualBox:
> Network > Adapter 1 > Advanced > Port Forwarding:
> Host Port 8080 → Guest Port 8080
> Host Port 8000 → Guest Port 8000

---

## Architecture

```
ai-radio-station/
├── config/
│   ├── preferences.yaml     # YOUR music taste + budget_mode setting
│   └── schedule.yaml        # news timing, rotation blocks
├── services/
│   ├── llm_router/          # routes tasks to GPT-4o-mini (budget) or GPT-4o
│   ├── playlist_engine/     # LLM-powered playlist generation
│   ├── dj_script_generator/ # Gonzo DJ scripts via LLM
│   ├── news_weather/        # news + weather API → broadcast segment
│   ├── audio_pipeline/      # YouTube fetch, TTS, Icecast streaming
│   └── discord_bot/         # song request bot
├── orchestration/
│   ├── scheduler/           # main loop — plays tracks, schedules DJ/news
│   └── state_manager/       # thread-safe now_playing + queue state
├── web/
│   ├── player/index.html    # dark retro web player UI
│   └── api_server.py        # Flask API (now_playing, queue, requests)
├── outputs/
│   ├── now_playing.json     # live-updated by scheduler
│   └── current_queue.json
├── main.py                  # entry point
├── Dockerfile               # linux/amd64 — Ubuntu/VirtualBox compatible
├── docker-compose.yml       # icecast + radio services
└── .env.example             # API key reference
```

---

## Multi-LLM Architecture

Each role uses a separate LLM call — all routed through `services/llm_router/`.

| Role | Task | Budget Model |
|---|---|---|
| Playlist | Generate track lists, discover similar artists | gpt-4o-mini |
| DJ Script | Gonzo-style intros, outros, station IDs | gpt-4o-mini |
| News | Turn API data into broadcast segments | gpt-4o-mini |
| Moderation | Ensure output structure is valid | gpt-4o-mini |

---

## DJ Persona

The station's DJ is inspired by Hunter S. Thompson — Gonzo, chaotic, poetic, deeply passionate about music, anti-establishment, explicit, and uncensored. Personality is defined in `services/dj_script_generator/__init__.py` and is never moderated for content.

---

## Logs

```bash
docker compose logs -f radio     # station logs
docker compose logs -f icecast   # stream server logs
```

## Stop

```bash
docker compose down
```

## Update

```bash
git pull
docker compose up -d --build
```

---

*Radio Free Gonzo — no ads, no algorithm, no apologies.*
