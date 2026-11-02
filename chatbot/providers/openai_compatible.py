import requests
from django.conf import settings

from .base import LLMProvider, ProviderError

MAX_TOKENS = 1000


class OpenAICompatibleProvider(LLMProvider):
    """DeepSeek, Groq และ LLM ภายในที่เปิด API แบบ /chat/completions"""

    def __init__(self, name, config, requires_key=True):
        self.name = name
        self.base_url = config.get("base_url", "").rstrip("/")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "")
        self.requires_key = requires_key

    def is_configured(self):
        return bool(self.base_url and self.model and (self.api_key or not self.requires_key))

    def generate(self, system, messages):
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except requests.RequestException as exc:
            raise ProviderError(f"{self.name}: {type(exc).__name__}") from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError(f"{self.name}: รูปแบบคำตอบไม่ถูกต้อง") from None
