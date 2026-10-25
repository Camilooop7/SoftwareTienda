from decimal import Decimal
from django.test import TestCase, SimpleTestCase
from aplicaciones.gestion_usuario.models import Usuario
from ..models import Nomina
from ..reportes import resumen_mensual, nombre_periodo, MESES
from ..templatetags.formatos import formatear_moneda


class ResumenMensualTest(TestCase):
    def setUp(self):
        self.usuario_uno = Usuario.objects.create_user(
            username='reporte-uno', email='reporte-uno@example.com', password='test-password',
            first_name='Ana', last_name='Alfa',
        )
        self.usuario_dos = Usuario.objects.create_user(
            username='reporte-dos', email='reporte-dos@example.com', password='test-password',
            first_name='Beto', last_name='Beta',
        )
        self.usuario_pendiente = Usuario.objects.create_user(
            username='reporte-pendiente', email='reporte-pendiente@example.com', password='test-password',
        )
        self.usuario_rechazado = Usuario.objects.create_user(
            username='reporte-rechazado', email='reporte-rechazado@example.com', password='test-password',
        )
        self._crear_nomina(self.usuario_uno, '2026-09', Nomina.Estado.ACEPTADA,
                           '1000', '100', '50', '40', '40', '1020')
        self._crear_nomina(self.usuario_dos, '2026-09', Nomina.Estado.ACEPTADA,
                           '2000', '200', '100', '80', '80', '2040')
        self._crear_nomina(self.usuario_pendiente, '2026-09', Nomina.Estado.PENDIENTE,
                           '9000', '0', '0', '0', '0', '9000')
        self._crear_nomina(self.usuario_rechazado, '2026-09', Nomina.Estado.RECHAZADA,
                           '8000', '0', '0', '0', '0', '8000')
        self._crear_nomina(self.usuario_uno, '2026-08', Nomina.Estado.ACEPTADA,
                           '7000', '0', '0', '0', '0', '7000')

    def _crear_nomina(self, usuario, periodo, estado, salario, bonificacion,
                      horas, salud, pension, pagado):
        Nomina.objects.create(
            usuario=usuario, periodo=periodo, estado=estado,
            salario_bruto=Decimal(salario), valor_bonificacion=Decimal(bonificacion),
            valor_horas_extra=Decimal(horas), deduccion_salud=Decimal(salud),
            deduccion_pension=Decimal(pension), deducciones=Decimal(salud) + Decimal(pension),
            total_pagar=Decimal(pagado),
        )

    def test_suma_solo_nominas_aceptadas_del_periodo(self):
        resumen = resumen_mensual('2026-09')

        self.assertEqual(resumen['empleados'], 2)
        self.assertEqual(resumen['total_pagado'], Decimal('3060'))
        self.assertEqual(resumen['total_salud'], Decimal('120'))
        self.assertEqual(resumen['total_pension'], Decimal('120'))
        self.assertEqual(resumen['total_salarios'], Decimal('3000'))
        self.assertEqual(resumen['total_bonificaciones'], Decimal('300'))
        self.assertEqual(resumen['total_horas_extra'], Decimal('150'))
        self.assertEqual(resumen['total_devengado'], Decimal('3450'))

    def test_mes_sin_datos_devuelve_ceros(self):
        resumen = resumen_mensual('2026-07')

        campos = (
            'total_salarios', 'total_bonificaciones', 'total_horas_extra', 'total_devengado',
            'total_salud', 'total_pension', 'total_deducciones', 'total_pagado',
        )
        for campo in campos:
            self.assertEqual(resumen[campo], Decimal('0'))
        self.assertEqual(resumen['empleados'], 0)
        self.assertEqual(resumen['pct_salud'], Decimal('0'))
        self.assertEqual(resumen['pct_pension'], Decimal('0'))
        self.assertEqual(resumen['pct_neto'], Decimal('0'))


class FormatoMonedaTest(TestCase):
    def test_formatea_moneda(self):
        casos = (
            (1234567, '$1.234.567'),
            (Decimal('1500.50'), '$1.501'),
            (0, '$0'),
            (None, '$0'),
            (-1234, '-$1.234'),
        )
        for valor, esperado in casos:
            with self.subTest(valor=valor):
                self.assertEqual(formatear_moneda(valor), esperado)


from django.test import SimpleTestCase
from decimal import Decimal
from ..templatetags.formatos import formatear_moneda
from ..reportes import MESES


class FormatoMonedaAdicionalTest(SimpleTestCase):
    def test_valores_redondeados_y_entradas_invalidas(self):
        self.assertEqual(formatear_moneda(Decimal('0.5')), '$1')
        self.assertEqual(formatear_moneda(Decimal('-0.4')), '$0')
        self.assertEqual(formatear_moneda('1500'), '$1.500')
        self.assertEqual(formatear_moneda('abc'), '$0')

    def test_nombre_de_los_doce_meses(self):
        for mes, nombre in MESES.items():
            with self.subTest(mes=mes):
                self.assertEqual(nombre_periodo('2026-{0:02d}'.format(mes)), '{0} 2026'.format(nombre))


from django.test import TestCase
from .utils import crear_usuario
from ..pdf import generar_pdf_reporte


class GenerarPdfReporteTest(TestCase):
    def test_pdf_vacio_y_con_cuarenta_nominas(self):
        usuario = crear_usuario('pdf-report', salario_base=Decimal('1000000'))
        resumen = resumen_mensual('2026-09')
        pdf_vacio = generar_pdf_reporte(resumen, usuario)
        self.assertTrue(pdf_vacio.startswith(b'%PDF'))
        for indice in range(40):
            empleado = crear_usuario('pdf-empleado-{0}'.format(indice), salario_base=Decimal('1000000'))
            Nomina.objects.create(usuario=empleado, periodo='2026-09', salario_bruto=Decimal('1000000'), valor_bonificacion=0, valor_horas_extra=0, deducciones=80000, deduccion_salud=40000, deduccion_pension=40000, total_pagar=920000, estado=Nomina.Estado.ACEPTADA)
        pdf = generar_pdf_reporte(resumen_mensual('2026-09'), usuario)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(pdf.count(b'/Type /Page') - pdf.count(b'/Type /Pages'), 1)
