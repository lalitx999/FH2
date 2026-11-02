import anthropic
from django.conf import settings

from .base import LLMProvider, ProviderError

MAX_TOKENS = 4000


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, config):
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "")

    def is_configured(self):
        return bool(self.api_key and self.model)

    def generate(self, system, messages):
        client = anthropic.Anthropic(api_key=self.api_key, timeout=settings.LLM_TIMEOUT_SECONDS, max_retries=1)
        try:
            response = client.beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=messages,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError:
            raise ProviderError("claude: ถูกจำกัดอัตราการเรียก") from None
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"claude: HTTP {exc.status_code}") from None
        except anthropic.APIConnectionError:
            raise ProviderError("claude: เชื่อมต่อไม่ได้") from None
        if response.stop_reason == "refusal":
            raise ProviderError("claude: ปฏิเสธการตอบ")
        return "".join(block.text for block in response.content if block.type == "text")
