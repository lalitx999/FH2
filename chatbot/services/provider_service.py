from django.conf import settings

from chatbot.providers.claude import ClaudeProvider
from chatbot.providers.gemini import GeminiProvider
from chatbot.providers.openai_compatible import OpenAICompatibleProvider

PROVIDER_NAMES = ("local", "claude", "deepseek", "groq", "gemini")


def _build(name):
    config = settings.LLM_CONFIG[name]
    if name == "claude":
        return ClaudeProvider(config)
    if name == "gemini":
        return GeminiProvider(config)
    return OpenAICompatibleProvider(name, config, requires_key=name != "local")


def active_providers():
    """ผู้ให้บริการตามลำดับใน LLM_PROVIDERS เฉพาะที่ตั้งค่าครบ"""
    providers = [_build(name) for name in settings.LLM_PROVIDERS if name in PROVIDER_NAMES]
    return [provider for provider in providers if provider.is_configured()]


def provider_status():
    """สำหรับหน้าแอดมิน ไม่คืนค่า key ใด ๆ"""
    return [
        {"name": name, "enabled": name in settings.LLM_PROVIDERS, "configured": _build(name).is_configured()}
        for name in PROVIDER_NAMES
    ]
