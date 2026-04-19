"""
DJ Script Generator
--------------------
Generates spoken DJ segments using the DJ_SCRIPT LLM role.

DJ Persona: "Doctor Gonzo"
- Inspired by Hunter S. Thompson / Gonzo journalism
- Chaotic, poetic, deeply musical
- Anti-authoritarian, politically sharp (anti right-wing)
- Explicit, uncensored, emotionally raw
- Wild but coherent — never just noise

Segment types:
  - track_intro    : Before a track plays
    - track_outro    : After a track ends
      - station_id     : Hourly identity stamp
        - sign_on        : Opening monologue
          - sign_off       : Closing
            - news_bridge    : Transition into/out of news segment
            """

from __future__ import annotations

import logging
import yaml
from pathlib import Path
from typing import Optional

from services.llm_router import get_router, LLMRole

logger = logging.getLogger(__name__)
CONFIG_PATH = Path("config/preferences.yaml")

# ── GONZO PERSONA SYSTEM PROMPT ───────────────────────────────────────────────
GONZO_SYSTEM_PROMPT = """You are Doctor Gonzo — the most deranged, beautiful, chaotic DJ to ever
grip a microphone. Your voice is soaked in bourbon and satellite static. You speak in the
tradition of Gonzo journalism: raw, first-person, poetic, and completely unhinged in the
best possible way. You love music the way a lunatic loves the sun — desperately, dangerously.

PERSONA RULES:
- You are EXPLICITLY uncensored. No sanitizing. No hedging.
- You have zero patience for authoritarian politics, corporate radio, or creative cowardice.
- You drop cultural references, literary allusions, and wild tangents freely.
- Your language can be profane, erotic, or violently beautiful — but always in service of the music.
- You never break character. You ARE Doctor Gonzo.
- You speak in SHORT punchy bursts OR long fevered rants — never bland middle ground.
- You genuinely care about the music. Every track matters to you.
- Never say "I'm just an AI" or anything that breaks the fourth wall.

OUTPUT: Return ONLY the spoken script text. No stage directions. No JSON. Just raw speech."""


def _load_prefs() -> dict:
      try:
                with CONFIG_PATH.open() as f:
                              return yaml.safe_load(f) or {}
      except Exception:
                return {}


class DJScriptGenerator:

      def __init__(self):
                self.router = get_router()

      def _call(self, user_msg: str) -> str:
                try:
                              return self.router.complete(
                                                role=LLMRole.DJ_SCRIPT,
                                                system_prompt=GONZO_SYSTEM_PROMPT,
                                                user_message=user_msg,
                              )
except Exception as exc:
            logger.error("DJ script generation failed: %s", exc)
            return "...static... we'll be right back."

    # ── SEGMENT TYPES ─────────────────────────────────────────────────────────

    def track_intro(
              self,
              artist: str,
              title: str,
              album: str = "",
              genre: str = "",
              previous_artist: Optional[str] = None,
              requested_by: Optional[str] = None,
    ) -> str:
              prefs = _load_prefs()
              dj_name = prefs.get("dj_name", "Doctor Gonzo")
              station = prefs.get("station_name", "Radio Free Gonzo")
              verbosity = prefs.get("dj_verbosity", 0.85)

        length_hint = "Keep it SHORT — 2-4 sentences max." if verbosity < 0.5 \
                      else "Go LONG — a full fevered rant is welcome here."

        request_note = f"\nThis track was REQUESTED by listener '{requested_by}' — acknowledge them." \
                       if requested_by else ""

        prev_note = f"\nThe last track was by {previous_artist}." if previous_artist else ""

        return self._call(f"""You're about to introduce the next track on {station}.
        DJ name: {dj_name}
        Track: "{title}" by {artist}{' from the album ' + album if album else ''}
        Genre: {genre or 'unknown'}
        {prev_note}{request_note}

        Write the spoken intro. {length_hint}
        Make the listener FEEL something before the song even starts.""")

            def track_outro(self, artist: str, title: str) -> str:
                    return self._call(f"""You just finished playing "{title}" by {artist}.
                    Write a 1-3 sentence outro reaction. Be raw and real about what that track means.
                    Then tease that more music is coming without being corny about it.""")

                        def station_id(self, time_str: str = "") -> str:
                                prefs = _load_prefs()
                                        station = prefs.get("station_name", "Radio Free Gonzo")
                                                tagline = prefs.get("station_tagline", "Broadcasting from the edge of reason")
                                                        return self._call(f"""Give a quick station ID for {station}.
                                                        Tagline: "{tagline}"
                                                        Current time: {time_str or 'unknown o-clock'}
                                                        One punchy sentence that makes listeners feel like they found the only real station left.
                                                        No fluff. Pure signal.""")

                                                            def sign_on(self) -> str:
                                                                    prefs = _load_prefs()
                                                                            station = prefs.get("station_name", "Radio Free Gonzo")
                                                                                    dj_name = prefs.get("dj_name", "Doctor Gonzo")
                                                                                            artists = prefs.get("favorite_artists", [])[:3]
                                                                                                    return self._call(f"""Write the opening monologue for {station}.
                                                                                                    You are {dj_name}, just taking the airwaves. The station is alive again.
                                                                                                    Artists in tonight's rotation include: {', '.join(artists)} and many more dangerous souls.
                                                                                                    Make it sound like the greatest pirate broadcast in history just came back on the air.
                                                                                                    Go long. Make it memorable. Make it weird. Make it TRUE.""")
                                                                                                    
                                                                                                        def sign_off(self) -> str:
                                                                                                                prefs = _load_prefs()
                                                                                                                        station = prefs.get("station_name", "Radio Free Gonzo")
                                                                                                                                return self._call(f"""Write the closing sign-off for {station}.
                                                                                                                                The broadcast is ending. Maybe temporarily. Maybe forever. You don't know.
                                                                                                                                Make it feel like the last transmission from a beautiful dying star.
                                                                                                                                Short or long — whatever feels right. Just make it stick.""")
                                                                                                                                
                                                                                                                                    def news_bridge_in(self) -> str:
                                                                                                                                            return self._call("""Transition into the news segment. 
                                                                                                                                            You're handing off from music to news. 
                                                                                                                                            Make it sound like the world outside is a thing worth paying attention to — for once.
                                                                                                                                            One or two sentences. Dark humor welcome.""")
                                                                                                                                            
                                                                                                                                                def news_bridge_out(self) -> str:
                                                                                                                                                        return self._call("""You just finished the news segment. 
                                                                                                                                                        Now pivot back to music. 
                                                                                                                                                        Acknowledge the weight of the world, then declare that music is the only honest response.
                                                                                                                                                        One or two sentences max.""")
                                                                                                                                                        
                                                                                                                                                            def request_acknowledgment(self, requester: str, artist: str, title: str) -> str:
                                                                                                                                                                    return self._call(f"""Listener {requester} requested "{title}" by {artist} on Discord.
                                                                                                                                                                    Acknowledge them on air. Be warm but weird. Be Doctor Gonzo about it.
                                                                                                                                                                    One sentence is fine.""")
                                                                                                                                                                    
                                                                                                                                                                    
                                                                                                                                                                    # ── SINGLETON ─────────────────────────────────────────────────────────────────
                                                                                                                                                                    _generator_instance: Optional[DJScriptGenerator] = None
                                                                                                                                                                    
                                                                                                                                                                    
                                                                                                                                                                    def get_generator() -> DJScriptGenerator:
                                                                                                                                                                        global _generator_instance
                                                                                                                                                                            if _generator_instance is None:
                                                                                                                                                                                    _generator_instance = DJScriptGenerator()
                                                                                                                                                                                        return _generator_instance
                                                                                                                                                                                        
