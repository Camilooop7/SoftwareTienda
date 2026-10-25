from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from decimal import Decimal
from django.test import TestCase, SimpleTestCase
from aplicaciones.gestion_usuario.models import Usuario
from ..models import Nomina, Solicitud
from ..services import calcular_nomina, generar_prenomina, aceptar_prenomina, rechazar_prenomina
from ..excepciones import HoraExtraInvalidaError, MotivoRechazoRequeridoError, NominaYaCalculadaError, PreNominaNoPendienteError, SinEmpleadosActivosError
from ..reportes import resumen_mensual


class PreNominaFlujoTest(CasoPruebaMixin, TestCase):
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

    @caso('RF-008', 'Validar que la pre-nómina genere una nómina por cada empleado activo.',
          '2 empleados activos; periodo 2026-09', '2 nóminas en estado PENDIENTE')
    def test_generar_crea_nominas_pendientes(self):
        self._generar()
        cantidad = Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.PENDIENTE).count()
        self.obtenido(f'Nóminas pendientes: {cantidad}')
        self.assertEqual(cantidad, 2)

    @caso('RF-008', 'Validar que la pre-nómina se envíe como una única solicitud de aprobación.',
          '2 empleados activos; periodo 2026-09', '1 solicitud tipo NOMINA, periodo 2026-09, estado PENDIENTE')
    def test_generar_crea_una_solicitud_pendiente(self):
        solicitud = self._generar()
        cantidad = Solicitud.objects.filter(tipo=Solicitud.Tipo.NOMINA, periodo=self.periodo).count()
        self.obtenido(f'Solicitudes: {cantidad}; tipo {solicitud.tipo}; periodo {solicitud.periodo}; estado {solicitud.estado}')
        self.assertEqual((cantidad, solicitud.tipo, solicitud.periodo, solicitud.estado),
                         (1, Solicitud.Tipo.NOMINA, self.periodo, Solicitud.Estado.PENDIENTE))

    @caso('RF-008', 'Validar que todas las nóminas generadas queden asociadas a la solicitud.',
          '2 empleados activos; periodo 2026-09', 'Todas las nóminas apuntan a la solicitud creada')
    def test_generar_asocia_todas_las_nominas_a_solicitud_devuelta(self):
        solicitud = self._generar()
        ids = set(Nomina.objects.filter(periodo=self.periodo).values_list('solicitud_id', flat=True))
        self.obtenido(f'Solicitudes asociadas: {ids}; solicitud creada: {solicitud.pk}')
        self.assertEqual(ids, {solicitud.pk})

    @caso('RF-008', 'Validar que la nómina de un periodo se calcule una sola vez.',
          'Generar la pre-nómina de 2026-09 dos veces', 'NominaYaCalculadaError con el periodo 2026-09 en el mensaje')
    def test_generar_dos_veces_informa_que_ya_fue_calculada(self):
        self._generar()
        try:
            self._generar()
            mensaje = 'No se lanzó excepción'
        except NominaYaCalculadaError as error:
            mensaje = str(error)
        self.obtenido(f'Mensaje: {mensaje}')
        self.assertIn(self.periodo, mensaje)

    @caso('RF-007', 'Validar que al aceptar la pre-nómina todas sus nóminas queden aceptadas.',
          'Pre-nómina de 2 empleados; el Auxiliar acepta', '2 nóminas en estado ACEPTADA')
    def test_aceptar_cambia_estado_nominas(self):
        aceptar_prenomina(self._generar(), self.auxiliar)
        cantidad = Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.ACEPTADA).count()
        self.obtenido(f'Nóminas aceptadas: {cantidad}')
        self.assertEqual(cantidad, 2)

    @caso('RF-007', 'Validar que la aceptación registre quién y cuándo revisó.',
          'Pre-nómina aceptada por el Auxiliar', 'revisada_por = Auxiliar y fecha_revision con valor')
    def test_aceptar_registra_revisor(self):
        aceptar_prenomina(self._generar(), self.auxiliar)
        nomina = Nomina.objects.filter(periodo=self.periodo).first()
        self.obtenido(f'Revisada por: {nomina.revisada_por}; fecha: {nomina.fecha_revision}')
        self.assertTrue(nomina.revisada_por == self.auxiliar and nomina.fecha_revision is not None)

    @caso('RF-008', 'Validar que al aceptar se actualice el último pago de cada empleado.',
          'Pre-nómina 2026-09 aceptada', 'ultimo_periodo_pagado = 2026-09 y ultimo_total_pagado = total de su nómina')
    def test_aceptar_actualiza_ultimo_pago(self):
        aceptar_prenomina(self._generar(), self.auxiliar)
        empleado = self.empleados[0]
        empleado.refresh_from_db()
        nomina = Nomina.objects.get(usuario=empleado, periodo=self.periodo)
        self.obtenido(f'Último periodo: {empleado.ultimo_periodo_pagado}; último total: {empleado.ultimo_total_pagado}; total nómina: {nomina.total_pagar}')
        self.assertEqual((empleado.ultimo_periodo_pagado, empleado.ultimo_total_pagado),
                         (self.periodo, nomina.total_pagar))

    @caso('RF-004', 'Validar que las nóminas aceptadas aparezcan en el reporte mensual.',
          'Pre-nómina 2026-09 de 2 empleados aceptada', 'Reporte: 2 empleados y total pagado igual a la suma de las nóminas')
    def test_aceptar_incluye_en_reporte(self):
        aceptar_prenomina(self._generar(), self.auxiliar)
        resumen = resumen_mensual(self.periodo)
        esperado = sum((n.total_pagar for n in Nomina.objects.filter(periodo=self.periodo)), Decimal('0'))
        self.obtenido(f"Empleados: {resumen['empleados']}; total pagado: {resumen['total_pagado']}")
        self.assertEqual((resumen['empleados'], resumen['total_pagado']), (2, esperado))

    @caso('RF-007', 'Validar que una pre-nómina ya aceptada no se pueda aceptar otra vez.',
          'Aceptar dos veces la misma pre-nómina', 'PreNominaNoPendienteError')
    def test_aceptar_dos_veces_lanza_error(self):
        solicitud = self._generar()
        aceptar_prenomina(solicitud, self.auxiliar)
        try:
            aceptar_prenomina(solicitud, self.auxiliar)
            obtenido = 'Se aceptó otra vez'
        except PreNominaNoPendienteError:
            obtenido = 'PreNominaNoPendienteError'
        self.obtenido(obtenido)
        self.assertEqual(obtenido, 'PreNominaNoPendienteError')

    @caso('RF-008', 'Validar que la información del empleado se actualice una sola vez.',
          'Pre-nómina aceptada; se cambia el último total a 12345.67 y se intenta aceptar de nuevo',
          'El último total pagado sigue en 12345.67')
    def test_aceptar_dos_veces_no_sobrescribe_ultimo_pago(self):
        solicitud = self._generar()
        aceptar_prenomina(solicitud, self.auxiliar)
        empleado = self.empleados[0]
        empleado.ultimo_total_pagado = Decimal('12345.67')
        empleado.save(update_fields=['ultimo_total_pagado'])
        try:
            aceptar_prenomina(solicitud, self.auxiliar)
        except PreNominaNoPendienteError:
            pass
        empleado.refresh_from_db()
        self.obtenido(f'Último total pagado: {empleado.ultimo_total_pagado}')
        self.assertEqual(empleado.ultimo_total_pagado, Decimal('12345.67'))

    @caso('RF-007', 'Validar que no se pueda rechazar la pre-nómina sin motivo.',
          "Rechazo con motivo '  '", 'MotivoRechazoRequeridoError')
    def test_rechazar_sin_motivo_lanza_error(self):
        solicitud = self._generar()
        try:
            rechazar_prenomina(solicitud, self.auxiliar, '  ')
            obtenido = 'Rechazo aceptado sin motivo'
        except MotivoRechazoRequeridoError:
            obtenido = 'MotivoRechazoRequeridoError'
        self.obtenido(obtenido)
        self.assertEqual(obtenido, 'MotivoRechazoRequeridoError')

    @caso('RF-007', 'Validar que un rechazo sin motivo no cambie el estado de la pre-nómina.',
          "Rechazo con motivo '  '", 'La solicitud sigue PENDIENTE')
    def test_rechazar_sin_motivo_no_cambia_estado(self):
        solicitud = self._generar()
        try:
            rechazar_prenomina(solicitud, self.auxiliar, '  ')
        except MotivoRechazoRequeridoError:
            pass
        solicitud.refresh_from_db()
        self.obtenido(f'Estado de la solicitud: {solicitud.estado}')
        self.assertEqual(solicitud.estado, Solicitud.Estado.PENDIENTE)

    @caso('RF-007', 'Validar que el rechazo guarde el motivo sin espacios sobrantes.',
          "Rechazo con motivo '   Datos incorrectos   '", "Estado RECHAZADA; motivo 'Datos incorrectos'")
    def test_rechazar_guarda_motivo(self):
        solicitud = self._generar()
        rechazar_prenomina(solicitud, self.auxiliar, '   Datos incorrectos   ')
        solicitud.refresh_from_db()
        self.obtenido(f'Estado: {solicitud.estado}; motivo: {solicitud.motivo_rechazo!r}')
        self.assertEqual((solicitud.estado, solicitud.motivo_rechazo), (Solicitud.Estado.RECHAZADA, 'Datos incorrectos'))

    @caso('RF-007', 'Validar que al rechazar la pre-nómina sus nóminas queden rechazadas.',
          'Pre-nómina de 2 empleados rechazada', '2 nóminas en estado RECHAZADA')
    def test_rechazar_cambia_estado_nominas(self):
        rechazar_prenomina(self._generar(), self.auxiliar, 'Datos incorrectos')
        cantidad = Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.RECHAZADA).count()
        self.obtenido(f'Nóminas rechazadas: {cantidad}')
        self.assertEqual(cantidad, 2)

    @caso('RF-008', 'Validar que un rechazo no actualice el último pago de los empleados.',
          'Pre-nómina rechazada', "ultimo_periodo_pagado = '' y ultimo_total_pagado = None")
    def test_rechazar_no_actualiza_ultimo_pago(self):
        rechazar_prenomina(self._generar(), self.auxiliar, 'Datos incorrectos')
        empleado = self.empleados[0]
        empleado.refresh_from_db()
        self.obtenido(f'Último periodo: {empleado.ultimo_periodo_pagado!r}; último total: {empleado.ultimo_total_pagado}')
        self.assertEqual((empleado.ultimo_periodo_pagado, empleado.ultimo_total_pagado), ('', None))

    @caso('RF-008', 'Validar que tras un rechazo se pueda generar de nuevo la pre-nómina.',
          'Pre-nómina rechazada y generada otra vez', 'Nueva solicitud; 2 nóminas PENDIENTES y ninguna RECHAZADA')
    def test_rechazar_y_generar_de_nuevo(self):
        solicitud = self._generar()
        rechazar_prenomina(solicitud, self.auxiliar, 'Datos incorrectos')
        nueva = self._generar()
        pendientes = Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.PENDIENTE).count()
        rechazadas = Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.RECHAZADA).count()
        self.obtenido(f'Solicitud nueva distinta: {nueva.pk != solicitud.pk}; pendientes: {pendientes}; rechazadas: {rechazadas}')
        self.assertEqual((nueva.pk != solicitud.pk, pendientes, rechazadas), (True, 2, 0))

    @caso('RF-007', 'Validar que aceptar una pre-nómina no cambie nóminas de otra solicitud.',
          'Pre-nómina 2026-09 aceptada; nóminas de 2026-08 calculadas aparte', 'Las nóminas de 2026-08 siguen PENDIENTES')
    def test_aceptar_solo_cambia_nominas_de_su_solicitud(self):
        solicitud = self._generar()
        otras = [calcular_nomina(u, '2026-08') for u in self.empleados]
        aceptar_prenomina(solicitud, self.auxiliar)
        estados = {Nomina.objects.get(pk=n.pk).estado for n in otras}
        self.obtenido(f'Estados de las nóminas de 2026-08: {estados}')
        self.assertEqual(estados, {Nomina.Estado.PENDIENTE})

    @caso('RF-008', 'Validar que no se genere pre-nómina sin empleados activos.',
          'Todos los usuarios inactivos', 'SinEmpleadosActivosError')
    def test_sin_empleados_activos(self):
        Usuario.objects.filter(is_active=True).update(is_active=False)
        try:
            self._generar()
            obtenido = 'Se generó la pre-nómina'
        except SinEmpleadosActivosError:
            obtenido = 'SinEmpleadosActivosError'
        self.obtenido(obtenido)
        self.assertEqual(obtenido, 'SinEmpleadosActivosError')

    def crear_nuevo(self):
        return Usuario.objects.create_user(
            username='prenomina-nuevo', email='prenomina-nuevo@example.com',
            password='test-password', fecha_ingreso='2026-10-15',
            salario_base=Decimal('2000000'),
        )

    @caso('RF-008', 'Validar que un empleado no reciba nómina de meses anteriores a su ingreso.',
          'Empleado con ingreso 2026-10-15; pre-nómina de 2026-09', 'No se genera nómina para el empleado')
    def test_empleado_nuevo_sin_nomina_antes_del_ingreso(self):
        nuevo = self.crear_nuevo()
        generar_prenomina('2026-09', self.gerente)
        existe = Nomina.objects.filter(usuario=nuevo, periodo='2026-09').exists()
        self.obtenido(f'Nómina generada: {existe}')
        self.assertFalse(existe)

    @caso('RF-008', 'Validar que un empleado reciba nómina desde el mes de su ingreso.',
          'Empleado con ingreso 2026-10-15; pre-nómina de 2026-11', 'Se genera nómina para el empleado')
    def test_empleado_nuevo_con_nomina_despues_del_ingreso(self):
        nuevo = self.crear_nuevo()
        generar_prenomina('2026-11', self.gerente)
        existe = Nomina.objects.filter(usuario=nuevo, periodo='2026-11').exists()
        self.obtenido(f'Nómina generada: {existe}')
        self.assertTrue(existe)


class MensajesExcepcionesTest(CasoPruebaMixin, SimpleTestCase):
    @caso('RNF-009', 'Validar que el mensaje de nómina ya calculada incluya el periodo y su estado.',
          "NominaYaCalculadaError('2026-09', 'aceptada')", "Mensaje con '2026-09' y 'aceptada'")
    def test_mensaje_nomina_ya_calculada(self):
        mensaje = str(NominaYaCalculadaError('2026-09', 'aceptada'))
        self.obtenido(f'Mensaje: {mensaje}')
        self.assertTrue('2026-09' in mensaje and 'aceptada' in mensaje)

    @caso('RNF-009', 'Validar que el mensaje sin empleados activos incluya el periodo.',
          "SinEmpleadosActivosError('2026-09')", "Mensaje con '2026-09'")
    def test_mensaje_sin_empleados(self):
        mensaje = str(SinEmpleadosActivosError('2026-09'))
        self.obtenido(f'Mensaje: {mensaje}')
        self.assertIn('2026-09', mensaje)

    @caso('RNF-009', 'Validar que el mensaje de pre-nómina no pendiente incluya su estado.',
          "PreNominaNoPendienteError('aceptada')", "Mensaje con 'aceptada'")
    def test_mensaje_prenomina_no_pendiente(self):
        mensaje = str(PreNominaNoPendienteError('aceptada'))
        self.obtenido(f'Mensaje: {mensaje}')
        self.assertIn('aceptada', mensaje)

    @caso('RNF-009', 'Validar que el mensaje de rechazo sin motivo lo indique claramente.',
          'MotivoRechazoRequeridoError()', "Mensaje con la palabra 'motivo'")
    def test_mensaje_motivo_requerido(self):
        mensaje = str(MotivoRechazoRequeridoError())
        self.obtenido(f'Mensaje: {mensaje}')
        self.assertIn('motivo', mensaje)

    @caso('RNF-009', 'Validar que el error de horas extra conserve el mensaje recibido.',
          "HoraExtraInvalidaError('hora inválida')", "Mensaje 'hora inválida'")
    def test_mensaje_hora_extra_invalida(self):
        mensaje = str(HoraExtraInvalidaError('hora inválida'))
        self.obtenido(f'Mensaje: {mensaje}')
        self.assertIn('hora inválida', mensaje)
