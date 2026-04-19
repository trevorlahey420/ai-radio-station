"""State Manager - Central in-memory + on-disk state for the radio station."""
from __future__ import annotations
import json, logging, threading, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
NOW_PLAYING_PATH = Path("outputs/now_playing.json")
NOW_PLAYING_PATH.parent.mkdir(parents=True, exist_ok=True)

@dataclass
class StationState:
      now_playing: Optional[dict] = None
      is_streaming: bool = False
      skip_requested: bool = False
      station_start_time: float = field(default_factory=time.time)
      tracks_played_count: int = 0
      last_news_segment_time: float = 0.0
      current_segment_type: str = "music"

class StateManager:
      def __init__(self):
                self._state = StationState()
                self._lock = threading.Lock()
                self._running = False

      @property
      def now_playing(self):
                with self._lock:
                              return self._state.now_playing

            @property
      def skip_requested(self):
                with self._lock:
                              return self._state.skip_requested

            @property
    def tracks_played_count(self):
              with self._lock:
                            return self._state.tracks_played_count

          @property
    def last_news_segment_time(self):
              with self._lock:
                            return self._state.last_news_segment_time

          def set_now_playing(self, track_dict):
                    with self._lock:
                                  self._state.now_playing = track_dict
                                  if track_dict:
                                                    self._state.tracks_played_count += 1
                                            self._flush()
                              artist = (track_dict or {}).get("artist", "?")
        title = (track_dict or {}).get("title", "?")
        logger.info("Now playing: %s - %s", artist, title)

    def set_streaming(self, value):
              with self._lock:
                            self._state.is_streaming = value

    def set_segment_type(self, seg_type):
              with self._lock:
                            self._state.current_segment_type = seg_type

    def request_skip(self):
              with self._lock:
                            self._state.skip_requested = True
                        logger.info("Skip requested")

    def clear_skip(self):
              with self._lock:
                            self._state.skip_requested = False

    def record_news_segment(self):
              with self._lock:
                            self._state.last_news_segment_time = time.time()

    def news_due(self, interval_hours=4.0):
              with self._lock:
                            elapsed = time.time() - self._state.last_news_segment_time
                            return elapsed >= interval_hours * 3600

    def _flush(self):
              try:
                            with self._lock:
                                              data = {
                                                                    "now_playing": self._state.now_playing,
                                                                    "is_streaming": self._state.is_streaming,
                                                                    "tracks_played": self._state.tracks_played_count,
                                                                    "segment_type": self._state.current_segment_type,
                                                                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                              }
                                          with NOW_PLAYING_PATH.open("w") as f:
                                                            json.dump(data, f, indent=2)
except Exception as exc:
            logger.error("State flush failed: %s", exc)

    def start_background_flush(self, interval_seconds=10):
              self._running = True
        def _loop():
                      while self._running:
                                        self._flush()
                                        time.sleep(interval_seconds)
                                threading.Thread(target=_loop, daemon=True).start()

    def stop(self):
              self._running = False

_sm: Optional[StateManager] = None

def get_state_manager():
      global _sm
    if _sm is None:
              _sm = StateManager()
    return _sm
