from django.test import TestCase
from datetime import date, time
from decimal import Decimal
from django.contrib.auth.models import Group
from django.urls import reverse

from aplicaciones.gestion_usuario.models import Usuario
from .models import ConfiguracionBonificacion, HoraExtra, Nomina
from .services import calcular_nomina
from .forms import ReporteFiltroForm
from .reportes import resumen_mensual
from .templatetags.formatos import formatear_moneda


class CalcularNominaTest(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='nomina-test',
            email='nomina-test@example.com',
            password='test-password',
        )

    def test_deducciones_salud_pension_sobre_salario_bruto(self):
        self.usuario.salario_base = Decimal('1000000')
        self.usuario.save()
        ConfiguracionBonificacion.objects.create(
            usuario=self.usuario,
            porcentaje=Decimal('10'),
            meta_mensual=Decimal('500000'),
        )
        HoraExtra.objects.create(
            usuario=self.usuario,
            fecha=date(2026, 9, 15),
            hora_ingreso=time(8, 0),
            hora_salida=time(17, 0),
            tipo=HoraExtra.Tipo.DIURNA,
            cantidad_horas=Decimal('1'),
            valor=Decimal('30000'),
            motivo='Prueba',
            periodo='2026-09',
        )

        nomina = calcular_nomina(self.usuario, '2026-09')

        self.assertEqual(nomina.deduccion_salud, Decimal('40000'))
        self.assertEqual(nomina.deduccion_pension, Decimal('40000'))
        self.assertEqual(nomina.deducciones, Decimal('80000'))
        self.assertEqual(nomina.total_pagar, Decimal('1000000'))
        self.assertEqual(nomina.estado, Nomina.Estado.PENDIENTE)

    def test_salario_cero_da_deducciones_cero(self):
        self.usuario.salario_base = Decimal('0')
        self.usuario.save()

        nomina = calcular_nomina(self.usuario, '2026-09')

        self.assertEqual(nomina.deduccion_salud, Decimal('0'))
        self.assertEqual(nomina.deduccion_pension, Decimal('0'))


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


class ReporteFiltroFormTest(TestCase):
    def test_mensajes_de_validacion(self):
        casos = (
            ('', 'Selecciona un período para generar el reporte.'),
            ('2026/09', 'El período debe tener el formato AAAA-MM (ej: 2026-09).'),
            ('2026-13', 'El mes debe estar entre 01 y 12.'),
            ('2019-12', 'No hay reportes anteriores a enero de 2020.'),
        )
        for periodo, mensaje in casos:
            with self.subTest(periodo=periodo):
                form = ReporteFiltroForm(data={'periodo': periodo})
                self.assertFalse(form.is_valid())
                self.assertEqual(form.errors['periodo'][0], mensaje)

    def test_periodo_valido_y_periodo_futuro(self):
        pasado = ReporteFiltroForm(data={'periodo': '2026-09'})
        self.assertTrue(pasado.is_valid(), pasado.errors)
        self.assertEqual(pasado.cleaned_data['periodo'], '2026-09')

        hoy = date.today()
        if hoy.month == 12:
            ano_futuro, mes_futuro = hoy.year + 1, 1
        else:
            ano_futuro, mes_futuro = hoy.year, hoy.month + 1
        periodo_futuro = '{0:04d}-{1:02d}'.format(ano_futuro, mes_futuro)
        form_futuro = ReporteFiltroForm(data={'periodo': periodo_futuro})
        self.assertFalse(form_futuro.is_valid())
        self.assertEqual(
            form_futuro.errors['periodo'][0],
            'No se puede generar el reporte de un mes futuro.',
        )


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


class ReporteMensualViewTest(TestCase):
    def setUp(self):
        self.gerente_group, _ = Group.objects.get_or_create(name='Gerente')
        self.auxiliar_group, _ = Group.objects.get_or_create(name='Auxiliar Administrativo')
        self.vendedor_group, _ = Group.objects.get_or_create(name='Vendedor')
        self.gerente = Usuario.objects.create_user(
            username='reporte-gerente', email='reporte-gerente@example.com', password='test-password')
        self.auxiliar = Usuario.objects.create_user(
            username='reporte-auxiliar', email='reporte-auxiliar@example.com', password='test-password')
        self.vendedor = Usuario.objects.create_user(
            username='reporte-vendedor', email='reporte-vendedor@example.com', password='test-password')
        self.gerente.groups.add(self.gerente_group)
        self.auxiliar.groups.add(self.auxiliar_group)
        self.vendedor.groups.add(self.vendedor_group)

    def _crear_nomina(self, usuario, estado, pagado):
        Nomina.objects.create(
            usuario=usuario, periodo='2026-09', estado=estado,
            salario_bruto=Decimal('1000000'), valor_bonificacion=Decimal('0'),
            valor_horas_extra=Decimal('0'), deducciones=Decimal('80000'),
            deduccion_salud=Decimal('40000'), deduccion_pension=Decimal('40000'),
            total_pagar=Decimal(pagado),
        )

    def test_permisos_por_grupo_y_anonimo(self):
        url = reverse('reporte_mensual')
        for usuario in (self.gerente, self.auxiliar):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.vendedor)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.logout()
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.url.startswith('/login/'))

    def test_reporte_filtra_nominas_aceptadas_y_formatea_total(self):
        self._crear_nomina(self.gerente, Nomina.Estado.ACEPTADA, '920000')
        self._crear_nomina(self.auxiliar, Nomina.Estado.PENDIENTE, '920000')
        self.client.force_login(self.gerente)

        respuesta = self.client.get(reverse('reporte_mensual'), {'periodo': '2026-09'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'reporte-gerente')
        self.assertNotContains(respuesta, 'reporte-auxiliar')
        self.assertContains(respuesta, '$920.000')

    def test_periodo_invalido_muestra_error_especifico(self):
        self.client.force_login(self.gerente)
        url = reverse('reporte_mensual')

        respuesta_mes = self.client.get(url, {'periodo': '2026-13'})
        self.assertEqual(respuesta_mes.status_code, 200)
        self.assertContains(respuesta_mes, 'El mes debe estar entre 01 y 12.')

        respuesta_formato = self.client.get(url, {'periodo': 'abc'})
        self.assertEqual(respuesta_formato.status_code, 200)
        self.assertContains(
            respuesta_formato, 'El período debe tener el formato AAAA-MM (ej: 2026-09).')


class ReportePDFViewTest(TestCase):
    def setUp(self):
        from aplicaciones.gestion_usuario.models import Auditoria
        self.Auditoria = Auditoria
        self.gerente_group, _ = Group.objects.get_or_create(name='Gerente')
        self.vendedor_group, _ = Group.objects.get_or_create(name='Vendedor')
        self.gerente = Usuario.objects.create_user(
            username='reporte-pdf-gerente', email='reporte-pdf-gerente@example.com', password='test-password')
        self.vendedor = Usuario.objects.create_user(
            username='reporte-pdf-vendedor', email='reporte-pdf-vendedor@example.com', password='test-password')
        self.gerente.groups.add(self.gerente_group)
        self.vendedor.groups.add(self.vendedor_group)

    def _crear_nomina_aceptada(self):
        Nomina.objects.create(
            usuario=self.gerente, periodo='2026-09', estado=Nomina.Estado.ACEPTADA,
            salario_bruto=Decimal('1000000'), valor_bonificacion=Decimal('0'),
            valor_horas_extra=Decimal('0'), deducciones=Decimal('80000'),
            deduccion_salud=Decimal('40000'), deduccion_pension=Decimal('40000'),
            total_pagar=Decimal('920000'),
        )

    def test_exporta_pdf_y_registra_auditoria(self):
        self._crear_nomina_aceptada()
        self.client.force_login(self.gerente)
        respuesta = self.client.get(reverse('reporte_mensual_pdf'), {'periodo': '2026-09'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertTrue(respuesta.content.startswith(b'%PDF'))
        self.assertIn('reporte_nomina_2026-09.pdf', respuesta['Content-Disposition'])
        self.assertTrue(self.Auditoria.objects.filter(
            usuario=self.gerente, accion=self.Auditoria.Accion.EXPORTAR).exists())

    def test_mes_vacio_devuelve_pdf_valido(self):
        self.client.force_login(self.gerente)
        respuesta = self.client.get(reverse('reporte_mensual_pdf'), {'periodo': '2026-09'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertTrue(respuesta.content.startswith(b'%PDF'))

    def test_permisos_y_periodo_invalido(self):
        url = reverse('reporte_mensual_pdf')
        self.client.force_login(self.vendedor)
        self.assertEqual(self.client.get(url, {'periodo': '2026-09'}).status_code, 403)

        self.client.logout()
        self.assertEqual(self.client.get(url, {'periodo': '2026-09'}).status_code, 302)

        self.client.force_login(self.gerente)
        respuesta = self.client.get(url, {'periodo': '2026-13'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse('reporte_mensual'))

    def test_generador_produce_pdf(self):
        from .pdf import generar_pdf_reporte
        self._crear_nomina_aceptada()
        self.assertTrue(generar_pdf_reporte(resumen_mensual('2026-09'), self.gerente).startswith(b'%PDF'))


