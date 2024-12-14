from os.path import splitext

from django import template

register = template.Library()


@register.filter
def split_ext(path):
    _, ext = splitext(path)
    return ext[1:]  # Remove the leading dot ('.jpg' -> 'jpg')
