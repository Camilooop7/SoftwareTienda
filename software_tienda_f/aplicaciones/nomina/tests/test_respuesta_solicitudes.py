from decimal import Decimal

from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from aplicaciones.gestion_usuario.models import Usuario
from aplicaciones.nomina.models import Nomina, Solicitud
from aplicaciones.nomina.services import generar_prenomina, aceptar_prenomina, rechazar_prenomina


class RespuestaSolicitudesTest(TestCase):
    def setUp(self):
        self.empleado = Usuario.objects.create_user(username='empleado-resp', email='empleado-resp@example.com', password='ClaveSegura1', salario_base=Decimal('1000000'))
        self.gerente = Usuario.objects.create_user(username='gerente-resp', email='gerente-resp@example.com', password='ClaveSegura1')
        self.auxiliar = Usuario.objects.create_user(username='auxiliar-resp', email='auxiliar-resp@example.com', password='ClaveSegura1')
        self.empleado.groups.add(Group.objects.get_or_create(name='Vendedor')[0])
        self.gerente.groups.add(Group.objects.get_or_create(name='Gerente')[0])
        self.auxiliar.groups.add(Group.objects.get_or_create(name='Auxiliar Administrativo')[0])

    def test_aprobar_vacaciones_y_rechazar_certificado_notifican_empleado(self):
        self.client.force_login(self.auxiliar)
        for tipo, accion, motivo in (
            (Solicitud.Tipo.VACACIONES, 'aprobar', ''),
            (Solicitud.Tipo.VACACIONES, 'rechazar', 'Fechas no disponibles'),
            (Solicitud.Tipo.CERTIFICADO, 'aprobar', ''),
            (Solicitud.Tipo.CERTIFICADO, 'rechazar', 'Falta soporte'),
        ):
            solicitud = Solicitud.objects.create(usuario=self.empleado, tipo=tipo, fecha_desde=timezone.localdate(), fecha_hasta=timezone.localdate())
            with self.captureOnCommitCallbacks(execute=True):
                respuesta = self.client.post(reverse('bandeja_aprobacion'), {
                    'solicitud_id': solicitud.pk, 'accion': accion, 'motivo_rechazo': motivo,
                })
            self.assertEqual(respuesta.status_code, 302)
            solicitud.refresh_from_db()
            self.assertIsNotNone(solicitud.fecha_respuesta)
            self.assertEqual(solicitud.respondida_por, self.auxiliar)
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].to, [self.empleado.email])
            self.assertIn(solicitud.get_estado_display().lower(), mail.outbox[0].subject)
            if motivo:
                self.assertIn(motivo, mail.outbox[0].body)
            mail.outbox.clear()

    def test_respuestas_prenomina_notifican_al_gerente_calculador(self):
        for aprobar in (True, False):
            solicitud = generar_prenomina('2026-08' if aprobar else '2026-07', self.gerente)
            with self.captureOnCommitCallbacks(execute=True):
                if aprobar:
                    aceptar_prenomina(solicitud, self.auxiliar)
                else:
                    rechazar_prenomina(solicitud, self.auxiliar, 'Revisar valores')
            solicitud.refresh_from_db()
            self.assertIsNotNone(solicitud.fecha_respuesta)
            self.assertEqual(solicitud.respondida_por, self.auxiliar)
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].to, [self.gerente.email])
            if not aprobar:
                self.assertIn('Revisar valores', mail.outbox[0].body)
            mail.outbox.clear()

    def test_historial_presenta_respuesta_y_motivo(self):
        solicitud = Solicitud.objects.create(
            usuario=self.empleado, tipo=Solicitud.Tipo.CERTIFICADO,
            estado=Solicitud.Estado.RECHAZADA, motivo_rechazo='Documento incompleto',
            fecha_respuesta=timezone.now(), respondida_por=self.auxiliar,
        )
        self.client.force_login(self.empleado)
        respuesta = self.client.get(reverse('nomina_historial'))
        self.assertContains(respuesta, 'Documento incompleto')
        self.assertContains(respuesta, timezone.localtime(solicitud.fecha_respuesta).strftime('%d/%m/%Y %H:%M'))

    def test_consulta_muestra_bonificacion_y_horas_extra_aceptadas(self):
        Nomina.objects.create(
            usuario=self.empleado, periodo=timezone.localdate().strftime('%Y-%m'),
            salario_bruto=Decimal('1000000'), valor_bonificacion=Decimal('125000'),
            valor_horas_extra=Decimal('45000'), deducciones=Decimal('80000'),
            deduccion_salud=Decimal('40000'), deduccion_pension=Decimal('40000'),
            total_pagar=Decimal('1090000'), estado=Nomina.Estado.ACEPTADA,
        )
        self.client.force_login(self.empleado)
        respuesta = self.client.get(reverse('nomina_consultar'))
        self.assertContains(respuesta, 'Bonificaciones')
        self.assertContains(respuesta, 'Horas extra')
        self.assertContains(respuesta, '125.000')
        self.assertContains(respuesta, '45.000')
