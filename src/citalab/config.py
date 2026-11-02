"""Configuración única del proyecto, leída de variables de entorno y `.env`."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUTPUT = ROOT / "output"


def _load_env() -> None:
    # En un worktree el .env vive en la carpeta principal del repositorio.
    for candidate in (ROOT / ".env", *[p / ".env" for p in ROOT.parents][:4]):
        if candidate.exists():
            load_dotenv(candidate, override=False)
            return


_load_env()


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str | None
    model: str
    reasoning_effort: str | None = "low"

    @property
    def available(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class Settings:
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    simulator: ProviderConfig | None = None
    timeout_seconds: float = 60.0
    temperature: float = 0.0
    max_output_tokens: int = 1200
    max_attempts: int = 4


def load_settings() -> Settings:
    groq_key = os.getenv("GROQ_API_KEY") or None
    gemini_key = os.getenv("GEMINI_API_KEY") or None
    providers = {
        "groq": ProviderConfig(
            "groq", "https://api.groq.com/openai/v1", groq_key,
            os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"), "low"),
        "google": ProviderConfig(
            "google", "https://generativelanguage.googleapis.com/v1beta/openai", gemini_key,
            os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"), "low"),
    }
    simulator = ProviderConfig(
        "groq", "https://api.groq.com/openai/v1", groq_key,
        os.getenv("SIMULATOR_MODEL", "qwen/qwen3.8-27b"), None)
    return Settings(
        providers=providers,
        simulator=simulator,
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        max_output_tokens=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1200")),
    )
