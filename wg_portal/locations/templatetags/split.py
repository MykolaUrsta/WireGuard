from django import template

register = template.Library()

@register.filter
def trim(value):
    """Обрізає пробіли з початку і кінця рядка"""
    if not isinstance(value, str):
        return value
    return value.strip()

@register.filter
def split(value, delimiter=','):
    """Розбиває рядок по роздільнику (за замовчуванням кома)"""
    if not value:
        return []
    return [v.strip() for v in value.split(delimiter)]
