"""
LLM Router — Multi-provider abstraction layer
Routes different tasks to different LLM providers/models.

Supported providers:
  - openai      (GPT-4o, GPT-4-turbo, etc.)
    - anthropic   (Claude 3.5 Sonnet, Haiku, etc.)
      - local       (Ollama / llama.cpp compatible)

      Each task role maps to a specific provider + model configured via
      environment variables or the llm_config dict below.
      """

from __future__ import annotations

import os
import logging
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class LLMRole(str, Enum):
      PLAYLIST    = "playlist"       # Structured reasoning for track selection
    DJ_SCRIPT   = "dj_script"     # Creative, expressive DJ persona writing
    NEWS        = "news"           # Accurate summarization + light styling
    MODERATION  = "moderation"    # Sanity / structure checking


# ── DEFAULT MODEL ROUTING MAP ─────────────────────────────────────────────────
# Override any of these with environment variables:
#   LLM_PLAYLIST_PROVIDER, LLM_PLAYLIST_MODEL
#   LLM_DJ_PROVIDER,       LLM_DJ_MODEL
#   LLM_NEWS_PROVIDER,     LLM_NEWS_MODEL
#   LLM_MOD_PROVIDER,      LLM_MOD_MODEL

DEFAULT_ROUTING: dict[str, dict] = {
      LLMRole.PLAYLIST: {
                "provider": os.getenv("LLM_PLAYLIST_PROVIDER", "openai"),
                "model":    os.getenv("LLM_PLAYLIST_MODEL",    "gpt-4o"),
                "temperature": 0.4,
                "max_tokens": 2048,
      },
      LLMRole.DJ_SCRIPT: {
                "provider": os.getenv("LLM_DJ_PROVIDER",   "anthropic"),
                "model":    os.getenv("LLM_DJ_MODEL",       "claude-3-5-sonnet-20241022"),
                "temperature": 1.0,
                "max_tokens": 4096,
      },
      LLMRole.NEWS: {
                "provider": os.getenv("LLM_NEWS_PROVIDER", "openai"),
                "model":    os.getenv("LLM_NEWS_MODEL",    "gpt-4o-mini"),
                "temperature": 0.3,
                "max_tokens": 1024,
      },
      LLMRole.MODERATION: {
                "provider": os.getenv("LLM_MOD_PROVIDER", "openai"),
                "model":    os.getenv("LLM_MOD_MODEL",    "gpt-4o-mini"),
                "temperature": 0.0,
                "max_tokens": 512,
      },
}


class LLMRouter:
      """Central router that dispatches LLM calls to the right provider."""

    def __init__(self, routing: Optional[dict] = None):
              self.routing = routing or DEFAULT_ROUTING
              self._clients: dict[str, object] = {}

    # ── CLIENT FACTORY ────────────────────────────────────────────────────────

    def _get_client(self, provider: str):
              if provider in self._clients:
                            return self._clients[provider]

              if provider == "openai":
                            import openai
                            client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
elif provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
elif provider == "local":
            import openai
            # Ollama exposes an OpenAI-compatible endpoint
            client = openai.OpenAI(
                              base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"),
                              api_key="ollama",
            )
else:
            raise ValueError(f"Unknown LLM provider: {provider!r}")

        self._clients[provider] = client
        return client

    # ── MAIN DISPATCH ─────────────────────────────────────────────────────────

    def complete(
              self,
              role: LLMRole,
              system_prompt: str,
              user_message: str,
              **kwargs,
    ) -> str:
              """
                      Send a completion request routed by role.
                              Returns the assistant's text response.
                                      """
              cfg = {**self.routing[role], **kwargs}
              provider = cfg["provider"]
              model    = cfg["model"]

        logger.debug("LLMRouter: role=%s provider=%s model=%s", role, provider, model)

        client = self._get_client(provider)

        if provider in ("openai", "local"):
                      return self._openai_complete(client, cfg, system_prompt, user_message)
elif provider == "anthropic":
              return self._anthropic_complete(client, cfg, system_prompt, user_message)
else:
              raise ValueError(f"No completion handler for provider: {provider!r}")

    def _openai_complete(self, client, cfg: dict, system: str, user: str) -> str:
              resp = client.chat.completions.create(
                            model=cfg["model"],
                            temperature=cfg.get("temperature", 0.7),
                            max_tokens=cfg.get("max_tokens", 1024),
                            messages=[
                                              {"role": "system", "content": system},
                                              {"role": "user",   "content": user},
                            ],
              )
              return resp.choices[0].message.content.strip()

    def _anthropic_complete(self, client, cfg: dict, system: str, user: str) -> str:
              resp = client.messages.create(
                            model=cfg["model"],
                            max_tokens=cfg.get("max_tokens", 1024),
                            temperature=cfg.get("temperature", 0.7),
                            system=system,
                            messages=[{"role": "user", "content": user}],
              )
              return resp.content[0].text.strip()


# ── SINGLETON ─────────────────────────────────────────────────────────────────
_router_instance: Optional[LLMRouter] = None


def get_router() -> LLMRouter:
      global _router_instance
      if _router_instance is None:
                _router_instance = LLMRouter()
            return _router_instance
