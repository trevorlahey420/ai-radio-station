"""
LLM Router — routes tasks to appropriate LLM providers and models.
Respects budget_mode from config/preferences.yaml.
Budget mode (default ON): uses gpt-4o-mini for all roles.
"""

import os
import yaml
from enum import Enum
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path(__file__).parents[2] / "config" / "preferences.yaml"


class LLMRole(Enum):
    PLAYLIST = "playlist"
    DJ_SCRIPT = "dj_script"
    NEWS = "news"
    MODERATION = "moderation"


def _load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def _resolve_model(role: LLMRole, cfg: dict) -> str:
    """
    Determine which model to use for a given role.
    Budget mode always uses the budget_model (gpt-4o-mini).
    If budget_mode is off, checks for per-role overrides, then falls back to quality_model.
    """
    llm_cfg = cfg.get("llm", {})
    budget_mode = cfg.get("budget_mode", True)  # DEFAULT: budget mode ON

    # Budget mode: always use the cheapest model regardless of role
    if budget_mode:
        return llm_cfg.get("budget_model", "gpt-4o-mini")

    # Quality mode: check for per-role override first
    role_key = f"{role.value}_model"
    role_override = llm_cfg.get(role_key, "")
    if role_override:
        return role_override

    # Fall back to quality model
    return llm_cfg.get("quality_model", "gpt-4o")


class LLMRouter:
    """
    Routes LLM calls to the correct provider and model based on role and config.
    Supports: openai, anthropic, local (stub).
    """

    def __init__(self):
        self._cfg = _load_config()
        self._provider = self._cfg.get("llm", {}).get("provider", "openai")
        self._clients = {}
        self._init_clients()

    def _init_clients(self):
        if self._provider == "openai":
            try:
                from openai import OpenAI
                self._clients["openai"] = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
            except Exception as e:
                print(f"[LLMRouter] OpenAI init failed: {e}")

        elif self._provider == "anthropic":
            try:
                import anthropic
                self._clients["anthropic"] = anthropic.Anthropic(
                    api_key=os.environ["ANTHROPIC_API_KEY"]
                )
            except Exception as e:
                print(f"[LLMRouter] Anthropic init failed: {e}")

    def reload_config(self):
        """Hot-reload config — called when preferences.yaml changes."""
        self._cfg = _load_config()
        self._provider = self._cfg.get("llm", {}).get("provider", "openai")

    def complete(
        self,
        role: LLMRole,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Send a completion request for a given role.
        Automatically selects model based on budget_mode.
        Returns the response text.
        """
        self.reload_config()
        model = _resolve_model(role, self._cfg)

        if self._provider == "openai":
            return self._openai_complete(model, system_prompt, user_prompt, temperature, max_tokens)
        elif self._provider == "anthropic":
            return self._anthropic_complete(model, system_prompt, user_prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {self._provider}")

    def _openai_complete(
        self, model: str, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int
    ) -> str:
        client = self._clients.get("openai")
        if not client:
            raise RuntimeError("OpenAI client not initialized")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()

    def _anthropic_complete(
        self, model: str, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int
    ) -> str:
        client = self._clients.get("anthropic")
        if not client:
            raise RuntimeError("Anthropic client not initialized")

        # Map OpenAI model names to Anthropic equivalents if needed
        if "gpt" in model:
            model = "claude-3-haiku-20240307"  # budget Anthropic equivalent

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=temperature,
        )
        return response.content[0].text.strip()

    def get_active_model(self, role: LLMRole) -> str:
        """Returns the model name that would be used for a given role (useful for logging)."""
        self.reload_config()
        return _resolve_model(role, self._cfg)

    def is_budget_mode(self) -> bool:
        self.reload_config()
        return self._cfg.get("budget_mode", True)


# Singleton
_router_instance: Optional[LLMRouter] = None


def get_router() -> LLMRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouter()
    return _router_instance
