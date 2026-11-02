import requests
from django.conf import settings

from .base import LLMProvider, ProviderError

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, config):
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "")

    def is_configured(self):
        return bool(self.api_key and self.model)

    def generate(self, system, messages):
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages
            ],
        }
        try:
            response = requests.post(
                f"{BASE_URL}/{self.model}:generateContent", json=payload,
                headers={"x-goog-api-key": self.api_key}, timeout=settings.LLM_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            parts = response.json()["candidates"][0]["content"]["parts"]
            return "".join(part.get("text", "") for part in parts)
        except requests.RequestException as exc:
            raise ProviderError(f"gemini: {type(exc).__name__}") from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("gemini: รูปแบบคำตอบไม่ถูกต้อง") from None
