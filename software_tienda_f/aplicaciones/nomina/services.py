from datetime import datetime, timedelta
from decimal import Decimal
from .models import HoraExtra, Nomina, ConfiguracionBonificacion

JORNADA_DIARIA = Decimal('8.4')
HORA_INICIO_DIURNA = 6
HORA_FIN_DIURNA = 19
PCT_HORA_DIURNA = Decimal('0.006')
PCT_HORA_NOCTURNA = Decimal('0.008')
PCT_DEDUCCIONES = Decimal('0.08')


def calcular_horas_extra(usuario, fecha, hora_ingreso, hora_salida, motivo):

    if hora_salida <= hora_ingreso:
        raise ValueError('La hora de salida debe ser posterior a la de ingreso.')

    delta = (datetime.combine(fecha, hora_salida) - datetime.combine(fecha, hora_ingreso))
    horas_trabajadas = Decimal(str(delta.total_seconds() / 3600)).quantize(Decimal('0.1'))
    horas_extra = max(horas_trabajadas - JORNADA_DIARIA, Decimal('0'))

    if horas_extra == 0:
        return None

    es_diurna = HORA_INICIO_DIURNA <= hora_salida.hour < HORA_FIN_DIURNA

    salario_bruto = Decimal(str(usuario.salario_base))
    pct = PCT_HORA_DIURNA if es_diurna else PCT_HORA_NOCTURNA
    valor = (horas_extra * salario_bruto * pct).quantize(Decimal('0'))

    return HoraExtra.objects.create(
        usuario=usuario,
        fecha=fecha,
        hora_ingreso=hora_ingreso,
        hora_salida=hora_salida,
        tipo=HoraExtra.Tipo.DIURNA if es_diurna else HoraExtra.Tipo.NOCTURNA,
        cantidad_horas=horas_extra,
        valor=valor,
        motivo=motivo,
        periodo=fecha.strftime('%Y-%m'),
    )


def calcular_nomina(usuario, periodo):
    salario_bruto = Decimal(str(usuario.salario_base))

    config = ConfiguracionBonificacion.objects.filter(usuario=usuario).first()
    bonificacion = Decimal('0')
    if config and config.meta_mensual > 0:
        bonificacion = (config.porcentaje / 100 * config.meta_mensual).quantize(Decimal('0'))

    horas_extra = HoraExtra.objects.filter(usuario=usuario, periodo=periodo)
    total_horas = sum((h.valor for h in horas_extra), Decimal('0'))

    deducciones = (salario_bruto * PCT_DEDUCCIONES).quantize(Decimal('0'))
    total = salario_bruto + bonificacion + total_horas - deducciones

    nomina, creado = Nomina.objects.update_or_create(
        usuario=usuario,
        periodo=periodo,
        defaults={
            'salario_bruto': salario_bruto,
            'valor_bonificacion': bonificacion,
            'valor_horas_extra': total_horas,
            'deducciones': deducciones,
            'total_pagar': total,
        },
    )
    return nomina