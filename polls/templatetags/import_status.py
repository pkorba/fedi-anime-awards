from django import template

from polls.models import ImportState

register = template.Library()


@register.simple_tag
def get_import_state():
    return ImportState.objects.filter(pk=1).first()
