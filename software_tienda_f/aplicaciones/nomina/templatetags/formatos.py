from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template


register = template.Library()


def formatear_moneda(valor):
    if valor is None or valor == '':
        return '$0'
    try:
        decimal_valor = Decimal(str(valor))
        if not decimal_valor.is_finite():
            return '$0'
        numero = decimal_valor.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return '$0'
    entero = format(abs(numero), ',f').replace(',', '.')
    if numero < 0:
        return '-${0}'.format(entero)
    return '${0}'.format(entero)


@register.filter(name='moneda')
def moneda(valor):
    return formatear_moneda(valor)
