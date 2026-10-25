from decimal import Decimal
from datetime import date, time, timedelta
from django.test import TestCase
from django.contrib.auth.models import Group
from django.urls import reverse
from aplicaciones.gestion_usuario.models import Usuario
from ..models import ConfiguracionBonificacion, HoraExtra, Nomina, Solicitud
from ..forms import BonificacionForm
from ..services import generar_prenomina, aceptar_prenomina, rechazar_prenomina
from ..reportes import resumen_mensual


class NovedadesViewTest(TestCase):
    def setUp(self):
        self.gerente_group, _ = Group.objects.get_or_create(name='Gerente')
        self.vendedor_group, _ = Group.objects.get_or_create(name='Vendedor')
        self.gerente = Usuario.objects.create_user(
            username='novedades-gerente', email='novedades-gerente@example.com', password='clave')
        self.vendedor = Usuario.objects.create_user(
            username='novedades-vendedor', email='novedades-vendedor@example.com', password='clave')
        self.empleado = Usuario.objects.create_user(
            username='novedades-empleado', email='novedades-empleado@example.com', password='clave',
            salario_base=Decimal('1000000'))
        self.gerente.groups.add(self.gerente_group)
        self.vendedor.groups.add(self.vendedor_group)

    def test_pantalla_muestra_ambas_secciones_y_restringe_vendedor(self):
        self.client.force_login(self.gerente)
        respuesta = self.client.get(reverse('novedades'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Configuración de bonificaciones')
        self.assertContains(respuesta, 'Trabajador')
        self.assertContains(respuesta, 'action="/nomina/bonificaciones/"')
        self.assertContains(respuesta, 'action="/nomina/horas-extra/"')

        self.client.force_login(self.vendedor)
        self.assertEqual(self.client.get(reverse('novedades')).status_code, 403)

    def test_get_de_vistas_antiguas_redirige_a_su_seccion(self):
        self.client.force_login(self.gerente)
        for nombre, destino in (
            ('horas_extra', '?seccion=horas-extra#horas-extra'),
            ('bonificaciones', '?seccion=bonificaciones#bonificaciones'),
        ):
            respuesta = self.client.get(reverse(nombre))
            self.assertEqual(respuesta.status_code, 302)
            self.assertEqual(respuesta.url, reverse('novedades') + destino)

    def test_post_valido_bonificaciones_crea_y_actualiza_configuracion(self):
        self.client.force_login(self.gerente)
        datos = {'usuario': self.empleado.pk, 'porcentaje': '10', 'meta_mensual': '500000'}
        respuesta = self.client.post(reverse('bonificaciones'), datos)
        self.assertEqual(respuesta.url, reverse('novedades') + '?seccion=bonificaciones#bonificaciones')
        config = ConfiguracionBonificacion.objects.get(usuario=self.empleado)
        self.assertEqual(config.porcentaje, Decimal('10'))

        datos['porcentaje'] = '15'
        respuesta = self.client.post(reverse('bonificaciones'), datos)
        config.refresh_from_db()
        self.assertEqual(config.porcentaje, Decimal('15'))
        self.assertEqual(respuesta.status_code, 302)

    def test_post_invalido_bonificacion_renderiza_novedades_con_error(self):
        self.client.force_login(self.gerente)
        respuesta = self.client.post(reverse('bonificaciones'), {
            'usuario': self.empleado.pk, 'porcentaje': '', 'meta_mensual': '500000'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'novedades.html')
        self.assertContains(respuesta, 'Escribe el porcentaje de bonificación.')

    def test_formularios_renderizan_restricciones_de_entrada(self):
        from aplicaciones.gestion_usuario.forms import UsuarioCrearForm

        self.assertIn('data-solo="numeros"', str(UsuarioCrearForm()['identificacion']))
        self.assertIn('data-solo="letras"', str(UsuarioCrearForm()['first_name']))
        self.assertIn('data-solo="decimal"', str(BonificacionForm()['porcentaje']))

    def test_bonificacion_acepta_coma_y_punto_decimal(self):
        for porcentaje in ('15,5', '15.5'):
            form = BonificacionForm(data={
                'usuario': self.empleado.pk,
                'porcentaje': porcentaje,
                'meta_mensual': '500000',
            })
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data['porcentaje'], Decimal('15.5'))

    def test_novedades_muestra_montos_formateados(self):
        self.client.force_login(self.gerente)
        ConfiguracionBonificacion.objects.create(
            usuario=self.empleado,
            porcentaje=Decimal('15.5'),
            meta_mensual=Decimal('1500000'),
        )
        respuesta = self.client.get(reverse('novedades'))
        self.assertContains(respuesta, '$1.500.000')
        self.assertNotContains(respuesta, '1500000.00')

    def test_post_valido_horas_extra_crea_registro_y_redirige(self):
        self.client.force_login(self.gerente)
        respuesta = self.client.post(reverse('horas_extra'), {
            'usuario': self.empleado.pk, 'fecha': '2026-10-24',
            'hora_ingreso': '08:00', 'hora_salida': '19:00', 'motivo': 'Inventario'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse('novedades') + '?seccion=horas-extra#horas-extra')
        self.assertEqual(HoraExtra.objects.filter(usuario=self.empleado).count(), 1)


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
        from ..pdf import generar_pdf_reporte
        self._crear_nomina_aceptada()
        self.assertTrue(generar_pdf_reporte(resumen_mensual('2026-09'), self.gerente).startswith(b'%PDF'))


class PreNominaIntegracionViewTest(TestCase):
    def setUp(self):
        self.gerente_group, _ = Group.objects.get_or_create(name='Gerente')
        self.auxiliar_group, _ = Group.objects.get_or_create(name='Auxiliar Administrativo')
        self.vendedor_group, _ = Group.objects.get_or_create(name='Vendedor')
        self.gerente = Usuario.objects.create_user(
            username='integracion-gerente', email='integracion-gerente@example.com', password='clave')
        self.auxiliar = Usuario.objects.create_user(
            username='integracion-auxiliar', email='integracion-auxiliar@example.com', password='clave')
        self.vendedor = Usuario.objects.create_user(
            username='integracion-vendedor', email='integracion-vendedor@example.com', password='clave')
        self.empleado = Usuario.objects.create_user(
            username='integracion-empleado', email='integracion-empleado@example.com', password='clave',
            first_name='Empleada', last_name='Prueba', salario_base=Decimal('1000000'))
        self.gerente.groups.add(self.gerente_group)
        self.auxiliar.groups.add(self.auxiliar_group)
        self.vendedor.groups.add(self.vendedor_group)
        self.empleado.groups.add(self.vendedor_group)
        self.periodo = date.today().strftime('%Y-%m')

    def _calcular(self):
        self.client.force_login(self.gerente)
        return self.client.post(reverse('calculo_nomina'), {'periodo': self.periodo})

    def test_calcular_bandeja_detalle_y_permisos(self):
        response = self._calcular()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.PENDIENTE).exists())
        solicitud = Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=self.periodo)
        segunda = self.client.post(reverse('calculo_nomina'), {'periodo': self.periodo}, follow=True)
        self.assertContains(segunda, 'ya fue calculada')
        self.assertEqual(Nomina.objects.filter(periodo=self.periodo).count(), 4)
        self.client.force_login(self.auxiliar)
        self.assertContains(self.client.get(reverse('bandeja_aprobacion')), 'Pre-nómina')
        detalle = reverse('prenomina_detalle', args=[solicitud.pk])
        self.assertEqual(self.client.get(detalle).status_code, 200)
        self.assertContains(self.client.get(detalle), 'Empleada Prueba')
        for no_autorizado in (self.gerente, self.vendedor):
            self.client.force_login(no_autorizado)
            self.assertEqual(self.client.get(detalle).status_code, 403)

    def test_aprobacion_publica_reporte_nomina_y_perfil(self):
        self._calcular()
        solicitud = Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=self.periodo)
        self.client.force_login(self.auxiliar)
        self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': solicitud.pk, 'accion': 'aprobar'})
        self.assertFalse(Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.PENDIENTE).exists())
        self.assertTrue(Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.ACEPTADA).exists())
        self.client.force_login(self.gerente)
        self.assertContains(self.client.get(reverse('reporte_mensual'), {'periodo': self.periodo}), 'Empleada Prueba')
        self.client.force_login(self.empleado)
        self.assertContains(self.client.get(reverse('nomina_consultar'), {'periodo': self.periodo}), 'Total a pagar')
        self.assertContains(self.client.get(reverse('perfil_actual')), 'Último pago')

    def test_rechazo_requiere_motivo_y_permite_recalculo(self):
        self._calcular()
        solicitud = Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=self.periodo)
        self.client.force_login(self.auxiliar)
        url = reverse('bandeja_aprobacion')
        respuesta = self.client.post(url, {'solicitud_id': solicitud.pk, 'accion': 'rechazar'}, follow=True)
        self.assertContains(respuesta, 'Debes escribir el motivo')
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, Solicitud.Estado.PENDIENTE)
        self.client.post(url, {'solicitud_id': solicitud.pk, 'accion': 'rechazar', 'motivo_rechazo': 'Datos errados'})
        self.client.force_login(self.gerente)
        self.assertEqual(self.client.post(reverse('calculo_nomina'), {'periodo': self.periodo}).status_code, 302)
        self.assertEqual(Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.PENDIENTE).count(), 4)

    def test_detalle_rechazado_no_muestra_lote_recalculado(self):
        self._calcular()
        vieja = Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=self.periodo)
        self.client.force_login(self.auxiliar)
        self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': vieja.pk, 'accion': 'rechazar', 'motivo_rechazo': 'Datos errados'})
        self.empleado.salario_base = Decimal('2000000')
        self.empleado.save(update_fields=['salario_base'])
        self.client.force_login(self.gerente)
        self.client.post(reverse('calculo_nomina'), {'periodo': self.periodo})
        nueva = Solicitud.objects.exclude(pk=vieja.pk).get(
            tipo=Solicitud.Tipo.NOMINA, periodo=self.periodo)
        detalle_url = reverse('prenomina_detalle', args=[vieja.pk])
        self.client.force_login(self.auxiliar)
        respuesta_vieja = self.client.get(detalle_url)
        self.assertContains(respuesta_vieja, 'se reemplazaron')
        self.assertNotContains(respuesta_vieja, '$1.840.000')
        respuesta_nueva = self.client.get(reverse('prenomina_detalle', args=[nueva.pk]))
        self.assertContains(respuesta_nueva, 'Empleada Prueba')
        self.assertContains(respuesta_nueva, '$1.840.000')

    def test_nomina_pendiente_no_expone_montos_y_error_de_periodo(self):
        self._calcular()
        self.client.force_login(self.empleado)
        respuesta = self.client.get(reverse('nomina_consultar'), {'periodo': self.periodo})
        self.assertContains(respuesta, 'está en revisión')
        self.assertNotContains(respuesta, '$1.000.000')
        self.client.force_login(self.gerente)
        respuesta = self.client.post(reverse('calculo_nomina'), {'periodo': '2026/09'}, follow=True)
        self.assertContains(respuesta, 'formato AAAA-MM')
