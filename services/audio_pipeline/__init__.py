"""
Audio Pipeline — handles YouTube audio fetching, TTS generation, and Icecast streaming.

TTS Provider priority (budget mode ON by default):
  1. openai  — cheap, good quality, uses tts-1 model + onyx voice
  2. elevenlabs — more expressive but costs more
  3. piper  — fully local/free, no API needed

Budget mode is read from config/preferences.yaml.
"""

import os
import subprocess
import tempfile
import time
import logging
from pathlib import Path
from typing import Optional
import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parents[2] / "config" / "preferences.yaml"
CACHE_DIR = Path(__file__).parents[2] / "outputs" / "audio_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


# ─── YouTube Audio Fetcher ───────────────────────────────────────────────────

class YouTubeAudioFetcher:
    """
    Downloads audio from YouTube using yt-dlp.
    Outputs mp3 files to the audio cache directory.
    Budget: uses lowest reasonable quality (128kbps mp3) to save space/bandwidth.
    """

    def __init__(self):
        self.cache_dir = CACHE_DIR

    def fetch(self, query: str, track_id: str) -> Optional[Path]:
        """
        Search YouTube for query and download best audio.
        Returns path to downloaded mp3, or None on failure.
        """
        output_path = self.cache_dir / f"{track_id}.mp3"

        if output_path.exists():
            logger.info(f"[AudioFetch] Cache hit: {track_id}")
            return output_path

        logger.info(f"[AudioFetch] Fetching: {query}")

        cmd = [
            "yt-dlp",
            f"ytsearch1:{query}",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "5",       # 128kbps approx — budget quality
            "--output", str(self.cache_dir / f"{track_id}.%(ext)s"),
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            "--socket-timeout", "30",
        ]

        try:
            result = subprocess.run(cmd, timeout=120, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"[AudioFetch] yt-dlp error: {result.stderr}")
                return None
            if output_path.exists():
                return output_path
            logger.error(f"[AudioFetch] File not found after download: {output_path}")
            return None
        except subprocess.TimeoutExpired:
            logger.error(f"[AudioFetch] Timeout fetching: {query}")
            return None
        except Exception as e:
            logger.error(f"[AudioFetch] Exception: {e}")
            return None


# ─── TTS Engine ──────────────────────────────────────────────────────────────

class TTSEngine:
    """
    Text-to-speech engine for DJ voice generation.
    Reads provider from config/preferences.yaml tts section.
    Budget default: OpenAI TTS with tts-1 model (cheapest option).
    """

    def __init__(self):
        self._cfg = _load_config()

    def reload_config(self):
        self._cfg = _load_config()

    def _get_tts_cfg(self) -> dict:
        return self._cfg.get("tts", {})

    def _get_provider(self) -> str:
        budget_mode = self._cfg.get("budget_mode", True)
        tts_cfg = self._get_tts_cfg()
        explicit_provider = tts_cfg.get("provider", "")

        # In budget mode, always use openai unless explicitly overridden to piper
        if budget_mode and explicit_provider not in ("piper", "elevenlabs"):
            return "openai"
        return explicit_provider or "openai"

    def synthesize(self, text: str, output_path: Path) -> bool:
        """
        Convert text to speech. Returns True on success.
        """
        self.reload_config()
        provider = self._get_provider()
        logger.info(f"[TTS] Using provider: {provider}")

        if provider == "openai":
            return self._openai_tts(text, output_path)
        elif provider == "elevenlabs":
            return self._elevenlabs_tts(text, output_path)
        elif provider == "piper":
            return self._piper_tts(text, output_path)
        else:
            logger.error(f"[TTS] Unknown provider: {provider}")
            return False

    def _openai_tts(self, text: str, output_path: Path) -> bool:
        """
        OpenAI TTS — budget default.
        tts-1 model: ~$15 per 1M characters (~$0.015 per 1K chars)
        onyx voice: deep, gravelly — best fit for Gonzo DJ persona
        """
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
            tts_cfg = self._get_tts_cfg()

            model = tts_cfg.get("openai_model", "tts-1")      # tts-1 = budget
            voice = tts_cfg.get("openai_voice", "onyx")       # onyx = deep/gravelly

            response = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format="mp3",
            )
            response.stream_to_file(str(output_path))
            logger.info(f"[TTS/OpenAI] Generated: {output_path}")
            return True
        except Exception as e:
            logger.error(f"[TTS/OpenAI] Failed: {e}")
            return False

    def _elevenlabs_tts(self, text: str, output_path: Path) -> bool:
        """ElevenLabs TTS — higher quality but costs more."""
        try:
            import requests
            voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "")
            api_key = os.environ.get("ELEVENLABS_API_KEY", "")
            if not voice_id or not api_key:
                logger.error("[TTS/ElevenLabs] Missing ELEVENLABS_VOICE_ID or ELEVENLABS_API_KEY")
                return False

            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
            payload = {
                "text": text,
                "model_id": "eleven_turbo_v2",   # cheapest ElevenLabs model
                "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            if resp.status_code == 200:
                output_path.write_bytes(resp.content)
                logger.info(f"[TTS/ElevenLabs] Generated: {output_path}")
                return True
            else:
                logger.error(f"[TTS/ElevenLabs] HTTP {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"[TTS/ElevenLabs] Failed: {e}")
            return False

    def _piper_tts(self, text: str, output_path: Path) -> bool:
        """
        Piper TTS — fully local, completely free.
        Requires piper binary installed. Lower expressiveness than cloud options.
        """
        try:
            tts_cfg = self._get_tts_cfg()
            model = tts_cfg.get("piper_model", "en_US-danny-low")
            wav_path = output_path.with_suffix(".wav")

            cmd = ["piper", "--model", model, "--output_file", str(wav_path)]
            result = subprocess.run(
                cmd, input=text, text=True, capture_output=True, timeout=60
            )
            if result.returncode != 0:
                logger.error(f"[TTS/Piper] Error: {result.stderr}")
                return False

            # Convert wav to mp3 for consistency
            mp3_cmd = [
                "ffmpeg", "-y", "-i", str(wav_path),
                "-codec:a", "libmp3lame", "-b:a", "128k",
                str(output_path)
            ]
            subprocess.run(mp3_cmd, capture_output=True, timeout=30)
            wav_path.unlink(missing_ok=True)
            return output_path.exists()
        except Exception as e:
            logger.error(f"[TTS/Piper] Failed: {e}")
            return False


# ─── Icecast Streamer ─────────────────────────────────────────────────────────

class IcecastStreamer:
    """
    Streams audio files to an Icecast2 server using ffmpeg.
    Compatible with Linux (Ubuntu/VirtualBox) and any system with ffmpeg installed.
    """

    def __init__(self):
        cfg = _load_config()
        stream_cfg = cfg.get("stream", {})
        self.host = os.environ.get("ICECAST_HOST", "icecast")
        self.port = int(os.environ.get("ICECAST_PORT", "8000"))
        self.password = os.environ.get("ICECAST_PASSWORD", "hackme")
        self.mount = os.environ.get("ICECAST_MOUNT", "/radio")
        self.bitrate = stream_cfg.get("quality", 128)
        self._process: Optional[subprocess.Popen] = None

    def stream_file(self, file_path: Path, block: bool = True) -> bool:
        """
        Stream a single audio file to Icecast.
        If block=False, returns immediately (fire-and-forget).
        """
        if not file_path.exists():
            logger.error(f"[Stream] File not found: {file_path}")
            return False

        icecast_url = (
            f"icecast://source:{self.password}@{self.host}:{self.port}{self.mount}"
        )

        cmd = [
            "ffmpeg",
            "-re",                          # real-time playback rate
            "-i", str(file_path),
            "-vn",                          # no video
            "-codec:a", "libmp3lame",
            "-b:a", f"{self.bitrate}k",
            "-content_type", "audio/mpeg",
            "-f", "mp3",
            icecast_url,
            "-y",
        ]

        logger.info(f"[Stream] Streaming: {file_path.name}")
        try:
            if block:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return result.returncode == 0
            else:
                self._process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
        except Exception as e:
            logger.error(f"[Stream] ffmpeg error: {e}")
            return False

    def stop(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process = None


# ─── Cache Cleanup ───────────────────────────────────────────────────────────

def cleanup_cache(max_files: int = 50):
    """
    Remove oldest cached audio files if cache exceeds max_files.
    Keeps the cache lean to avoid filling up VirtualBox disk space.
    """
    files = sorted(CACHE_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime)
    if len(files) > max_files:
        to_delete = files[:len(files) - max_files]
        for f in to_delete:
            f.unlink(missing_ok=True)
            logger.info(f"[Cache] Removed old file: {f.name}")
