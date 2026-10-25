from decimal import Decimal

from django.db.models import Count, Sum, Value
from django.db.models.functions import Coalesce

from .models import Nomina


MESES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}


def nombre_periodo(periodo):
    ano, mes = periodo.split('-')
    return '{0} {1}'.format(MESES[int(mes)], ano)


def resumen_mensual(periodo):
    nominas = Nomina.objects.filter(
        periodo=periodo,
        estado=Nomina.Estado.ACEPTADA,
    ).select_related('usuario').order_by('usuario__first_name', 'usuario__last_name')
    cero = Value(Decimal('0'))
    totales = nominas.aggregate(
        empleados=Count('usuario', distinct=True),
        total_salarios=Coalesce(Sum('salario_bruto'), cero),
        total_bonificaciones=Coalesce(Sum('valor_bonificacion'), cero),
        total_horas_extra=Coalesce(Sum('valor_horas_extra'), cero),
        total_salud=Coalesce(Sum('deduccion_salud'), cero),
        total_pension=Coalesce(Sum('deduccion_pension'), cero),
        total_deducciones=Coalesce(Sum('deducciones'), cero),
        total_pagado=Coalesce(Sum('total_pagar'), cero),
    )
    totales['total_devengado'] = (
        totales['total_salarios'] + totales['total_bonificaciones'] + totales['total_horas_extra']
    )
    base = totales['total_pagado'] + totales['total_salud'] + totales['total_pension']
    for clave, valor in (
        ('pct_salud', totales['total_salud']),
        ('pct_pension', totales['total_pension']),
        ('pct_neto', totales['total_pagado']),
    ):
        totales[clave] = (valor * Decimal('100') / base).quantize(Decimal('0.1')) if base else Decimal('0')

    return {
        'periodo': periodo,
        'nombre_periodo': nombre_periodo(periodo),
        'nominas': nominas,
        **totales,
    }
