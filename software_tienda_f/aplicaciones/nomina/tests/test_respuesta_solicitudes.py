from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from aplicaciones.gestion_usuario.models import Usuario
from aplicaciones.nomina.models import Nomina, Solicitud
from aplicaciones.nomina.services import generar_prenomina, aceptar_prenomina, rechazar_prenomina


class RespuestaSolicitudesTest(CasoPruebaMixin, TestCase):
    def setUp(self):
        self.empleado = Usuario.objects.create_user(username='empleado-resp', email='empleado-resp@example.com', password='ClaveSegura1', salario_base=Decimal('1000000'))
        self.gerente = Usuario.objects.create_user(username='gerente-resp', email='gerente-resp@example.com', password='ClaveSegura1')
        self.auxiliar = Usuario.objects.create_user(username='auxiliar-resp', email='auxiliar-resp@example.com', password='ClaveSegura1')
        self.empleado.groups.add(Group.objects.get_or_create(name='Vendedor')[0])
        self.gerente.groups.add(Group.objects.get_or_create(name='Gerente')[0])
        self.auxiliar.groups.add(Group.objects.get_or_create(name='Auxiliar Administrativo')[0])

    def responder(self, tipo, accion, motivo=''):
        self.client.force_login(self.auxiliar)
        solicitud = Solicitud.objects.create(usuario=self.empleado, tipo=tipo, fecha_desde=timezone.localdate(), fecha_hasta=timezone.localdate())
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('bandeja_aprobacion'), {
                'solicitud_id': solicitud.pk, 'accion': accion, 'motivo_rechazo': motivo,
            })
        solicitud.refresh_from_db()
        return solicitud

    @caso('RF-007', 'Validar que aprobar vacaciones cambie su estado a aceptada.',
          'Solicitud de vacaciones; el Auxiliar aprueba', 'Estado = ACEPTADA')
    def test_aprobar_vacaciones_cambia_estado(self):
        solicitud = self.responder(Solicitud.Tipo.VACACIONES, 'aprobar')
        self.obtenido(f'Estado = {solicitud.estado}')
        self.assertEqual(solicitud.estado, Solicitud.Estado.ACEPTADA)

    @caso('RF-007', 'Validar que la respuesta registre la fecha y quién respondió.',
          'Solicitud de vacaciones aprobada por el Auxiliar', 'fecha_respuesta con valor; respondida_por = Auxiliar')
    def test_respuesta_registra_fecha_y_responsable(self):
        solicitud = self.responder(Solicitud.Tipo.VACACIONES, 'aprobar')
        self.obtenido(f'Fecha respuesta: {solicitud.fecha_respuesta}; respondida por: {solicitud.respondida_por}')
        self.assertTrue(solicitud.fecha_respuesta is not None and solicitud.respondida_por == self.auxiliar)

    @caso('RF-007', 'Validar que al aprobar vacaciones se notifique al empleado por correo.',
          'Solicitud de vacaciones aprobada', '1 correo al empleado con "aceptada" en el asunto')
    def test_aprobar_vacaciones_notifica_empleado(self):
        self.responder(Solicitud.Tipo.VACACIONES, 'aprobar')
        correo = mail.outbox[0] if mail.outbox else None
        self.obtenido(f'Correos: {len(mail.outbox)}; para: {correo.to if correo else "-"}; asunto: {correo.subject if correo else "-"}')
        self.assertTrue(len(mail.outbox) == 1 and correo.to == [self.empleado.email] and 'aceptada' in correo.subject)

    @caso('RF-007', 'Validar que el rechazo de vacaciones notifique el motivo al empleado.',
          "Rechazo de vacaciones con motivo 'Fechas no disponibles'", 'Correo al empleado que incluye el motivo')
    def test_rechazar_vacaciones_notifica_motivo(self):
        self.responder(Solicitud.Tipo.VACACIONES, 'rechazar', 'Fechas no disponibles')
        cuerpo = mail.outbox[0].body if mail.outbox else ''
        self.obtenido(f'Correos: {len(mail.outbox)}; motivo en el correo: {"Fechas no disponibles" in cuerpo}')
        self.assertIn('Fechas no disponibles', cuerpo)

    @caso('RF-003', 'Validar que al aprobar un certificado se notifique al empleado.',
          'Solicitud de certificado aprobada', '1 correo al empleado con "aceptada" en el asunto')
    def test_aprobar_certificado_notifica_empleado(self):
        self.responder(Solicitud.Tipo.CERTIFICADO, 'aprobar')
        correo = mail.outbox[0] if mail.outbox else None
        self.obtenido(f'Correos: {len(mail.outbox)}; para: {correo.to if correo else "-"}; asunto: {correo.subject if correo else "-"}')
        self.assertTrue(len(mail.outbox) == 1 and correo.to == [self.empleado.email] and 'aceptada' in correo.subject)

    @caso('RF-003', 'Validar que el rechazo de un certificado notifique el motivo.',
          "Rechazo de certificado con motivo 'Falta soporte'", 'Correo al empleado que incluye el motivo')
    def test_rechazar_certificado_notifica_motivo(self):
        solicitud = self.responder(Solicitud.Tipo.CERTIFICADO, 'rechazar', 'Falta soporte')
        cuerpo = mail.outbox[0].body if mail.outbox else ''
        self.obtenido(f'Estado: {solicitud.estado}; motivo en el correo: {"Falta soporte" in cuerpo}')
        self.assertIn('Falta soporte', cuerpo)

    @caso('RF-007', 'Validar que al aceptar la pre-nómina se notifique al Gerente que la calculó.',
          'Pre-nómina 2026-08 generada por el Gerente y aceptada por el Auxiliar', '1 correo dirigido al Gerente')
    def test_aceptar_prenomina_notifica_gerente(self):
        solicitud = generar_prenomina('2026-08', self.gerente)
        with self.captureOnCommitCallbacks(execute=True):
            aceptar_prenomina(solicitud, self.auxiliar)
        destinos = [c.to for c in mail.outbox]
        self.obtenido(f'Correos enviados a: {destinos}')
        self.assertEqual(destinos, [[self.gerente.email]])

    @caso('RF-007', 'Validar que el rechazo de la pre-nómina notifique el motivo al Gerente.',
          "Pre-nómina 2026-07 rechazada con motivo 'Revisar valores'", 'Correo al Gerente que incluye el motivo')
    def test_rechazar_prenomina_notifica_motivo(self):
        solicitud = generar_prenomina('2026-07', self.gerente)
        with self.captureOnCommitCallbacks(execute=True):
            rechazar_prenomina(solicitud, self.auxiliar, 'Revisar valores')
        cuerpo = mail.outbox[0].body if mail.outbox else ''
        self.obtenido(f'Correos: {len(mail.outbox)}; motivo en el correo: {"Revisar valores" in cuerpo}')
        self.assertIn('Revisar valores', cuerpo)

    def historial_rechazado(self):
        solicitud = Solicitud.objects.create(
            usuario=self.empleado, tipo=Solicitud.Tipo.CERTIFICADO,
            estado=Solicitud.Estado.RECHAZADA, motivo_rechazo='Documento incompleto',
            fecha_respuesta=timezone.now(), respondida_por=self.auxiliar,
        )
        self.client.force_login(self.empleado)
        return solicitud, self.client.get(reverse('nomina_historial'))

    @caso('RF-004', 'Validar que el historial muestre el motivo del rechazo.',
          "Solicitud rechazada con motivo 'Documento incompleto'", "El historial muestra 'Documento incompleto'")
    def test_historial_presenta_motivo(self):
        _, respuesta = self.historial_rechazado()
        self.obtenido(f"HTTP {respuesta.status_code}; motivo visible: {'Documento incompleto' in respuesta.content.decode()}")
        self.assertContains(respuesta, 'Documento incompleto')

    @caso('RF-004', 'Validar que el historial muestre la fecha y hora de la respuesta.',
          'Solicitud respondida ahora', 'El historial muestra la fecha en formato dd/mm/aaaa hh:mm')
    def test_historial_presenta_fecha_respuesta(self):
        solicitud, respuesta = self.historial_rechazado()
        fecha = timezone.localtime(solicitud.fecha_respuesta).strftime('%d/%m/%Y %H:%M')
        self.obtenido(f'Fecha {fecha} visible: {fecha in respuesta.content.decode()}')
        self.assertContains(respuesta, fecha)

    def consultar_con_novedades(self):
        Nomina.objects.create(
            usuario=self.empleado, periodo=timezone.localdate().strftime('%Y-%m'),
            salario_bruto=Decimal('1000000'), valor_bonificacion=Decimal('125000'),
            valor_horas_extra=Decimal('45000'), deducciones=Decimal('80000'),
            deduccion_salud=Decimal('40000'), deduccion_pension=Decimal('40000'),
            total_pagar=Decimal('1090000'), estado=Nomina.Estado.ACEPTADA,
        )
        self.client.force_login(self.empleado)
        return self.client.get(reverse('nomina_consultar'))

    @caso('RF-004', 'Validar que la consulta de nómina muestre la bonificación del empleado.',
          'Nómina aceptada con bonificación 125.000', "La consulta muestra 'Bonificaciones' y '125.000'")
    def test_consulta_muestra_bonificacion(self):
        respuesta = self.consultar_con_novedades()
        html = respuesta.content.decode()
        self.obtenido(f"'Bonificaciones' visible: {'Bonificaciones' in html}; '125.000' visible: {'125.000' in html}")
        self.assertTrue('Bonificaciones' in html and '125.000' in html)

    @caso('RF-004', 'Validar que la consulta de nómina muestre las horas extra del empleado.',
          'Nómina aceptada con horas extra 45.000', "La consulta muestra 'Horas extra' y '45.000'")
    def test_consulta_muestra_horas_extra(self):
        respuesta = self.consultar_con_novedades()
        html = respuesta.content.decode()
        self.obtenido(f"'Horas extra' visible: {'Horas extra' in html}; '45.000' visible: {'45.000' in html}")
        self.assertTrue('Horas extra' in html and '45.000' in html)
