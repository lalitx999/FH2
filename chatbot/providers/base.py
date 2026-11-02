class ProviderError(Exception):
    """ผู้ให้บริการตอบไม่ได้ ให้ลองรายถัดไป ห้ามใส่ API key ในข้อความนี้"""


class LLMProvider:
    name = ""

    def is_configured(self):
        raise NotImplementedError

    def generate(self, system, messages):
        """messages คือ [{"role": "user"|"assistant", "content": str}] คืนข้อความคำตอบ"""
        raise NotImplementedError
