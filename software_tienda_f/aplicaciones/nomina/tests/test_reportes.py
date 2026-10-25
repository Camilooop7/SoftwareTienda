from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from decimal import Decimal
from django.test import TestCase, SimpleTestCase
from aplicaciones.gestion_usuario.models import Usuario
from ..models import Nomina
from ..reportes import resumen_mensual, nombre_periodo, MESES
from ..templatetags.formatos import formatear_moneda
from ..pdf import generar_pdf_reporte
from .utils import crear_usuario


class ResumenMensualTest(CasoPruebaMixin, TestCase):
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

    @caso('RF-004', 'Validar que el reporte cuente solo los empleados con nómina aceptada.',
          '2026-09: 2 nóminas ACEPTADAS, 1 PENDIENTE, 1 RECHAZADA', 'Empleados = 2')
    def test_reporte_cuenta_solo_aceptadas(self):
        resumen = resumen_mensual('2026-09')
        self.obtenido(f"Empleados = {resumen['empleados']}")
        self.assertEqual(resumen['empleados'], 2)

    @caso('RF-004', 'Validar el total pagado del mes con solo nóminas aceptadas.',
          '2026-09: aceptadas 1.020 y 2.040; pendiente 9.000; rechazada 8.000', 'Total pagado = 3060')
    def test_reporte_total_pagado(self):
        resumen = resumen_mensual('2026-09')
        self.obtenido(f"Total pagado = {resumen['total_pagado']}")
        self.assertEqual(resumen['total_pagado'], Decimal('3060'))

    @caso('RF-004', 'Validar el total de salud (4%) del mes.',
          '2026-09: salud 40 y 80 en nóminas aceptadas', 'Total salud = 120')
    def test_reporte_total_salud(self):
        resumen = resumen_mensual('2026-09')
        self.obtenido(f"Total salud = {resumen['total_salud']}")
        self.assertEqual(resumen['total_salud'], Decimal('120'))

    @caso('RF-004', 'Validar el total de pensión (4%) del mes.',
          '2026-09: pensión 40 y 80 en nóminas aceptadas', 'Total pensión = 120')
    def test_reporte_total_pension(self):
        resumen = resumen_mensual('2026-09')
        self.obtenido(f"Total pensión = {resumen['total_pension']}")
        self.assertEqual(resumen['total_pension'], Decimal('120'))

    @caso('RF-004', 'Validar el total devengado del mes (salarios + bonificaciones + horas extra).',
          '2026-09: salarios 3.000; bonificaciones 300; horas extra 150', 'Total devengado = 3450')
    def test_reporte_total_devengado(self):
        resumen = resumen_mensual('2026-09')
        self.obtenido(f"Salarios {resumen['total_salarios']}; bonificaciones {resumen['total_bonificaciones']}; "
                      f"horas extra {resumen['total_horas_extra']}; devengado {resumen['total_devengado']}")
        self.assertEqual(resumen['total_devengado'], Decimal('3450'))

    @caso('RF-004', 'Validar que el filtro por mes no mezcle nóminas de otros meses.',
          'Reporte de 2026-08 (1 nómina aceptada de 7.000)', 'Empleados = 1; total pagado = 7000')
    def test_reporte_filtra_por_mes(self):
        resumen = resumen_mensual('2026-08')
        self.obtenido(f"Empleados = {resumen['empleados']}; total pagado = {resumen['total_pagado']}")
        self.assertEqual((resumen['empleados'], resumen['total_pagado']), (1, Decimal('7000')))

    @caso('RF-004', 'Validar que un mes sin nóminas devuelva todos los totales en cero.',
          'Reporte de 2026-07 (sin nóminas)', 'Empleados 0 y todos los totales y porcentajes en 0')
    def test_mes_sin_datos_devuelve_ceros(self):
        resumen = resumen_mensual('2026-07')
        campos = (
            'total_salarios', 'total_bonificaciones', 'total_horas_extra', 'total_devengado',
            'total_salud', 'total_pension', 'total_deducciones', 'total_pagado',
            'pct_salud', 'pct_pension', 'pct_neto',
        )
        distintos = [c for c in campos if resumen[c] != Decimal('0')]
        self.obtenido(f"Empleados = {resumen['empleados']}; campos distintos de cero: {distintos or 'ninguno'}")
        self.assertEqual((resumen['empleados'], distintos), (0, []))


class FormatoMonedaTest(CasoPruebaMixin, SimpleTestCase):
    def formato(self, valor, esperado):
        obtenido = formatear_moneda(valor)
        self.obtenido(f'Formato: {obtenido}')
        self.assertEqual(obtenido, esperado)

    @caso('RF-004', 'Validar el formato de moneda con separador de miles.', 'valor: 1234567', '$1.234.567')
    def test_formatea_miles(self):
        self.formato(1234567, '$1.234.567')

    @caso('RF-004', 'Validar que la moneda se redondee al peso.', "valor: Decimal('1500.50')", '$1.501')
    def test_formatea_redondeo(self):
        self.formato(Decimal('1500.50'), '$1.501')

    @caso('RF-004', 'Validar el formato de un valor vacío.', 'valor: None', '$0')
    def test_formatea_none(self):
        self.formato(None, '$0')

    @caso('RF-004', 'Validar el formato de un valor negativo.', 'valor: -1234', '-$1.234')
    def test_formatea_negativo(self):
        self.formato(-1234, '-$1.234')

    @caso('RF-004', 'Validar que un negativo menor a medio peso se muestre como cero.', "valor: Decimal('-0.4')", '$0')
    def test_formatea_negativo_pequeno(self):
        self.formato(Decimal('-0.4'), '$0')

    @caso('RF-004', 'Validar el formato de un número recibido como texto.', "valor: '1500'", '$1.500')
    def test_formatea_texto_numerico(self):
        self.formato('1500', '$1.500')

    @caso('RF-004', 'Validar que un texto no numérico se muestre como cero.', "valor: 'abc'", '$0')
    def test_formatea_texto_invalido(self):
        self.formato('abc', '$0')

    @caso('RF-004', 'Validar el nombre en español de los doce meses del periodo.',
          "periodos '2026-01' a '2026-12'", "'Enero 2026' ... 'Diciembre 2026' (12 correctos)")
    def test_nombre_de_los_doce_meses(self):
        correctos = sum(1 for mes, nombre in MESES.items()
                        if nombre_periodo('2026-{0:02d}'.format(mes)) == '{0} 2026'.format(nombre))
        self.obtenido(f'Meses con nombre correcto: {correctos} de 12 (ej. {nombre_periodo("2026-09")})')
        self.assertEqual(correctos, 12)


class GenerarPdfReporteTest(CasoPruebaMixin, TestCase):
    def setUp(self):
        self.usuario = crear_usuario('pdf-report', salario_base=Decimal('1000000'))

    @caso('RF-004', 'Validar que se genere el PDF de un mes sin nóminas.', 'Reporte de 2026-09 sin nóminas',
          'Archivo que inicia con %PDF')
    def test_pdf_vacio(self):
        pdf = generar_pdf_reporte(resumen_mensual('2026-09'), self.usuario)
        self.obtenido(f'Encabezado del archivo: {pdf[:4]!r}; tamaño {len(pdf)} bytes')
        self.assertTrue(pdf.startswith(b'%PDF'))

    @caso('RF-004', 'Validar que un reporte con muchas nóminas se pagine en varias hojas.',
          'Reporte de 2026-09 con 40 nóminas aceptadas', 'PDF con más de 1 página')
    def test_pdf_con_cuarenta_nominas_pagina(self):
        for indice in range(40):
            empleado = crear_usuario('pdf-empleado-{0}'.format(indice), salario_base=Decimal('1000000'))
            Nomina.objects.create(usuario=empleado, periodo='2026-09', salario_bruto=Decimal('1000000'), valor_bonificacion=0, valor_horas_extra=0, deducciones=80000, deduccion_salud=40000, deduccion_pension=40000, total_pagar=920000, estado=Nomina.Estado.ACEPTADA)
        pdf = generar_pdf_reporte(resumen_mensual('2026-09'), self.usuario)
        paginas = pdf.count(b'/Type /Page') - pdf.count(b'/Type /Pages')
        self.obtenido(f'Páginas del PDF: {paginas}')
        self.assertGreater(paginas, 1)
