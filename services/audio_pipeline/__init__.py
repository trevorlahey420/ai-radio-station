"""
Audio Pipeline
--------------
Handles all audio I/O for the radio station:

1. YouTube Audio Fetching (yt-dlp)
   - Downloads/streams audio for a track given a search query
      - Converts to streamable MP3/AAC

      2. Text-to-Speech (DJ Voice)
         - Converts DJ scripts to audio
            - Pluggable provider: ElevenLabs | OpenAI TTS | Local

            3. Icecast/Liquidsoap Stream Output
               - Pushes continuous audio to Icecast2 server
                  - Manages crossfade between tracks

                  4. Cache Management
                     - Caches downloaded audio files
                        - Auto-purges based on schedule config
                        """

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

import requests
import yaml

logger = logging.getLogger(__name__)

CACHE_DIR = Path("outputs/audio_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = Path("config/preferences.yaml")


def _load_prefs() -> dict:
      try:
                with CONFIG_PATH.open() as f:
                              return yaml.safe_load(f) or {}
      except Exception:
                return {}


# ── YOUTUBE AUDIO FETCHER ─────────────────────────────────────────────────────

class YouTubeAudioFetcher:
      """
          Uses yt-dlp to search YouTube and download/stream audio.
              yt-dlp must be installed: pip install yt-dlp
                  """

    def search_and_get_url(self, query: str) -> Optional[str]:
              """
                      Search YouTube for `query` and return a direct audio stream URL.
                              Falls back to downloading a cached file if streaming fails.
                                      """
              import yt_dlp

        ydl_opts = {
                      "format": "bestaudio/best",
                      "quiet": True,
                      "no_warnings": True,
                      "extract_flat": False,
                      "default_search": "ytsearch1:",
        }

        try:
                      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                        info = ydl.extract_info(query, download=False)
                                        if "entries" in info:
                                                              info = info["entries"][0]
                                                          url = info.get("url")
                                        logger.info("Resolved audio URL for: %s", query)
                                        return url
        except Exception as exc:
                      logger.error("YouTube URL extraction failed for '%s': %s", query, exc)
                      return None

    def download_to_cache(self, query: str) -> Optional[Path]:
              """Download audio to cache dir and return local file path."""
              import yt_dlp

        cache_key = hashlib.md5(query.encode()).hexdigest()
        out_path  = CACHE_DIR / f"{cache_key}.mp3"

        if out_path.exists():
                      logger.debug("Cache hit: %s", out_path)
                      return out_path

        prefs  = _load_prefs()
        bitrate = prefs.get("audio_bitrate", 192)

        ydl_opts = {
                      "format": "bestaudio/best",
                      "quiet": True,
                      "no_warnings": True,
                      "default_search": "ytsearch1:",
                      "outtmpl": str(CACHE_DIR / f"{cache_key}.%(ext)s"),
                      "postprocessors": [{
                                        "key": "FFmpegExtractAudio",
                                        "preferredcodec": "mp3",
                                        "preferredquality": str(bitrate),
                      }],
        }

        try:
                      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                        ydl.download([query])
                                    if out_path.exists():
                                                      logger.info("Downloaded: %s -> %s", query, out_path)
                                                      return out_path
except Exception as exc:
            logger.error("Download failed for '%s': %s", query, exc)
        return None


# ── TEXT-TO-SPEECH ────────────────────────────────────────────────────────────

class TTSEngine:
      """
          Pluggable TTS engine. Provider selected from preferences.yaml.
              Supported: elevenlabs | openai | local (piper/coqui)
                  """

    def __init__(self):
              prefs = _load_prefs()
                  self.provider = prefs.get("dj_voice_provider", "elevenlabs")
        self.voice_id = prefs.get("dj_voice_id", "")

    def synthesize(self, text: str, output_path: Optional[Path] = None) -> Path:
              """Convert text to audio file. Returns path to the audio file."""
        if output_path is None:
                      cache_key   = hashlib.md5(text.encode()).hexdigest()[:16]
            output_path = CACHE_DIR / f"tts_{cache_key}.mp3"

        if output_path.exists():
                      return output_path

        if self.provider == "elevenlabs":
                      return self._elevenlabs(text, output_path)
elif self.provider == "openai":
            return self._openai_tts(text, output_path)
elif self.provider == "local":
            return self._local_tts(text, output_path)
else:
            raise ValueError(f"Unknown TTS provider: {self.provider}")

    def _elevenlabs(self, text: str, out: Path) -> Path:
              api_key  = os.environ.get("ELEVENLABS_API_KEY", "")
        voice_id = self.voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "")

        if not api_key:
                      raise RuntimeError("ELEVENLABS_API_KEY not set")

        url  = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
                      "xi-api-key": api_key,
                      "Content-Type": "application/json",
        }
        payload = {
                      "text": text,
                      "model_id": "eleven_turbo_v2",
                      "voice_settings": {"stability": 0.35, "similarity_boost": 0.75},
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        out.write_bytes(resp.content)
        logger.info("ElevenLabs TTS -> %s", out)
        return out

    def _openai_tts(self, text: str, out: Path) -> Path:
              import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp   = client.audio.speech.create(
                      model="tts-1-hd",
                      voice="onyx",
                      input=text,
        )
        out.write_bytes(resp.content)
        logger.info("OpenAI TTS -> %s", out)
        return out

    def _local_tts(self, text: str, out: Path) -> Path:
              # Assumes piper TTS installed: https://github.com/rhasspy/piper
              model = os.getenv("LOCAL_TTS_MODEL", "en_US-lessac-medium")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                      tmp_wav = Path(tmp.name)

        subprocess.run(
                      ["piper", "--model", model, "--output_file", str(tmp_wav)],
                      input=text.encode(),
                      check=True,
        )
        # Convert WAV -> MP3
        subprocess.run(
                      ["ffmpeg", "-y", "-i", str(tmp_wav), str(out)],
                      check=True, capture_output=True,
        )
        tmp_wav.unlink(missing_ok=True)
        logger.info("Local TTS -> %s", out)
        return out


# ── STREAM OUTPUT ─────────────────────────────────────────────────────────────

class IcecastStreamer:
      """
          Streams audio to an Icecast2 server using ffmpeg.
              Supports queuing multiple audio files for seamless playback.
                  """

    def __init__(self):
              self.host     = os.getenv("ICECAST_HOST",     "localhost")
        self.port     = int(os.getenv("ICECAST_PORT", "8000"))
        self.password = os.getenv("ICECAST_PASSWORD", "hackme")
        self.mount    = os.getenv("ICECAST_MOUNT",    "/stream")
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def stream_file(self, audio_path: Path, metadata: Optional[dict] = None) -> None:
              """Stream a single audio file to Icecast."""
        prefs  = _load_prefs()
        bitrate = prefs.get("audio_bitrate", 192)
        title   = f"{metadata.get('artist','?')} - {metadata.get('title','?')}" \
                  if metadata else "Radio Free Gonzo"

        icecast_url = (
                      f"icecast://source:{self.password}@{self.host}:{self.port}{self.mount}"
        )

        cmd = [
                      "ffmpeg", "-re", "-i", str(audio_path),
                      "-vn",
                      "-acodec", "libmp3lame",
                      "-ab", f"{bitrate}k",
                      "-ar", "44100",
                      "-content_type", "audio/mpeg",
                      "-ice_name", "Radio Free Gonzo",
                      "-ice_description", title,
                      "-f", "mp3", icecast_url,
                      "-loglevel", "error",
        ]

        logger.info("Streaming: %s -> %s", audio_path.name, icecast_url)
        with self._lock:
                      self._proc = subprocess.Popen(cmd)
            self._proc.wait()

    def stop(self) -> None:
              if self._proc and self._proc.poll() is None:
                            self._proc.terminate()
                            logger.info("Stream stopped")


# ── CACHE CLEANUP ─────────────────────────────────────────────────────────────

def cleanup_cache(max_age_hours: int = 24) -> None:
      """Remove cached audio files older than max_age_hours."""
    import time
    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0
    for f in CACHE_DIR.iterdir():
              if f.is_file() and f.stat().st_mtime < cutoff:
                            f.unlink()
                            removed += 1
                    if removed:
                              logger.info("Cleaned up %d old cache files", removed)
                      
