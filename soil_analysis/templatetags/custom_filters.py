from django import template

register = template.Library()


@register.filter
def get_value(value, key):
    if key in value:
        return value[key]
    else:
        return None
