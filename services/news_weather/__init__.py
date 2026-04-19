"""
News & Weather Service
-----------------------
Fetches real-world data from APIs and converts it into
broadcast-ready DJ-voiced segments via the NEWS LLM.

APIs supported:
  - NewsAPI (https://newsapi.org)  — NEWSAPI_KEY env var
    - OpenWeatherMap                  — OPENWEATHER_KEY env var

    Segment flow:
      1. Fetch top N news articles
        2. Fetch current weather for configured location
          3. Feed raw data to NEWS LLM with DJ styling instructions
            4. Return formatted broadcast script
              5. Hand off to TTS pipeline
              """

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
import yaml
from pathlib import Path

from services.llm_router import get_router, LLMRole

logger = logging.getLogger(__name__)
CONFIG_PATH = Path("config/preferences.yaml")

NEWS_SYSTEM_PROMPT = """You are a news writer for an underground radio station with attitude.
Your job is to take raw news headlines and weather data and turn them into a punchy,
opinionated, entertaining 5-10 minute broadcast segment.
The station's DJ voice is Gonzo: sharp, real, darkly funny.
Do NOT be neutral. Have a point of view. Despise corporate spin.
Format: flowing broadcast prose, no bullet points, no headers.
End with a clear handoff back to music."""


def _load_prefs() -> dict:
      try:
                with CONFIG_PATH.open() as f:
                              return yaml.safe_load(f) or {}
      except Exception:
                return {}


@dataclass
class NewsArticle:
      title: str
      description: str
      source: str
      url: str
      published_at: str


@dataclass
class WeatherData:
      city: str
      description: str
      temp_f: float
      temp_c: float
      humidity: int
      wind_mph: float
      feels_like_f: float


class NewsWeatherService:

      def __init__(self):
                self.router = get_router()
                self.news_api_key      = os.getenv("NEWSAPI_KEY", "")
                self.weather_api_key   = os.getenv("OPENWEATHER_KEY", "")

      # ── NEWS ──────────────────────────────────────────────────────────────────

    def fetch_news(self, max_articles: int = 5, categories: Optional[list] = None) -> list[NewsArticle]:
              if not self.news_api_key:
                            logger.warning("NEWSAPI_KEY not set — skipping news fetch")
                            return []

              cat = (categories or ["general"])[0]  # NewsAPI top-headlines takes one category
        url = "https://newsapi.org/v2/top-headlines"
        params = {
                      "apiKey": self.news_api_key,
                      "language": "en",
                      "category": cat,
                      "pageSize": max_articles,
        }
        try:
                      resp = requests.get(url, params=params, timeout=10)
                      resp.raise_for_status()
                      articles = resp.json().get("articles", [])
                      return [
                          NewsArticle(
                              title=a.get("title", ""),
                              description=a.get("description", "") or "",
                              source=a.get("source", {}).get("name", "Unknown"),
                              url=a.get("url", ""),
                              published_at=a.get("publishedAt", ""),
                          )
                          for a in articles
                          if a.get("title") and "[Removed]" not in a.get("title", "")
                      ]
except Exception as exc:
              logger.error("News fetch failed: %s", exc)
                                                      return []

    # ── WEATHER ───────────────────────────────────────────────────────────────

    def fetch_weather(self) -> Optional[WeatherData]:
              if not self.weather_api_key:
                            logger.warning("OPENWEATHER_KEY not set — skipping weather fetch")
                            return None

        prefs = _load_prefs()
        loc = prefs.get("location", {})
        lat = loc.get("lat", 36.1699)
        lon = loc.get("lon", -115.1398)
        city = loc.get("city", "Las Vegas")

        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
                      "lat": lat,
                      "lon": lon,
                      "appid": self.weather_api_key,
                      "units": "metric",
        }
        try:
                      resp = requests.get(url, params=params, timeout=10)
                      resp.raise_for_status()
                      data = resp.json()
                      temp_c = data["main"]["temp"]
                      return WeatherData(
                          city=city,
                          description=data["weather"][0]["description"],
                          temp_c=round(temp_c, 1),
                          temp_f=round(temp_c * 9 / 5 + 32, 1),
                          humidity=data["main"]["humidity"],
                          wind_mph=round(data["wind"]["speed"] * 2.237, 1),
                          feels_like_f=round(data["main"]["feels_like"] * 9 / 5 + 32, 1),
                      )
except Exception as exc:
            logger.error("Weather fetch failed: %s", exc)
            return None

    # ── SEGMENT GENERATION ────────────────────────────────────────────────────

    def generate_segment(self) -> str:
              """Fetch fresh data and produce a full broadcast segment script."""
        prefs = _load_prefs()
        nw_cfg = {}
        try:
                      with Path("config/schedule.yaml").open() as f:
                                        sched = yaml.safe_load(f)
                                        nw_cfg = sched.get("news_weather", {})
except Exception:
            pass

        max_articles = nw_cfg.get("news_sources", [{}])[0].get("max_articles", 5) \
                       if nw_cfg.get("news_sources") else 5
        categories   = nw_cfg.get("news_sources", [{}])[0].get("categories", ["general"]) \
                       if nw_cfg.get("news_sources") else ["general"]

        articles = self.fetch_news(max_articles=max_articles, categories=categories)
        weather  = self.fetch_weather()

        # Build raw data block for the LLM
        now = datetime.now().strftime("%A, %B %d %Y — %I:%M %p")
        parts = [f"BROADCAST TIME: {now}\n"]

        if articles:
                      parts.append("TOP NEWS STORIES:")
                      for i, a in enumerate(articles, 1):
                                        parts.append(f"{i}. [{a.source}] {a.title}\n   {a.description}")
        else:
            parts.append("NEWS: Unable to fetch stories at this time.")

        if weather:
                      parts.append(
                                        f"\nWEATHER — {weather.city}: "
                                        f"{weather.description.capitalize()}, "
                                        f"{weather.temp_f}°F ({weather.temp_c}°C), "
                                        f"Humidity {weather.humidity}%, "
                                        f"Wind {weather.wind_mph} mph, "
                                        f"Feels like {weather.feels_like_f}°F"
                      )
else:
            parts.append("\nWEATHER: Data unavailable.")

        raw_data = "\n".join(parts)

        station = prefs.get("station_name", "Radio Free Gonzo")
        user_msg = f"""Generate a radio news + weather broadcast segment for {station}.

        RAW DATA:
        {raw_data}

        Create an engaging, personality-driven segment.
        Approximate length: {nw_cfg.get('segment_duration_minutes', 10)} minutes when read aloud.
        End with a clear cue back to music."""

        try:
                      script = self.router.complete(
                                        role=LLMRole.NEWS,
                                        system_prompt=NEWS_SYSTEM_PROMPT,
                                        user_message=user_msg,
                      )
                      logger.info("News/weather segment generated (%d chars)", len(script))
                      return script
except Exception as exc:
            logger.error("Segment generation failed: %s", exc)
            return f"The news is broken. The weather is weird. We'll be back with music in a moment."


_service_instance: Optional[NewsWeatherService] = None


def get_service() -> NewsWeatherService:
      global _service_instance
    if _service_instance is None:
              _service_instance = NewsWeatherService()
    return _service_instance
