from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """Отримує значення з словника за ключем"""
    return dictionary.get(key)
