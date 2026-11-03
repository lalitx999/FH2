from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from kombu.exceptions import OperationalError

from chatbot.models import ChatMessage
from chatbot.providers.base import ProviderError
from chatbot.services import chat_service, knowledge_service, provider_service
from properties.models import Category, Location, Property


def make_property(**extra):
    defaults = {
        "title": "คอนโดใกล้รถไฟฟ้า", "description": "ห้องสวย", "price": 15000, "property_type": Property.Type.RENT,
        "category": Category.objects.get(slug="condo"), "location": Location.objects.get_or_create(name="อโศก")[0],
        "status": Property.Status.PUBLISHED, "bedrooms": 1, "seller_name": "คุณผู้ขายลับ", "seller_phone": "0899999999",
    }
    return Property.objects.create(**{**defaults, **extra})


class ChatTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.prop = make_property()

    def send(self, message):
        return self.client.post("/chat/send/", {"message": message})


class AnalyzeTests(ChatTestCase):
    def test_finds_listing_by_reference_code(self):
        prop = make_property(reference_code="FH040")
        query = knowledge_service.analyze("ขอรายละเอียด fh040")
        self.assertEqual(query.code, "FH040")
        self.assertEqual(knowledge_service.find_properties(query), [prop])

    def test_reads_type_category_location_budget_and_bedrooms(self):
        query = knowledge_service.analyze("หาคอนโดให้เช่า แถวอโศก 2 ห้องนอน งบ 2 หมื่น")
        self.assertEqual(query.property_type, Property.Type.RENT)
        self.assertEqual(query.category.slug, "condo")
        self.assertEqual(query.location.name, "อโศก")
        self.assertEqual(query.max_price, 20000)
        self.assertEqual(query.bedrooms, 2)

    def test_townhome_is_not_read_as_house_and_consign_is_not_a_search(self):
        self.assertEqual(knowledge_service.analyze("ทาวน์โฮมบ้านกลางเมือง").category.slug, "townhome")
        query = knowledge_service.analyze("อยากฝากขายบ้าน")
        self.assertEqual(query.intent, "consign")
        self.assertFalse(query.has_criteria)

    def test_only_published_properties_are_found_or_given_to_llm(self):
        hidden = make_property(title="ทรัพย์ฉบับร่าง", status=Property.Status.DRAFT)
        found = knowledge_service.find_properties(knowledge_service.analyze("คอนโดให้เช่า"))
        self.assertEqual(found, [self.prop])
        self.assertEqual(knowledge_service.find_properties(knowledge_service.analyze(hidden.property_code)), [])
        prompt = knowledge_service.build_system_prompt(found)
        self.assertIn(self.prop.property_code, prompt)
        self.assertNotIn("0899999999", prompt)
        self.assertNotIn("คุณผู้ขายลับ", prompt)


class SendTests(ChatTestCase):
    def test_rule_based_reply_with_property_card_when_no_provider_configured(self):
        response = self.send("หาคอนโดให้เช่า")
        self.assertContains(response, self.prop.title)
        self.assertContains(response, "/properties/?type=RENT&amp;category=condo")
        answer = ChatMessage.objects.get(role=ChatMessage.Role.ASSISTANT)
        self.assertEqual(answer.status, ChatMessage.Status.DONE)
        self.assertEqual(answer.provider, "rule_based")

    def test_message_is_escaped(self):
        response = self.send("<script>alert(1)</script>")
        self.assertNotContains(response, "<script>alert")

    def test_rejects_empty_and_too_long_messages(self):
        self.assertEqual(self.send("  ").status_code, 400)
        self.assertEqual(self.send("ก" * 501).status_code, 400)
        self.assertFalse(ChatMessage.objects.exists())

    def test_session_rate_limit(self):
        statuses = [self.send("สวัสดี").status_code for _ in range(21)]
        self.assertEqual(statuses[:20], [200] * 20)
        self.assertEqual(statuses[20], 429)

    def test_cannot_read_another_visitors_message(self):
        self.send("สวัสดี")
        answer = ChatMessage.objects.get(role=ChatMessage.Role.ASSISTANT)
        self.assertEqual(self.client.get(f"/chat/messages/{answer.pk}/").status_code, 200)
        self.assertEqual(self.client_class().get(f"/chat/messages/{answer.pk}/").status_code, 404)

    def test_history_belongs_to_the_session(self):
        self.send("ข้อความลับของฉัน")
        self.assertContains(self.client.get("/chat/history/"), "ข้อความลับของฉัน")
        self.assertNotContains(self.client_class().get("/chat/history/"), "ข้อความลับของฉัน")

    @mock.patch("chatbot.tasks.generate_reply_task.delay", side_effect=OperationalError)
    def test_falls_back_to_rules_when_queue_is_down(self, _delay):
        response = self.send("คอนโดให้เช่า")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChatMessage.objects.get(role=ChatMessage.Role.ASSISTANT).provider, "rule_based")

    @mock.patch("chatbot.tasks.generate_reply_task.delay")
    def test_pending_reply_polls_then_blocks_a_second_send(self, _delay):
        self.assertContains(self.send("สวัสดี"), "data-poll-url")
        answer = ChatMessage.objects.get(role=ChatMessage.Role.ASSISTANT)
        self.assertEqual(self.client.get(f"/chat/messages/{answer.pk}/").status_code, 204)
        self.assertEqual(self.send("อีกข้อความ").status_code, 429)

    def test_widget_is_on_the_home_page_only(self):
        self.assertContains(self.client.get("/"), "data-chat-open")
        self.assertNotContains(self.client.get("/properties/"), "data-chat-open")


class FakeProvider:
    def __init__(self, name, result=None):
        self.name, self.result, self.calls = name, result, []

    def generate(self, system, messages):
        self.calls.append((system, messages))
        if self.result is None:
            raise ProviderError(f"{self.name}: ล่ม")
        return self.result


class ProviderFallbackTests(ChatTestCase):
    def reply_with(self, providers, text="คอนโดให้เช่า"):
        with mock.patch.object(provider_service, "active_providers", return_value=providers):
            self.send(text)
        return ChatMessage.objects.filter(role=ChatMessage.Role.ASSISTANT).latest("id")

    def test_uses_next_provider_after_a_failure(self):
        first, second = FakeProvider("local"), FakeProvider("groq", "คำตอบจาก LLM")
        answer = self.reply_with([first, second])
        self.assertEqual((answer.provider, answer.content), ("groq", "คำตอบจาก LLM"))
        self.assertEqual(second.calls[0][1], [{"role": "user", "content": "คอนโดให้เช่า"}])
        self.assertIn(self.prop.property_code, second.calls[0][0])

    def test_ends_with_rules_when_every_provider_fails_or_is_empty(self):
        answer = self.reply_with([FakeProvider("local"), FakeProvider("groq", "  ")])
        self.assertEqual(answer.provider, "rule_based")

    def test_suggestion_cards_come_from_database_not_llm_text(self):
        answer = self.reply_with([FakeProvider("groq", "แนะนำรหัส Z9999 ราคา 1 บาท")])
        self.assertEqual(list(answer.suggestions.all()), [self.prop])

    def test_unexpected_error_closes_the_pending_message(self):
        with mock.patch.object(chat_service, "generate_reply", side_effect=RuntimeError):
            self.send("สวัสดี")
        answer = ChatMessage.objects.get(role=ChatMessage.Role.ASSISTANT)
        self.assertEqual(answer.status, ChatMessage.Status.FAILED)

    @override_settings(LLM_PROVIDERS=["groq", "claude", "unknown"])
    def test_active_providers_needs_complete_config_and_status_hides_keys(self):
        config = {
            "local": {}, "deepseek": {}, "gemini": {}, "claude": {"api_key": "", "model": "m"},
            "groq": {"base_url": "https://x.test", "api_key": "secret-key", "model": "m"},
        }
        with override_settings(LLM_CONFIG=config):
            self.assertEqual([p.name for p in provider_service.active_providers()], ["groq"])
            self.assertNotIn("secret-key", str(provider_service.provider_status()))
