from django import template

from dashboard.selectors.overview_selector import pending_counts

register = template.Library()


@register.simple_tag
def dashboard_counts():
    return pending_counts()
