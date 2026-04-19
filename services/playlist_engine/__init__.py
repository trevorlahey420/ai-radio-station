"""
Playlist Engine
---------------
Reads config/preferences.yaml and uses the PLAYLIST LLM to generate
intelligent, variety-aware track queues.

Responsibilities:
  - Parse user preferences (live-reloaded)
    - Expand artist similarity graph
      - Generate ordered track lists respecting cooldowns
        - Blend genres by mood/time block
          - Inject listener requests at the right position
          """

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import yaml

from services.llm_router import get_router, LLMRole

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/preferences.yaml")
QUEUE_PATH  = Path("outputs/current_queue.json")


@dataclass
class Track:
      title: str
      artist: str
      album: str = ""
      genre: str = ""
      youtube_query: str = ""   # search string used to fetch audio
    duration_seconds: int = 0
    source_url: str = ""      # resolved YouTube URL
    requested_by: Optional[str] = None   # Discord user if requested


@dataclass
class PlaylistState:
      queue: list[Track] = field(default_factory=list)
      played_artists: list[str] = field(default_factory=list)
      played_tracks: list[str] = field(default_factory=list)
      genre_streak: dict[str, int] = field(default_factory=dict)
      last_config_mtime: float = 0.0


class PlaylistEngine:

      SYSTEM_PROMPT = """You are a world-class music curator AI for an internet radio station.
      Your job is to generate a playlist that feels alive, surprising, and flows naturally.
      You deeply understand genre connections, artist relationships, and emotional arcs.
      Output ONLY valid JSON — an array of track objects. No commentary.
      Each track object: { "title": str, "artist": str, "album": str, "genre": str, "youtube_query": str }"""

    def __init__(self):
              self.state = PlaylistState()
              self.prefs: dict = {}
              self._load_prefs()

    # ── CONFIG ────────────────────────────────────────────────────────────────

    def _load_prefs(self) -> None:
              try:
                            mtime = CONFIG_PATH.stat().st_mtime
                            if mtime == self.state.last_config_mtime:
                                              return
                                          with CONFIG_PATH.open() as f:
                                                            self.prefs = yaml.safe_load(f)
                                                        self.state.last_config_mtime = mtime
                            logger.info("Preferences reloaded from %s", CONFIG_PATH)
except Exception as exc:
            logger.error("Failed to load preferences: %s", exc)

    # ── MOOD RESOLUTION ───────────────────────────────────────────────────────

    def _current_mood(self, hour: Optional[int] = None) -> list[str]:
              if hour is None:
                            hour = time.localtime().tm_hour
                        moods = self.prefs.get("mood_preferences", {})
        if 6 <= hour < 12:
                      return moods.get("morning", ["energetic"])
elif 12 <= hour < 18:
            return moods.get("daytime", ["focused"])
elif 18 <= hour < 22:
            return moods.get("evening", ["atmospheric"])
else:
            return moods.get("nighttime", ["dark", "chill"])

    # ── ARTIST POOL ───────────────────────────────────────────────────────────

    def _build_artist_context(self) -> str:
              favorites = self.prefs.get("favorite_artists", [])
        genres    = self.prefs.get("favorite_genres", [])
        dislikes  = self.prefs.get("disliked_artists", [])
        banned_g  = self.prefs.get("banned_genres", [])
        discovery = self.prefs.get("discovery_level", 0.5)
        depth     = self.prefs.get("similarity_depth", 2)
        max_sim   = self.prefs.get("max_similar_artists", 15)
        explicit  = self.prefs.get("explicit_content", True)

        lines = [
                      f"Favorite artists: {', '.join(favorites)}",
                      f"Favorite genres: {', '.join(genres)}",
                      f"Disliked artists: {', '.join(dislikes) or 'none'}",
                      f"Banned genres: {', '.join(banned_g) or 'none'}",
                      f"Discovery level: {discovery} (0=safe, 1=maximum exploration)",
                      f"Similarity depth: {depth} (1=direct, 3=third-degree)",
                      f"Max similar artists to include: {max_sim}",
                      f"Explicit content allowed: {explicit}",
        ]
        return "\n".join(lines)

    # ── COOLDOWN FILTER ───────────────────────────────────────────────────────

    def _cooldown_context(self) -> str:
              cooldown_artists = self.prefs.get("artist_cooldown_minutes", 60)
              cooldown_tracks  = self.prefs.get("track_cooldown_minutes", 180)
              max_streak       = self.prefs.get("max_genre_streak", 4)

        recent_artists = self.state.played_artists[-20:]
        recent_tracks  = self.state.played_tracks[-10:]

        lines = [
                      f"Artist cooldown: {cooldown_artists} minutes. Recently played artists to AVOID: {recent_artists}",
                      f"Track cooldown: {cooldown_tracks} minutes. Recently played tracks to AVOID: {recent_tracks}",
                      f"Max consecutive same-genre tracks: {max_streak}",
        ]
        return "\n".join(lines)

    # ── LLM GENERATION ───────────────────────────────────────────────────────

    def generate_tracks(self, count: int = 10) -> list[Track]:
              self._load_prefs()
              moods = self._current_mood()
              artist_ctx  = self._build_artist_context()
              cooldown_ctx = self._cooldown_context()

        user_msg = f"""Generate exactly {count} tracks for the radio queue right now.

        CURRENT MOOD: {', '.join(moods)}

        MUSIC PREFERENCES:
        {artist_ctx}

        AVOID (cooldowns & repetition):
        {cooldown_ctx}

        RULES:
        - Mix familiar favorites with discovery picks (per discovery_level)
        - Ensure genre variety — no more than {self.prefs.get('max_genre_streak', 4)} consecutive same genre
        - Sequence tracks so the energy arc feels intentional
        - Include "youtube_query" as: "Artist Name - Track Title official audio"
- Output ONLY a JSON array of {count} track objects"""

        router = get_router()
        try:
                      raw = router.complete(
                                        role=LLMRole.PLAYLIST,
                                        system_prompt=self.SYSTEM_PROMPT,
                                        user_message=user_msg,
                      )
                      tracks_data = json.loads(raw)
                      tracks = [Track(**t) for t in tracks_data]
                      logger.info("Generated %d tracks", len(tracks))
                      return tracks
except Exception as exc:
              logger.error("Playlist generation failed: %s", exc)
              return self._fallback_tracks(count)

    def _fallback_tracks(self, count: int) -> list[Track]:
              """Return placeholder tracks if LLM fails — station must never stall."""
              favorites = self.prefs.get("favorite_artists", ["Radiohead"])
              artists = (favorites * ((count // len(favorites)) + 1))[:count]
              return [
                  Track(
                      title="[Pending]",
                      artist=a,
                      youtube_query=f"{a} best songs",
                  )
                  for a in artists
              ]

    # ── QUEUE MANAGEMENT ─────────────────────────────────────────────────────

    def ensure_queue(self, min_size: int = 5) -> None:
              """Top up the queue if it's running low."""
              if len(self.state.queue) < min_size:
                            needed = 10 - len(self.state.queue)
                            new_tracks = self.generate_tracks(needed)
                            self.state.queue.extend(new_tracks)
                            self._flush_queue()

          def inject_request(self, track: Track, position: int = 1) -> None:
                    """Insert a listener-requested track at the given queue position."""
                    self.state.queue.insert(position, track)
                    self._flush_queue()
                    logger.info("Injected request: %s - %s at position %d", track.artist, track.title, position)

    def pop_next(self) -> Optional[Track]:
              """Return and remove the next track from the queue."""
              if not self.state.queue:
                            self.ensure_queue()
                        if not self.state.queue:
                                      return None
                                  track = self.state.queue.pop(0)
        # Record for cooldown tracking
        self.state.played_artists.append(track.artist)
        self.state.played_tracks.append(f"{track.artist} - {track.title}")
        # Keep history bounded
        self.state.played_artists = self.state.played_artists[-50:]
        self.state.played_tracks  = self.state.played_tracks[-50:]
        self._flush_queue()
        return track

    def _flush_queue(self) -> None:
              QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with QUEUE_PATH.open("w") as f:
                      json.dump([asdict(t) for t in self.state.queue], f, indent=2)


_engine_instance: Optional[PlaylistEngine] = None


def get_engine() -> PlaylistEngine:
      global _engine_instance
    if _engine_instance is None:
              _engine_instance = PlaylistEngine()
    return _engine_instance
