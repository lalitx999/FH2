from chatbot.models import ChatMessage

HISTORY_LIMIT = 30
SUGGESTION_FIELDS = ("suggestions__category", "suggestions__location")


def _with_suggestions(queryset):
    return queryset.prefetch_related(*SUGGESTION_FIELDS)


def history(session):
    if session is None:
        return []
    recent = _with_suggestions(session.messages.order_by("-id"))[:HISTORY_LIMIT]
    return list(reversed(recent))


def message_for_session(session, message_id):
    if session is None:
        return None
    return _with_suggestions(ChatMessage.objects.filter(pk=message_id, session=session)).first()
