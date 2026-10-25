from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase
from django.db import connection
from unittest.mock import patch
from aplicaciones.gestion_usuario.models import Auditoria, Usuario
from aplicaciones.nomina.models import ConfiguracionBonificacion, HoraExtra, Nomina, Solicitud


class SembrarDatosCargaTest(CasoPruebaMixin, SimpleTestCase):
    @caso('RNF-016', 'Validar que el sembrado de datos de carga exija confirmación explícita.',
          'sembrar_datos_carga sin --confirmar', 'Agrega --confirmar para sembrar datos de carga.')
    def test_requiere_confirmacion(self):
        with patch('aplicaciones.nomina.management.commands.sembrar_datos_carga.connection.settings_dict', {'NAME': 'test_carga'}):
            try:
                call_command('sembrar_datos_carga')
                mensaje = 'El comando se ejecutó sin confirmación'
            except CommandError as error:
                mensaje = str(error)
        self.obtenido(f'Mensaje: {mensaje}')
        self.assertEqual(mensaje, 'Agrega --confirmar para sembrar datos de carga.')

    @caso('RNF-016', 'Validar que los datos de carga solo se siembren en una base terminada en "carga".',
          'sembrar_datos_carga --confirmar sobre la base de pruebas',
          'Este comando solo puede ejecutarse sobre una base de datos de carga (nombre terminado en "carga"). Base actual: <nombre>.')
    def test_rechaza_base_de_pruebas(self):
        nombre = connection.settings_dict.get('NAME', 'test_base')
        if nombre.lower().endswith('carga'):
            nombre = 'test_base'
        with patch('aplicaciones.nomina.management.commands.sembrar_datos_carga.connection.settings_dict', {'NAME': nombre}):
            try:
                call_command('sembrar_datos_carga', confirmar=True)
                mensaje = 'El comando se ejecutó'
            except CommandError as error:
                mensaje = str(error)
        self.obtenido(f'Mensaje: {mensaje}')
        self.assertEqual(mensaje, 'Este comando solo puede ejecutarse sobre una base de datos de carga (nombre terminado en "carga"). Base actual: {0}.'.format(nombre))


USUARIOS_DEMO = ('mgomez', 'acastro', 'lrojas', 'cortiz', 'dtorres', 'emora',
                 'farias', 'gpena', 'hruiz', 'isoto', 'jvega')


class PoblarDatosDemoTest(CasoPruebaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('poblar_datos_demo', confirmar=True, password='Clave#2026')

    @caso('RF-001', 'Validar que poblar datos de demostración exija confirmación.',
          'poblar_datos_demo sin --confirmar', 'Agrega --confirmar para poblar los datos de demostración.')
    def test_requiere_confirmacion(self):
        try:
            call_command('poblar_datos_demo')
            mensaje = 'El comando se ejecutó sin confirmación'
        except CommandError as error:
            mensaje = str(error)
        self.obtenido(f'Mensaje: {mensaje}')
        self.assertEqual(mensaje, 'Agrega --confirmar para poblar los datos de demostración.')

    @caso('RF-001', 'Validar que la demostración cree los 11 empleados con la contraseña indicada.',
          "poblar_datos_demo --confirmar --password 'Clave#2026'", '11 usuarios demo; todos con la contraseña Clave#2026')
    def test_crea_usuarios_demo(self):
        total = Usuario.objects.filter(username__in=USUARIOS_DEMO).count()
        con_clave = all(u.check_password('Clave#2026') for u in Usuario.objects.all())
        self.obtenido(f'Usuarios demo: {total}; todos con la contraseña: {con_clave}')
        self.assertEqual((total, con_clave), (11, True))

    @caso('RNF-016', 'Validar que la demostración deje al menos 10 registros en cada tabla.',
          'poblar_datos_demo --confirmar', 'Bonificaciones, horas extra, solicitudes, nóminas y auditoría ≥ 10')
    def test_volumen_por_tabla(self):
        conteos = {
            'bonificaciones': ConfiguracionBonificacion.objects.count(),
            'horas_extra': HoraExtra.objects.count(),
            'solicitudes': Solicitud.objects.count(),
            'nominas': Nomina.objects.count(),
            'auditoria': Auditoria.objects.count(),
        }
        self.obtenido(f'Registros por tabla: {conteos}')
        self.assertTrue(all(valor >= 10 for valor in conteos.values()))

    @caso('RF-008', 'Validar que la demostración genere nóminas aceptadas de 11 meses.',
          'poblar_datos_demo --confirmar', '11 periodos distintos con nóminas ACEPTADAS')
    def test_nominas_de_once_meses(self):
        periodos = Nomina.objects.filter(estado=Nomina.Estado.ACEPTADA).values('periodo').distinct().count()
        self.obtenido(f'Periodos con nómina aceptada: {periodos}')
        self.assertEqual(periodos, 11)

    @caso('RF-007', 'Validar que la demostración deje solicitudes pendientes para la bandeja.',
          'poblar_datos_demo --confirmar', 'Al menos 3 solicitudes pendientes (sin contar nómina)')
    def test_solicitudes_pendientes(self):
        pendientes = Solicitud.objects.filter(estado=Solicitud.Estado.PENDIENTE).exclude(tipo=Solicitud.Tipo.NOMINA).count()
        self.obtenido(f'Solicitudes pendientes: {pendientes}')
        self.assertGreaterEqual(pendientes, 3)

    @caso('RF-001', 'Validar que ejecutar dos veces la demostración no duplique usuarios.',
          'poblar_datos_demo --confirmar ejecutado dos veces', 'La cantidad de usuarios no cambia')
    def test_idempotente(self):
        antes = Usuario.objects.count()
        call_command('poblar_datos_demo', confirmar=True, password='Clave#2026')
        despues = Usuario.objects.count()
        self.obtenido(f'Usuarios antes: {antes}; después: {despues}')
        self.assertEqual(despues, antes)

    @caso('RF-008', 'Validar que el empleado de ingreso tardío no tenga nóminas antes de su ingreso.',
          'poblar_datos_demo --confirmar; empleado jvega', 'Ninguna nómina anterior al mes de ingreso')
    def test_ingreso_tardio_sin_nominas_previas(self):
        jvega = Usuario.objects.get(username='jvega')
        previas = Nomina.objects.filter(usuario=jvega, periodo__lt=jvega.fecha_ingreso.strftime('%Y-%m')).count()
        self.obtenido(f'Nóminas anteriores al ingreso ({jvega.fecha_ingreso}): {previas}')
        self.assertEqual(previas, 0)
