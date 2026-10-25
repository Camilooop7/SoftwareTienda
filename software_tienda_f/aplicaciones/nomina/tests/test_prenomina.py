from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from aplicaciones.gestion_usuario.models import Usuario
from ..models import ConfiguracionBonificacion, HoraExtra, Nomina, Solicitud
from ..services import calcular_nomina, generar_prenomina, aceptar_prenomina, rechazar_prenomina
from ..excepciones import MotivoRechazoRequeridoError, NominaYaCalculadaError, PreNominaNoPendienteError, SinEmpleadosActivosError
from ..reportes import resumen_mensual


class PreNominaFlujoTest(TestCase):
    def setUp(self):
        self.gerente = Usuario.objects.create_user(
            username='prenomina-gerente', email='prenomina-gerente@example.com',
            password='test-password', is_active=False)
        self.auxiliar = Usuario.objects.create_user(
            username='prenomina-auxiliar', email='prenomina-auxiliar@example.com',
            password='test-password', is_active=False)
        self.empleados = [
            Usuario.objects.create_user(
                username='prenomina-empleado-{0}'.format(i),
                email='prenomina-empleado-{0}@example.com'.format(i),
                password='test-password', salario_base=Decimal(str(i * 1000)))
            for i in (1, 2)
        ]
        self.periodo = '2026-09'

    def _generar(self):
        return generar_prenomina(self.periodo, self.gerente)

    def test_generar_crea_nominas_y_una_solicitud_pendientes(self):
        solicitud = self._generar()

        self.assertEqual(Nomina.objects.filter(periodo=self.periodo).count(), 2)
        self.assertEqual(Nomina.objects.filter(
            periodo=self.periodo, estado=Nomina.Estado.PENDIENTE).count(), 2)
        self.assertEqual(solicitud.tipo, Solicitud.Tipo.NOMINA)
        self.assertEqual(solicitud.periodo, self.periodo)
        self.assertEqual(solicitud.estado, Solicitud.Estado.PENDIENTE)
        self.assertEqual(Solicitud.objects.filter(
            tipo=Solicitud.Tipo.NOMINA, periodo=self.periodo).count(), 1)
        self.assertEqual(Nomina.objects.filter(solicitud=solicitud).count(), 2)

    def test_generar_asocia_todas_las_nominas_a_solicitud_devuelta(self):
        solicitud = self._generar()
        self.assertEqual(
            set(Nomina.objects.filter(periodo=self.periodo).values_list('solicitud_id', flat=True)),
            {solicitud.pk},
        )

    def test_generar_dos_veces_informa_que_ya_fue_calculada(self):
        self._generar()
        with self.assertRaises(NominaYaCalculadaError) as contexto:
            self._generar()
        self.assertIn(self.periodo, str(contexto.exception))

    def test_aceptar_actualiza_nominas_usuarios_y_reporte(self):
        solicitud = self._generar()

        cantidad = aceptar_prenomina(solicitud, self.auxiliar)

        self.assertEqual(cantidad, 2)
        for empleado in self.empleados:
            nomina = Nomina.objects.get(usuario=empleado, periodo=self.periodo)
            self.assertEqual(nomina.estado, Nomina.Estado.ACEPTADA)
            self.assertEqual(nomina.revisada_por, self.auxiliar)
            self.assertIsNotNone(nomina.fecha_revision)
            empleado.refresh_from_db()
            self.assertEqual(empleado.ultimo_periodo_pagado, self.periodo)
            self.assertEqual(empleado.ultimo_total_pagado, nomina.total_pagar)
        self.assertEqual(resumen_mensual(self.periodo)['empleados'], 2)
        self.assertEqual(resumen_mensual(self.periodo)['total_pagado'], sum(
            (Nomina.objects.get(usuario=u, periodo=self.periodo).total_pagar
             for u in self.empleados), Decimal('0')))

    def test_aceptar_dos_veces_no_sobrescribe_ultimo_pago(self):
        solicitud = self._generar()
        aceptar_prenomina(solicitud, self.auxiliar)
        empleado = self.empleados[0]
        empleado.ultimo_total_pagado = Decimal('12345.67')
        empleado.save(update_fields=['ultimo_total_pagado'])

        with self.assertRaises(PreNominaNoPendienteError):
            aceptar_prenomina(solicitud, self.auxiliar)

        empleado.refresh_from_db()
        self.assertEqual(empleado.ultimo_total_pagado, Decimal('12345.67'))

    def test_rechazar_sin_motivo_no_cambia_estado(self):
        solicitud = self._generar()

        with self.assertRaises(MotivoRechazoRequeridoError):
            rechazar_prenomina(solicitud, self.auxiliar, '  ')

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, Solicitud.Estado.PENDIENTE)
        self.assertEqual(Nomina.objects.filter(
            periodo=self.periodo, estado=Nomina.Estado.PENDIENTE).count(), 2)

    def test_rechazar_y_generar_de_nuevo(self):
        solicitud = self._generar()
        originales = list(Nomina.objects.filter(periodo=self.periodo))
        rechazar_prenomina(solicitud, self.auxiliar, '   Datos incorrectos   ')

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, Solicitud.Estado.RECHAZADA)
        self.assertEqual(solicitud.motivo_rechazo, 'Datos incorrectos')
        for nomina in originales:
            nomina.refresh_from_db()
            self.assertEqual(nomina.estado, Nomina.Estado.RECHAZADA)
            self.assertEqual(nomina.revisada_por, self.auxiliar)
        for empleado in self.empleados:
            empleado.refresh_from_db()
            self.assertEqual(empleado.ultimo_periodo_pagado, '')
            self.assertIsNone(empleado.ultimo_total_pagado)

        nueva_solicitud = self._generar()
        self.assertNotEqual(nueva_solicitud.pk, solicitud.pk)
        self.assertEqual(Nomina.objects.filter(
            periodo=self.periodo, estado=Nomina.Estado.PENDIENTE).count(), 2)
        self.assertFalse(Nomina.objects.filter(
            periodo=self.periodo, estado=Nomina.Estado.RECHAZADA).exists())

    def test_aceptar_solo_cambia_nominas_de_su_solicitud(self):
        solicitud = self._generar()
        otras = [calcular_nomina(u, '2026-08') for u in self.empleados]
        cantidad = aceptar_prenomina(solicitud, self.auxiliar)
        self.assertEqual(cantidad, 2)
        self.assertTrue(all(n.estado == Nomina.Estado.ACEPTADA for n in
                            Nomina.objects.filter(solicitud=solicitud)))
        for nomina in otras:
            nomina.refresh_from_db()
            self.assertEqual(nomina.estado, Nomina.Estado.PENDIENTE)

    def test_sin_empleados_activos(self):
        Usuario.objects.filter(is_active=True).update(is_active=False)

        with self.assertRaises(SinEmpleadosActivosError):
            self._generar()

    def test_empleado_nuevo_solo_recibe_nomina_desde_su_ingreso(self):
        nuevo = Usuario.objects.create_user(
            username='prenomina-nuevo', email='prenomina-nuevo@example.com',
            password='test-password', fecha_ingreso='2026-10-15',
            salario_base=Decimal('2000000'),
        )
        solicitud = generar_prenomina('2026-09', self.gerente)
        aceptar_prenomina(solicitud, self.auxiliar)
        self.assertFalse(Nomina.objects.filter(usuario=nuevo, periodo='2026-09').exists())

        solicitud = generar_prenomina('2026-11', self.gerente)
        aceptar_prenomina(solicitud, self.auxiliar)
        self.assertTrue(Nomina.objects.filter(usuario=nuevo, periodo='2026-11').exists())


from django.test import SimpleTestCase
from ..excepciones import HoraExtraInvalidaError, NominaYaCalculadaError, SinEmpleadosActivosError, PreNominaNoPendienteError, MotivoRechazoRequeridoError


class MensajesExcepcionesTest(SimpleTestCase):
    def test_excepciones_interpolan_datos_en_su_mensaje(self):
        casos = ((NominaYaCalculadaError('2026-09', 'aceptada'), '2026-09', 'aceptada'), (SinEmpleadosActivosError('2026-09'), '2026-09'), (PreNominaNoPendienteError('aceptada'), 'aceptada'), (MotivoRechazoRequeridoError(), 'motivo'), (HoraExtraInvalidaError('hora inválida'), 'hora inválida'))
        for error, *fragmentos in casos:
            with self.subTest(error=type(error).__name__):
                for fragmento in fragmentos: self.assertIn(fragmento, str(error))
