"""Backend-only Gemini settings. Never read OpenAI credentials."""
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_MODEL = "gemini-3.8-flash"


@dataclass(frozen=True)
class GeminiSettings:
    api_key: str = field(repr=False)
    model: str = DEFAULT_MODEL


def read_settings(secrets: Mapping, environ: Mapping | None = None) -> GeminiSettings:
    env = os.environ if environ is None else environ
    def text(value):
        return value.strip() if isinstance(value, str) else ""
    key = next((v for v in (
        text(env.get("GEMINI_API_KEY")), text(env.get("GOOGLE_API_KEY")),
        text(secrets.get("GEMINI_API_KEY")), text(secrets.get("GOOGLE_API_KEY"))
    ) if v), "")
    model = text(env.get("GEMINI_MODEL")) or text(secrets.get("GEMINI_MODEL")) or DEFAULT_MODEL
    return GeminiSettings(key, model)
