import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from aplicaciones.gestion_usuario.models import Auditoria, Usuario
from .models import HoraExtra, Nomina, ConfiguracionBonificacion, Solicitud
from .excepciones import (
    HoraExtraInvalidaError, MotivoRechazoRequeridoError, NominaYaCalculadaError,
    PreNominaNoPendienteError, SinEmpleadosActivosError,
)
from .reportes import nombre_periodo
from .notificaciones import notificar_respuesta_solicitud
from .templatetags.formatos import formatear_moneda

JORNADA_DIARIA = Decimal('8.4')
HORA_INICIO_DIURNA = 6
HORA_FIN_DIURNA = 19
PCT_HORA_DIURNA = Decimal('0.006')
PCT_HORA_NOCTURNA = Decimal('0.008')
PCT_SALUD = Decimal('0.04')
PCT_PENSION = Decimal('0.04')
PCT_DEDUCCIONES = PCT_SALUD + PCT_PENSION


def calcular_horas_extra(usuario, fecha, hora_ingreso, hora_salida, motivo):

    if hora_salida <= hora_ingreso:
        raise HoraExtraInvalidaError('La hora de salida debe ser posterior a la hora de ingreso.')

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


def calcular_nomina(usuario, periodo, solicitud=None):
    salario_bruto = Decimal(str(usuario.salario_base))

    config = ConfiguracionBonificacion.objects.filter(usuario=usuario).first()
    bonificacion = Decimal('0')
    if config and config.meta_mensual > 0:
        bonificacion = (config.porcentaje / 100 * config.meta_mensual).quantize(Decimal('0'))

    horas_extra = HoraExtra.objects.filter(usuario=usuario, periodo=periodo)
    total_horas = sum((h.valor for h in horas_extra), Decimal('0'))

    salud = (salario_bruto * PCT_SALUD).quantize(Decimal('0'))
    pension = (salario_bruto * PCT_PENSION).quantize(Decimal('0'))
    deducciones = salud + pension
    total = salario_bruto + bonificacion + total_horas - deducciones

    return Nomina.objects.create(
        usuario=usuario,
        solicitud=solicitud,
        periodo=periodo,
        salario_bruto=salario_bruto,
        valor_bonificacion=bonificacion,
        valor_horas_extra=total_horas,
        deducciones=deducciones,
        deduccion_salud=salud,
        deduccion_pension=pension,
        total_pagar=total,
    )


@transaction.atomic
def generar_prenomina(periodo, calculada_por):
    existentes = Nomina.objects.filter(periodo=periodo)
    if existentes.filter(estado=Nomina.Estado.PENDIENTE).exists():
        raise NominaYaCalculadaError(periodo, 'pendiente de aprobación')
    if existentes.filter(estado=Nomina.Estado.ACEPTADA).exists():
        raise NominaYaCalculadaError(periodo, 'aceptada')
    existentes.filter(estado=Nomina.Estado.RECHAZADA).delete()

    anio, mes = (int(parte) for parte in periodo.split('-'))
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    empleados = Usuario.objects.filter(is_active=True).filter(
        Q(fecha_ingreso__isnull=True) | Q(fecha_ingreso__lte=date(anio, mes, ultimo_dia))
    )
    if not empleados.exists():
        raise SinEmpleadosActivosError(periodo)

    solicitud = Solicitud.objects.create(
        usuario=calculada_por,
        tipo=Solicitud.Tipo.NOMINA,
        periodo=periodo,
        motivo='Pre-nómina {0}: cálculo en curso'.format(nombre_periodo(periodo)),
    )
    nominas = [calcular_nomina(usuario, periodo, solicitud=solicitud) for usuario in empleados]
    total = sum((nomina.total_pagar for nomina in nominas), Decimal('0'))
    motivo = 'Pre-nómina {0}: {1} empleados, total {2}'.format(
        nombre_periodo(periodo), len(nominas), formatear_moneda(total))
    solicitud.motivo = motivo
    solicitud.save(update_fields=['motivo'])
    Auditoria.objects.create(
        usuario=calculada_por,
        accion=Auditoria.Accion.CALCULAR,
        detalle='Calculó la pre-nómina de {0} y la envió a aprobación'.format(periodo),
    )
    return solicitud


def _obtener_prenomina_pendiente(solicitud):
    solicitud = Solicitud.objects.select_for_update().get(pk=solicitud.pk)
    if solicitud.tipo != Solicitud.Tipo.NOMINA:
        raise ValueError('La solicitud no corresponde a una pre-nómina.')
    if solicitud.estado != Solicitud.Estado.PENDIENTE:
        raise PreNominaNoPendienteError(solicitud.get_estado_display().lower())
    return solicitud


@transaction.atomic
def aceptar_prenomina(solicitud, auxiliar):
    solicitud = _obtener_prenomina_pendiente(solicitud)
    solicitud.estado = Solicitud.Estado.ACEPTADA
    solicitud.fecha_respuesta = timezone.now()
    solicitud.respondida_por = auxiliar
    solicitud.save(update_fields=['estado', 'fecha_respuesta', 'respondida_por'])
    nominas = Nomina.objects.select_for_update().filter(
        solicitud=solicitud, estado=Nomina.Estado.PENDIENTE)
    fecha_revision = timezone.now()
    cantidad = 0
    for nomina in nominas:
        nomina.estado = Nomina.Estado.ACEPTADA
        nomina.revisada_por = auxiliar
        nomina.fecha_revision = fecha_revision
        nomina.save(update_fields=['estado', 'revisada_por', 'fecha_revision'])
        Usuario.objects.filter(pk=nomina.usuario_id).update(
            ultimo_periodo_pagado=nomina.periodo,
            ultimo_total_pagado=nomina.total_pagar,
        )
        cantidad += 1
    Auditoria.objects.create(
        usuario=auxiliar,
        accion=Auditoria.Accion.ACTUALIZAR,
        detalle='Aceptó la pre-nómina de {0}'.format(solicitud.periodo),
    )
    transaction.on_commit(lambda: notificar_respuesta_solicitud(solicitud))
    return cantidad


@transaction.atomic
def rechazar_prenomina(solicitud, auxiliar, motivo):
    motivo = (motivo or '').strip()
    if not motivo:
        raise MotivoRechazoRequeridoError()
    solicitud = _obtener_prenomina_pendiente(solicitud)
    motivo = motivo[:200]
    solicitud.estado = Solicitud.Estado.RECHAZADA
    solicitud.motivo_rechazo = motivo
    solicitud.fecha_respuesta = timezone.now()
    solicitud.respondida_por = auxiliar
    solicitud.save(update_fields=['estado', 'motivo_rechazo', 'fecha_respuesta', 'respondida_por'])
    fecha_revision = timezone.now()
    Nomina.objects.select_for_update().filter(
        solicitud=solicitud, estado=Nomina.Estado.PENDIENTE).update(
            estado=Nomina.Estado.RECHAZADA,
            revisada_por=auxiliar,
            fecha_revision=fecha_revision,
            motivo_rechazo=motivo,
        )
    Auditoria.objects.create(
        usuario=auxiliar,
        accion=Auditoria.Accion.ACTUALIZAR,
        detalle='Rechazó la pre-nómina de {0}: {1}'.format(solicitud.periodo, motivo),
    )
    transaction.on_commit(lambda: notificar_respuesta_solicitud(solicitud))
