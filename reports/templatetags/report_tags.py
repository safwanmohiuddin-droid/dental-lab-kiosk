from django import template
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def fmt(value, measure):
    """Cost with 2 decimals, quantities as written (up to 3), empty as a dash."""
    if value is None:
        return "-"
    return floatformat(value, "2g" if measure == "cost" else "-3g")
