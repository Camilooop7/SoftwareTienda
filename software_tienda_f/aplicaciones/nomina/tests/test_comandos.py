from django.core.management import call_command, CommandError
from django.test import SimpleTestCase
from django.db import connection
from unittest.mock import patch


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
