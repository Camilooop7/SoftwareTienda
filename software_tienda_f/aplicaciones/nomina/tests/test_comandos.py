from django.core.management import call_command, CommandError
from django.test import SimpleTestCase
from django.db import connection
from unittest.mock import patch
from django.test import TestCase
from aplicaciones.gestion_usuario.models import Auditoria, Usuario
from aplicaciones.nomina.models import ConfiguracionBonificacion, HoraExtra, Nomina, Solicitud


class SembrarDatosCargaTest(SimpleTestCase):
    def test_requiere_confirmacion(self):
        with patch('aplicaciones.nomina.management.commands.sembrar_datos_carga.connection.settings_dict', {'NAME': 'test_carga'}):
            with self.assertRaisesMessage(CommandError, 'Agrega --confirmar para sembrar datos de carga.'):
                call_command('sembrar_datos_carga')

    def test_rechaza_base_de_pruebas(self):
        nombre = connection.settings_dict.get('NAME', 'test_base')
        if nombre.lower().endswith('carga'):
            nombre = 'test_base'
        with patch('aplicaciones.nomina.management.commands.sembrar_datos_carga.connection.settings_dict', {'NAME': nombre}):
            with self.assertRaisesMessage(
                CommandError,
                'Este comando solo puede ejecutarse sobre una base de datos de carga (nombre terminado en "carga"). Base actual: {0}.'.format(nombre),
            ):
                call_command('sembrar_datos_carga', confirmar=True)


class PoblarDatosDemoTest(TestCase):
    def test_puebla_datos_reales_idempotentemente(self):
        with self.assertRaisesMessage(
                CommandError, 'Agrega --confirmar para poblar los datos de demostración.'):
            call_command('poblar_datos_demo')

        call_command('poblar_datos_demo', confirmar=True, password='Clave#2026')
        usuarios_demo = Usuario.objects.filter(username__in=(
            'mgomez', 'acastro', 'lrojas', 'cortiz', 'dtorres', 'emora',
            'farias', 'gpena', 'hruiz', 'isoto', 'jvega',
        ))
        total_demo = usuarios_demo.count()
        self.assertEqual(total_demo, 11)
        self.assertTrue(all(u.check_password('Clave#2026') for u in Usuario.objects.all()))
        self.assertGreaterEqual(ConfiguracionBonificacion.objects.count(), 10)
        self.assertGreaterEqual(HoraExtra.objects.count(), 10)
        self.assertGreaterEqual(Solicitud.objects.count(), 10)
        self.assertGreaterEqual(Nomina.objects.count(), 10)
        self.assertGreaterEqual(Auditoria.objects.count(), 10)
        self.assertEqual(Nomina.objects.filter(estado=Nomina.Estado.ACEPTADA).values(
            'periodo').distinct().count(), 11)
        self.assertGreaterEqual(Solicitud.objects.filter(
            estado=Solicitud.Estado.PENDIENTE).exclude(
                tipo=Solicitud.Tipo.NOMINA).count(), 3)

        conteo_usuarios = Usuario.objects.count()
        call_command('poblar_datos_demo', confirmar=True, password='Clave#2026')
        self.assertEqual(Usuario.objects.count(), conteo_usuarios)
        ingreso_tardio = Usuario.objects.get(username='jvega')
        self.assertFalse(Nomina.objects.filter(
            usuario=ingreso_tardio, periodo__lt=ingreso_tardio.fecha_ingreso.strftime('%Y-%m')
        ).exists())
