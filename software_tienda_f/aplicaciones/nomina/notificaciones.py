from django.conf import settings
from django.core.mail import send_mail


def notificar_respuesta_solicitud(solicitud):
    destinatario = solicitud.usuario.email
    if not destinatario:
        return
    estado = solicitud.get_estado_display().lower()
    tipo = solicitud.get_tipo_display()
    asunto = 'Tu solicitud de {0} fue {1}'.format(tipo, estado)
    lineas = ['Tu solicitud de {0} fue {1}.'.format(tipo.lower(), estado)]
    if solicitud.fecha_desde or solicitud.fecha_hasta:
        if solicitud.fecha_desde and solicitud.fecha_hasta and solicitud.fecha_desde != solicitud.fecha_hasta:
            lineas.append('Fechas: del {0} al {1}.'.format(solicitud.fecha_desde.strftime('%d/%m/%Y'), solicitud.fecha_hasta.strftime('%d/%m/%Y')))
        else:
            fecha = solicitud.fecha_desde or solicitud.fecha_hasta
            lineas.append('Fecha: {0}.'.format(fecha.strftime('%d/%m/%Y')))
    if solicitud.periodo:
        lineas.append('Período: {0}.'.format(solicitud.periodo))
    lineas.append('Estado: {0}.'.format(solicitud.get_estado_display()))
    if solicitud.estado == solicitud.Estado.RECHAZADA:
        lineas.append('Motivo: {0}.'.format(solicitud.motivo_rechazo or 'Sin motivo especificado'))
    send_mail(asunto, '\n'.join(lineas), settings.DEFAULT_FROM_EMAIL, [destinatario], fail_silently=True)
