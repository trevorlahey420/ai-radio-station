"""
Scheduler - Main orchestration loop for the radio station.

This is the beating heart. It:
  1. Ensures queue always has tracks ready
    2. Pre-fetches next track audio while current plays
      3. Generates + speaks DJ intros before each track
        4. Fires news/weather segments on schedule
          5. Monitors for skip signals
            6. Never stalls - always has a fallback
            """

from __future__ import annotations

import dataclasses
import logging
import threading
import time
from pathlib import Path
from typing import Optional

import yaml

from orchestration.state_manager import get_state_manager
from services.audio_pipeline import YouTubeAudioFetcher, TTSEngine, IcecastStreamer, cleanup_cache
from services.dj_script_generator import get_generator
from services.news_weather import get_service as get_news_service
from services.playlist_engine import get_engine, Track

logger = logging.getLogger(__name__)

SCHEDULE_PATH = Path("config/schedule.yaml")


def _load_schedule() -> dict:
      try:
                with SCHEDULE_PATH.open() as f:
                              return yaml.safe_load(f) or {}
      except Exception:
                return {}


class RadioScheduler:
      """Main scheduling loop. Call run() to start broadcasting."""

    def __init__(self):
              self.engine    = get_engine()
              self.state_mgr = get_state_manager()
              self.dj_gen    = get_generator()
              self.news_svc  = get_news_service()
              self.fetcher   = YouTubeAudioFetcher()
              self.tts       = TTSEngine()
              self.streamer  = IcecastStreamer()
              self._running  = False
              self._prefetch_thread: Optional[threading.Thread] = None
              self._next_audio_path: Optional[Path] = None
              self._next_track: Optional[Track] = None

    # ── MAIN LOOP ─────────────────────────────────────────────────────────────

    def run(self):
              """Start the station. Blocks until stop() is called."""
              logger.info("Radio Free Gonzo is LIVE")
              self._running = True
              self.state_mgr.start_background_flush()

        # Opening sign-on
              self._play_dj_segment(self.dj_gen.sign_on())

        # Ensure we have tracks
              self.engine.ensure_queue(min_size=10)

        # Kick off prefetch thread
              self._start_prefetch()

        tracks_since_dj   = 0
        sched = _load_schedule()
        dj_every_n = sched.get("dj_segments", {}).get("dj_speak_every_n_tracks",
                                                                           yaml.safe_load(open("config/preferences.yaml").read()).get("dj_speak_every_n_tracks", 3))
        news_interval_h = sched.get("news_weather", {}).get("interval_hours", 4)

        while self._running:
                      try:
                                        sched = _load_schedule()

                          # Check if news segment is due
                                        if (sched.get("news_weather", {}).get("enabled", True)
                                                                    and self.state_mgr.news_due(interval_hours=news_interval_h)):
                                                                                          self._run_news_segment()
                                                                                          tracks_since_dj = 0

                                        # Get next track
                                        track = self._get_next_track()
                                        if not track:
                                                              logger.warning("No track available, waiting 5s...")
                                                              time.sleep(5)
                                                              continue

                                        # Generate + play DJ intro
                                        if tracks_since_dj >= dj_every_n:
                                                              prev_np = self.state_mgr.now_playing
                                                              prev_artist = (prev_np or {}).get("artist") if prev_np else None
                                                              script = self.dj_gen.track_intro(
                                                                  artist=track.artist,
                                                                  title=track.title,
                                                                  album=track.album,
                                                                  genre=track.genre,
                                                                  previous_artist=prev_artist,
                                                                  requested_by=track.requested_by,
                                                              )
                                                              self._play_dj_segment(script)
                                                              tracks_since_dj = 0

                                        # Update now playing state
                                        self.state_mgr.set_now_playing(dataclasses.asdict(track))
                self.state_mgr.set_segment_type("music")

                # Get audio (from prefetch or fresh download)
                audio_path = self._get_audio(track)
                if not audio_path:
                                      logger.error("Could not get audio for %s - %s, skipping", track.artist, track.title)
                                      tracks_since_dj += 1
                                      continue

                # Start next prefetch in background
                self._start_prefetch()

                # Stream the track
                self.state_mgr.set_streaming(True)
                self._stream_with_skip_monitor(audio_path, track)
                self.state_mgr.set_streaming(False)
                self.state_mgr.clear_skip()

                tracks_since_dj += 1

                # Cache cleanup on every 20th track
                if self.state_mgr.tracks_played_count % 20 == 0:
                                      sched_cfg = _load_schedule()
                                      max_age = sched_cfg.get("maintenance", {}).get("cache_cleanup_hours", 24)
                                      threading.Thread(
                                          target=cleanup_cache, args=(max_age,), daemon=True
                                      ).start()

except KeyboardInterrupt:
                break
except Exception as exc:
                logger.error("Scheduler error: %s", exc, exc_info=True)
                time.sleep(3)  # Brief pause before retrying

        self.state_mgr.stop()
        logger.info("Scheduler stopped.")

    def stop(self):
              self._running = False

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _get_next_track(self) -> Optional[Track]:
              """Pop track from queue, ensure queue stays topped up."""
        self.engine.ensure_queue(min_size=5)
        return self.engine.pop_next()

    def _get_audio(self, track: Track) -> Optional[Path]:
              """Use prefetched audio if available, otherwise download."""
        if self._next_audio_path and self._next_track and \
           self._next_track.youtube_query == track.youtube_query:
                         path = self._next_audio_path
                         self._next_audio_path = None
                         self._next_track = None
                         if path and path.exists():
                                           return path

                     # Fresh download
                     return self.fetcher.download_to_cache(track.youtube_query)

    def _start_prefetch(self):
              """Start downloading the next track in the background."""
        def _prefetch():
                      queue = self.engine.state.queue
            if not queue:
                              return
                          next_track = queue[0]
            logger.debug("Prefetching: %s", next_track.youtube_query)
            path = self.fetcher.download_to_cache(next_track.youtube_query)
            self._next_audio_path = path
            self._next_track = next_track

        if self._prefetch_thread and self._prefetch_thread.is_alive():
                      return
        self._prefetch_thread = threading.Thread(target=_prefetch, daemon=True)
        self._prefetch_thread.start()

    def _play_dj_segment(self, script: str):
              """Convert DJ script to audio and stream it."""
        if not script or not script.strip():
                      return
        try:
                      self.state_mgr.set_segment_type("dj")
            audio_path = self.tts.synthesize(script)
            self.streamer.stream_file(audio_path, metadata={"artist": "Doctor Gonzo", "title": "DJ Segment"})
except Exception as exc:
            logger.error("DJ segment playback failed: %s", exc)

    def _run_news_segment(self):
              """Generate and stream a news/weather broadcast."""
        try:
                      self.state_mgr.set_segment_type("news")
            bridge_in = self.dj_gen.news_bridge_in()
            self._play_dj_segment(bridge_in)

            script = self.news_svc.generate_segment()
            self._play_dj_segment(script)

            bridge_out = self.dj_gen.news_bridge_out()
            self._play_dj_segment(bridge_out)

            self.state_mgr.record_news_segment()
            logger.info("News segment complete.")
except Exception as exc:
            logger.error("News segment failed: %s", exc)

    def _stream_with_skip_monitor(self, audio_path: Path, track: Track):
              """Stream audio file while watching for skip signals."""
        stream_thread = threading.Thread(
                      target=self.streamer.stream_file,
                      args=(audio_path,),
                      kwargs={"metadata": dataclasses.asdict(track)},
                      daemon=True,
        )
        stream_thread.start()

        while stream_thread.is_alive():
                      if self.state_mgr.skip_requested:
                                        self.streamer.stop()
                                        logger.info("Track skipped.")
                                        break
                                    time.sleep(0.5)

        stream_thread.join(timeout=2)
