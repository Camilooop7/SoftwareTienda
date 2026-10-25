from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from aplicaciones.gestion_usuario.models import Auditoria, Usuario
from aplicaciones.gestion_usuario.forms import UsuarioCrearForm
from ..models import ConfiguracionBonificacion, HoraExtra, Nomina, Solicitud
from ..forms import BonificacionForm


class NovedadesViewTest(CasoPruebaMixin, TestCase):
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

    @caso('RF-005', 'Validar que la ventana Novedades muestre la sección de bonificaciones.',
          'Gerente abre /nomina/novedades/', 'HTTP 200 con formulario hacia /nomina/bonificaciones/')
    def test_novedades_muestra_bonificaciones(self):
        self.client.force_login(self.gerente)
        html = self.client.get(reverse('novedades')).content.decode()
        visible = 'Configuración de bonificaciones' in html and 'action="/nomina/bonificaciones/"' in html
        self.obtenido(f'Sección de bonificaciones visible: {visible}')
        self.assertTrue(visible)

    @caso('RF-002', 'Validar que la ventana Novedades muestre la sección de horas extra.',
          'Gerente abre /nomina/novedades/', 'HTTP 200 con formulario hacia /nomina/horas-extra/')
    def test_novedades_muestra_horas_extra(self):
        self.client.force_login(self.gerente)
        html = self.client.get(reverse('novedades')).content.decode()
        visible = 'Trabajador' in html and 'action="/nomina/horas-extra/"' in html
        self.obtenido(f'Sección de horas extra visible: {visible}')
        self.assertTrue(visible)

    @caso('RNF-003', 'Validar que un Vendedor no acceda a la ventana Novedades.',
          'Vendedor abre /nomina/novedades/', 'HTTP 403')
    def test_novedades_restringe_vendedor(self):
        self.client.force_login(self.vendedor)
        estado = self.client.get(reverse('novedades')).status_code
        self.obtenido(f'HTTP {estado}')
        self.assertEqual(estado, 403)

    @caso('RF-002', 'Validar que la ruta antigua de horas extra lleve a su sección en Novedades.',
          'GET /nomina/horas-extra/', 'HTTP 302 a /nomina/novedades/?seccion=horas-extra#horas-extra')
    def test_ruta_antigua_horas_extra_redirige(self):
        self.client.force_login(self.gerente)
        respuesta = self.client.get(reverse('horas_extra'))
        self.obtenido(f'HTTP {respuesta.status_code}; redirección a {respuesta.get("Location")}')
        self.assertEqual(respuesta.get('Location'), reverse('novedades') + '?seccion=horas-extra#horas-extra')

    @caso('RF-005', 'Validar que la ruta antigua de bonificaciones lleve a su sección en Novedades.',
          'GET /nomina/bonificaciones/', 'HTTP 302 a /nomina/novedades/?seccion=bonificaciones#bonificaciones')
    def test_ruta_antigua_bonificaciones_redirige(self):
        self.client.force_login(self.gerente)
        respuesta = self.client.get(reverse('bonificaciones'))
        self.obtenido(f'HTTP {respuesta.status_code}; redirección a {respuesta.get("Location")}')
        self.assertEqual(respuesta.get('Location'), reverse('novedades') + '?seccion=bonificaciones#bonificaciones')

    @caso('RF-005', 'Validar que se registre una bonificación nueva.',
          'POST bonificación: porcentaje 10; meta 500000', 'Configuración guardada con porcentaje 10')
    def test_post_valido_bonificacion_crea(self):
        self.client.force_login(self.gerente)
        self.client.post(reverse('bonificaciones'), {'usuario': self.empleado.pk, 'porcentaje': '10', 'meta_mensual': '500000'})
        config = ConfiguracionBonificacion.objects.filter(usuario=self.empleado).first()
        self.obtenido(f'Porcentaje guardado: {config.porcentaje if config else "sin registro"}')
        self.assertEqual(config.porcentaje, Decimal('10'))

    @caso('RF-005', 'Validar que al guardar una bonificación se vuelva a su sección de Novedades.',
          'POST bonificación válida', 'Redirección a /nomina/novedades/?seccion=bonificaciones#bonificaciones')
    def test_post_valido_bonificacion_redirige(self):
        self.client.force_login(self.gerente)
        respuesta = self.client.post(reverse('bonificaciones'), {'usuario': self.empleado.pk, 'porcentaje': '10', 'meta_mensual': '500000'})
        self.obtenido(f'HTTP {respuesta.status_code}; redirección a {respuesta.get("Location")}')
        self.assertEqual(respuesta.get('Location'), reverse('novedades') + '?seccion=bonificaciones#bonificaciones')

    @caso('RF-005', 'Validar que registrar otra bonificación al mismo empleado actualice la existente.',
          'Bonificación 10% existente; POST con porcentaje 15', 'Una sola configuración con porcentaje 15')
    def test_post_bonificacion_actualiza(self):
        self.client.force_login(self.gerente)
        datos = {'usuario': self.empleado.pk, 'porcentaje': '10', 'meta_mensual': '500000'}
        self.client.post(reverse('bonificaciones'), datos)
        datos['porcentaje'] = '15'
        self.client.post(reverse('bonificaciones'), datos)
        configs = list(ConfiguracionBonificacion.objects.filter(usuario=self.empleado).values_list('porcentaje', flat=True))
        self.obtenido(f'Configuraciones del empleado: {[str(p) for p in configs]}')
        self.assertEqual(configs, [Decimal('15')])

    @caso('RF-005', 'Validar que una bonificación sin porcentaje muestre el error en Novedades.',
          "POST bonificación con porcentaje ''", 'HTTP 200 en novedades.html con: Escribe el porcentaje de bonificación.')
    def test_post_invalido_bonificacion_muestra_error(self):
        self.client.force_login(self.gerente)
        respuesta = self.client.post(reverse('bonificaciones'), {
            'usuario': self.empleado.pk, 'porcentaje': '', 'meta_mensual': '500000'})
        mensaje = 'Escribe el porcentaje de bonificación.'
        plantillas = [t.name for t in respuesta.templates]
        self.obtenido(f'HTTP {respuesta.status_code}; plantilla novedades.html: {"novedades.html" in plantillas}; mensaje visible: {mensaje in respuesta.content.decode()}')
        self.assertTemplateUsed(respuesta, 'novedades.html')
        self.assertContains(respuesta, mensaje)

    @caso('RF-001', 'Validar que el campo identificación bloquee letras desde el teclado.',
          'Formulario de registro de usuario, campo identificación', 'Atributo data-solo="numeros"')
    def test_identificacion_bloquea_letras(self):
        html = str(UsuarioCrearForm()['identificacion'])
        self.obtenido(f'data-solo="numeros" presente: {"data-solo=\"numeros\"" in html}')
        self.assertIn('data-solo="numeros"', html)

    @caso('RF-001', 'Validar que el campo nombres bloquee números desde el teclado.',
          'Formulario de registro de usuario, campo nombres', 'Atributo data-solo="letras"')
    def test_nombres_bloquea_numeros(self):
        html = str(UsuarioCrearForm()['first_name'])
        self.obtenido(f'data-solo="letras" presente: {"data-solo=\"letras\"" in html}')
        self.assertIn('data-solo="letras"', html)

    @caso('RF-005', 'Validar que el porcentaje de bonificación solo admita números decimales.',
          'Formulario de bonificación, campo porcentaje', 'Atributo data-solo="decimal"')
    def test_porcentaje_solo_decimal(self):
        html = str(BonificacionForm()['porcentaje'])
        self.obtenido(f'data-solo="decimal" presente: {"data-solo=\"decimal\"" in html}')
        self.assertIn('data-solo="decimal"', html)

    def porcentaje_limpio(self, porcentaje):
        form = BonificacionForm(data={'usuario': self.empleado.pk, 'porcentaje': porcentaje, 'meta_mensual': '500000'})
        return form.cleaned_data['porcentaje'] if form.is_valid() else dict(form.errors)

    @caso('RF-005', 'Validar que el porcentaje acepte coma decimal.', "porcentaje: '15,5'", 'Porcentaje = 15.5')
    def test_bonificacion_acepta_coma(self):
        valor = self.porcentaje_limpio('15,5')
        self.obtenido(f'Porcentaje = {valor}')
        self.assertEqual(valor, Decimal('15.5'))

    @caso('RF-005', 'Validar que el porcentaje acepte punto decimal.', "porcentaje: '15.5'", 'Porcentaje = 15.5')
    def test_bonificacion_acepta_punto(self):
        valor = self.porcentaje_limpio('15.5')
        self.obtenido(f'Porcentaje = {valor}')
        self.assertEqual(valor, Decimal('15.5'))

    @caso('RF-005', 'Validar que la meta de bonificación se muestre con formato de moneda.',
          'Bonificación con meta 1500000', "Se muestra '$1.500.000' y no '1500000.00'")
    def test_novedades_muestra_montos_formateados(self):
        self.client.force_login(self.gerente)
        ConfiguracionBonificacion.objects.create(
            usuario=self.empleado, porcentaje=Decimal('15.5'), meta_mensual=Decimal('1500000'))
        html = self.client.get(reverse('novedades')).content.decode()
        self.obtenido(f"'$1.500.000' visible: {'$1.500.000' in html}; '1500000.00' visible: {'1500000.00' in html}")
        self.assertTrue('$1.500.000' in html and '1500000.00' not in html)

    @caso('RF-002', 'Validar el registro de horas extra desde la ventana Novedades.',
          'POST horas extra: ayer, 08:00 a 19:00, motivo Inventario', '1 registro de horas extra guardado')
    def test_post_valido_horas_extra_crea_registro(self):
        self.client.force_login(self.gerente)
        self.client.post(reverse('horas_extra'), {
            'usuario': self.empleado.pk, 'fecha': (timezone.localdate() - timedelta(days=1)).isoformat(),
            'hora_ingreso': '08:00', 'hora_salida': '19:00', 'motivo': 'Inventario'})
        cantidad = HoraExtra.objects.filter(usuario=self.empleado).count()
        self.obtenido(f'Registros de horas extra: {cantidad}')
        self.assertEqual(cantidad, 1)


class ReporteMensualViewTest(CasoPruebaMixin, TestCase):
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

    def estado_para(self, usuario):
        self.client.force_login(usuario)
        return self.client.get(reverse('reporte_mensual')).status_code

    @caso('RNF-003', 'Validar que el Gerente pueda ver los reportes de nómina.', 'Gerente abre /nomina/reportes/', 'HTTP 200')
    def test_gerente_ve_reportes(self):
        estado = self.estado_para(self.gerente)
        self.obtenido(f'HTTP {estado}')
        self.assertEqual(estado, 200)

    @caso('RNF-003', 'Validar que el Auxiliar Administrativo pueda ver los reportes.', 'Auxiliar abre /nomina/reportes/', 'HTTP 200')
    def test_auxiliar_ve_reportes(self):
        estado = self.estado_para(self.auxiliar)
        self.obtenido(f'HTTP {estado}')
        self.assertEqual(estado, 200)

    @caso('RNF-003', 'Validar que un Vendedor no pueda ver los reportes.', 'Vendedor abre /nomina/reportes/', 'HTTP 403')
    def test_vendedor_no_ve_reportes(self):
        estado = self.estado_para(self.vendedor)
        self.obtenido(f'HTTP {estado}')
        self.assertEqual(estado, 403)

    @caso('RNF-003', 'Validar que un usuario sin sesión sea enviado al inicio de sesión.', 'Visitante anónimo abre /nomina/reportes/', 'HTTP 302 a /login/')
    def test_anonimo_redirige_login(self):
        respuesta = self.client.get(reverse('reporte_mensual'))
        self.obtenido(f'HTTP {respuesta.status_code}; redirección a {respuesta.get("Location")}')
        self.assertTrue(respuesta.status_code == 302 and respuesta['Location'].startswith('/login/'))

    def reporte_septiembre(self):
        self._crear_nomina(self.gerente, Nomina.Estado.ACEPTADA, '920000')
        self._crear_nomina(self.auxiliar, Nomina.Estado.PENDIENTE, '920000')
        self.client.force_login(self.gerente)
        return self.client.get(reverse('reporte_mensual'), {'periodo': '2026-09'}).content.decode()

    @caso('RF-004', 'Validar que el reporte mensual liste solo empleados con nómina aceptada.',
          '2026-09: nómina ACEPTADA de reporte-gerente y PENDIENTE de reporte-auxiliar', 'Aparece reporte-gerente y no reporte-auxiliar')
    def test_reporte_lista_solo_aceptadas(self):
        html = self.reporte_septiembre()
        self.obtenido(f"reporte-gerente visible: {'reporte-gerente' in html}; reporte-auxiliar visible: {'reporte-auxiliar' in html}")
        self.assertTrue('reporte-gerente' in html and 'reporte-auxiliar' not in html)

    @caso('RF-004', 'Validar que el reporte mensual muestre los montos con formato de moneda.',
          '2026-09: nómina aceptada con total 920000', "Se muestra '$920.000'")
    def test_reporte_formatea_total(self):
        html = self.reporte_septiembre()
        self.obtenido(f"'$920.000' visible: {'$920.000' in html}")
        self.assertIn('$920.000', html)

    @caso('RF-004', 'Validar el mensaje del reporte cuando el mes no existe.', "periodo: '2026-13'", 'El mes debe estar entre 01 y 12.')
    def test_reporte_mes_invalido(self):
        self.client.force_login(self.gerente)
        respuesta = self.client.get(reverse('reporte_mensual'), {'periodo': '2026-13'})
        mensaje = 'El mes debe estar entre 01 y 12.'
        self.obtenido(f'HTTP {respuesta.status_code}; mensaje visible: {mensaje in respuesta.content.decode()}')
        self.assertContains(respuesta, mensaje)

    @caso('RF-004', 'Validar el mensaje del reporte cuando el periodo no tiene formato AAAA-MM.', "periodo: 'abc'",
          'El período debe tener el formato AAAA-MM (ej: 2026-09).')
    def test_reporte_formato_invalido(self):
        self.client.force_login(self.gerente)
        respuesta = self.client.get(reverse('reporte_mensual'), {'periodo': 'abc'})
        mensaje = 'El período debe tener el formato AAAA-MM (ej: 2026-09).'
        self.obtenido(f'HTTP {respuesta.status_code}; mensaje visible: {mensaje in respuesta.content.decode()}')
        self.assertContains(respuesta, mensaje)


class ReportePDFViewTest(CasoPruebaMixin, TestCase):
    def setUp(self):
        self.gerente_group, _ = Group.objects.get_or_create(name='Gerente')
        self.vendedor_group, _ = Group.objects.get_or_create(name='Vendedor')
        self.gerente = Usuario.objects.create_user(
            username='reporte-pdf-gerente', email='reporte-pdf-gerente@example.com', password='test-password')
        self.vendedor = Usuario.objects.create_user(
            username='reporte-pdf-vendedor', email='reporte-pdf-vendedor@example.com', password='test-password')
        self.gerente.groups.add(self.gerente_group)
        self.vendedor.groups.add(self.vendedor_group)

    def descargar(self, periodo='2026-09', con_nomina=True):
        if con_nomina:
            Nomina.objects.create(
                usuario=self.gerente, periodo='2026-09', estado=Nomina.Estado.ACEPTADA,
                salario_bruto=Decimal('1000000'), valor_bonificacion=Decimal('0'),
                valor_horas_extra=Decimal('0'), deducciones=Decimal('80000'),
                deduccion_salud=Decimal('40000'), deduccion_pension=Decimal('40000'),
                total_pagar=Decimal('920000'),
            )
        self.client.force_login(self.gerente)
        return self.client.get(reverse('reporte_mensual_pdf'), {'periodo': periodo})

    @caso('RF-004', 'Validar que el reporte mensual se descargue como PDF.', 'Gerente descarga el PDF de 2026-09',
          'HTTP 200; Content-Type application/pdf; contenido inicia con %PDF')
    def test_exporta_pdf(self):
        respuesta = self.descargar()
        self.obtenido(f"HTTP {respuesta.status_code}; tipo {respuesta['Content-Type']}; inicio {respuesta.content[:4]!r}")
        self.assertTrue(respuesta['Content-Type'] == 'application/pdf' and respuesta.content.startswith(b'%PDF'))

    @caso('RF-004', 'Validar el nombre del archivo PDF descargado.', 'Gerente descarga el PDF de 2026-09',
          'Archivo reporte_nomina_2026-09.pdf')
    def test_nombre_archivo_pdf(self):
        respuesta = self.descargar()
        self.obtenido(f"Content-Disposition: {respuesta['Content-Disposition']}")
        self.assertIn('reporte_nomina_2026-09.pdf', respuesta['Content-Disposition'])

    @caso('RF-017', 'Validar que la exportación del PDF quede en la auditoría.', 'Gerente descarga el PDF de 2026-09',
          'Registro de auditoría con acción EXPORTAR del Gerente')
    def test_exportar_pdf_registra_auditoria(self):
        self.descargar()
        existe = Auditoria.objects.filter(usuario=self.gerente, accion=Auditoria.Accion.EXPORTAR).exists()
        self.obtenido(f'Auditoría EXPORTAR registrada: {existe}')
        self.assertTrue(existe)

    @caso('RF-004', 'Validar que un mes sin nóminas también genere un PDF válido.', 'PDF de 2026-09 sin nóminas',
          'HTTP 200 y contenido que inicia con %PDF')
    def test_mes_vacio_devuelve_pdf_valido(self):
        respuesta = self.descargar(con_nomina=False)
        self.obtenido(f'HTTP {respuesta.status_code}; inicio {respuesta.content[:4]!r}')
        self.assertTrue(respuesta.status_code == 200 and respuesta.content.startswith(b'%PDF'))

    @caso('RNF-003', 'Validar que un Vendedor no pueda descargar el PDF.', 'Vendedor solicita el PDF de 2026-09', 'HTTP 403')
    def test_vendedor_no_descarga_pdf(self):
        self.client.force_login(self.vendedor)
        estado = self.client.get(reverse('reporte_mensual_pdf'), {'periodo': '2026-09'}).status_code
        self.obtenido(f'HTTP {estado}')
        self.assertEqual(estado, 403)

    @caso('RNF-003', 'Validar que un visitante sin sesión no pueda descargar el PDF.', 'Anónimo solicita el PDF de 2026-09', 'HTTP 302 (al inicio de sesión)')
    def test_anonimo_no_descarga_pdf(self):
        estado = self.client.get(reverse('reporte_mensual_pdf'), {'periodo': '2026-09'}).status_code
        self.obtenido(f'HTTP {estado}')
        self.assertEqual(estado, 302)

    @caso('RF-004', 'Validar que un periodo inválido en el PDF regrese a la pantalla de reportes.', "periodo: '2026-13'",
          'HTTP 302 a /nomina/reportes/')
    def test_pdf_periodo_invalido(self):
        respuesta = self.descargar(periodo='2026-13', con_nomina=False)
        self.obtenido(f'HTTP {respuesta.status_code}; redirección a {respuesta.get("Location")}')
        self.assertEqual(respuesta.get('Location'), reverse('reporte_mensual'))


class PreNominaIntegracionViewTest(CasoPruebaMixin, TestCase):
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

    def _solicitud(self):
        return Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=self.periodo)

    @caso('RF-008', 'Validar que el Gerente calcule la pre-nómina desde la pantalla de cálculo.',
          'Gerente envía el periodo actual', '4 nóminas PENDIENTES (una por usuario activo)')
    def test_calcular_crea_pendientes(self):
        self._calcular()
        cantidad = Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.PENDIENTE).count()
        self.obtenido(f'Nóminas pendientes: {cantidad}')
        self.assertEqual(cantidad, 4)

    @caso('RF-008', 'Validar que la pantalla informe cuando el periodo ya fue calculado.',
          'Gerente calcula dos veces el periodo actual', "Mensaje 'ya fue calculada' y siguen 4 nóminas")
    def test_calcular_dos_veces_informa(self):
        self._calcular()
        segunda = self.client.post(reverse('calculo_nomina'), {'periodo': self.periodo}, follow=True)
        cantidad = Nomina.objects.filter(periodo=self.periodo).count()
        self.obtenido(f"Mensaje visible: {'ya fue calculada' in segunda.content.decode()}; nóminas: {cantidad}")
        self.assertContains(segunda, 'ya fue calculada')
        self.assertEqual(cantidad, 4)

    @caso('RF-007', 'Validar que la pre-nómina aparezca en la bandeja del Auxiliar.',
          'Pre-nómina calculada; el Auxiliar abre la bandeja', "La bandeja muestra 'Pre-nómina'")
    def test_bandeja_muestra_prenomina(self):
        self._calcular()
        self.client.force_login(self.auxiliar)
        html = self.client.get(reverse('bandeja_aprobacion')).content.decode()
        self.obtenido(f"'Pre-nómina' visible en la bandeja: {'Pre-nómina' in html}")
        self.assertIn('Pre-nómina', html)

    @caso('RF-007', 'Validar que el Auxiliar vea el detalle de la pre-nómina por empleado.',
          'Auxiliar abre el detalle de la pre-nómina', "HTTP 200 con 'Empleada Prueba'")
    def test_detalle_visible_para_auxiliar(self):
        self._calcular()
        self.client.force_login(self.auxiliar)
        respuesta = self.client.get(reverse('prenomina_detalle', args=[self._solicitud().pk]))
        self.obtenido(f"HTTP {respuesta.status_code}; 'Empleada Prueba' visible: {'Empleada Prueba' in respuesta.content.decode()}")
        self.assertContains(respuesta, 'Empleada Prueba')

    @caso('RNF-003', 'Validar que solo el Auxiliar pueda abrir el detalle de la pre-nómina.',
          'Gerente y Vendedor abren el detalle', 'HTTP 403 para ambos')
    def test_detalle_restringido(self):
        self._calcular()
        detalle = reverse('prenomina_detalle', args=[self._solicitud().pk])
        estados = []
        for usuario in (self.gerente, self.vendedor):
            self.client.force_login(usuario)
            estados.append(self.client.get(detalle).status_code)
        self.obtenido(f'Gerente: HTTP {estados[0]}; Vendedor: HTTP {estados[1]}')
        self.assertEqual(estados, [403, 403])

    def _aprobar(self):
        self._calcular()
        self.client.force_login(self.auxiliar)
        self.client.post(reverse('bandeja_aprobacion'), {'solicitud_id': self._solicitud().pk, 'accion': 'aprobar'})

    @caso('RF-007', 'Validar que al aprobar desde la bandeja no queden nóminas pendientes.',
          'Auxiliar aprueba la pre-nómina', '0 PENDIENTES y nóminas ACEPTADAS')
    def test_aprobar_desde_bandeja(self):
        self._aprobar()
        pendientes = Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.PENDIENTE).count()
        aceptadas = Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.ACEPTADA).count()
        self.obtenido(f'Pendientes: {pendientes}; aceptadas: {aceptadas}')
        self.assertEqual((pendientes, aceptadas), (0, 4))

    @caso('RF-004', 'Validar que la nómina aprobada aparezca en el reporte mensual.',
          'Pre-nómina aprobada; Gerente abre el reporte del periodo', "El reporte muestra 'Empleada Prueba'")
    def test_aprobada_aparece_en_reporte(self):
        self._aprobar()
        self.client.force_login(self.gerente)
        html = self.client.get(reverse('reporte_mensual'), {'periodo': self.periodo}).content.decode()
        self.obtenido(f"'Empleada Prueba' en el reporte: {'Empleada Prueba' in html}")
        self.assertIn('Empleada Prueba', html)

    @caso('RF-004', 'Validar que el empleado consulte su nómina aprobada.',
          'Pre-nómina aprobada; el empleado consulta su nómina', "Se muestra 'Total a pagar'")
    def test_empleado_consulta_nomina_aprobada(self):
        self._aprobar()
        self.client.force_login(self.empleado)
        html = self.client.get(reverse('nomina_consultar'), {'periodo': self.periodo}).content.decode()
        self.obtenido(f"'Total a pagar' visible: {'Total a pagar' in html}")
        self.assertIn('Total a pagar', html)

    @caso('RF-012', 'Validar que el perfil del empleado muestre su último pago.',
          'Pre-nómina aprobada; el empleado abre su perfil', "El perfil muestra 'Último pago'")
    def test_perfil_muestra_ultimo_pago(self):
        self._aprobar()
        self.client.force_login(self.empleado)
        html = self.client.get(reverse('perfil_actual')).content.decode()
        self.obtenido(f"'Último pago' visible: {'Último pago' in html}")
        self.assertIn('Último pago', html)

    @caso('RF-007', 'Validar que la bandeja exija motivo para rechazar la pre-nómina.',
          'Auxiliar rechaza sin escribir motivo', "Mensaje 'Debes escribir el motivo' y solicitud PENDIENTE")
    def test_rechazo_requiere_motivo(self):
        self._calcular()
        solicitud = self._solicitud()
        self.client.force_login(self.auxiliar)
        respuesta = self.client.post(reverse('bandeja_aprobacion'), {'solicitud_id': solicitud.pk, 'accion': 'rechazar'}, follow=True)
        solicitud.refresh_from_db()
        self.obtenido(f"Mensaje visible: {'Debes escribir el motivo' in respuesta.content.decode()}; estado: {solicitud.estado}")
        self.assertContains(respuesta, 'Debes escribir el motivo')
        self.assertEqual(solicitud.estado, Solicitud.Estado.PENDIENTE)

    @caso('RF-008', 'Validar que tras rechazar la pre-nómina el Gerente pueda recalcularla.',
          "Rechazo con motivo 'Datos errados' y nuevo cálculo", '4 nóminas PENDIENTES nuevas')
    def test_rechazo_permite_recalculo(self):
        self._calcular()
        self.client.force_login(self.auxiliar)
        self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': self._solicitud().pk, 'accion': 'rechazar', 'motivo_rechazo': 'Datos errados'})
        self._calcular()
        cantidad = Nomina.objects.filter(periodo=self.periodo, estado=Nomina.Estado.PENDIENTE).count()
        self.obtenido(f'Nóminas pendientes tras recalcular: {cantidad}')
        self.assertEqual(cantidad, 4)

    def _rechazar_y_recalcular(self):
        self._calcular()
        vieja = self._solicitud()
        self.client.force_login(self.auxiliar)
        self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': vieja.pk, 'accion': 'rechazar', 'motivo_rechazo': 'Datos errados'})
        self.empleado.salario_base = Decimal('2000000')
        self.empleado.save(update_fields=['salario_base'])
        self._calcular()
        nueva = Solicitud.objects.exclude(pk=vieja.pk).get(tipo=Solicitud.Tipo.NOMINA, periodo=self.periodo)
        self.client.force_login(self.auxiliar)
        return vieja, nueva

    @caso('RF-007', 'Validar que el detalle de una pre-nómina rechazada no muestre el lote recalculado.',
          'Pre-nómina rechazada; salario cambiado a 2.000.000 y recalculada', "Detalle antiguo: 'se reemplazaron' y sin '$1.840.000'")
    def test_detalle_rechazado_no_muestra_lote_recalculado(self):
        vieja, _ = self._rechazar_y_recalcular()
        html = self.client.get(reverse('prenomina_detalle', args=[vieja.pk])).content.decode()
        self.obtenido(f"'se reemplazaron' visible: {'se reemplazaron' in html}; '$1.840.000' visible: {'$1.840.000' in html}")
        self.assertTrue('se reemplazaron' in html and '$1.840.000' not in html)

    @caso('RF-008', 'Validar que el nuevo cálculo use el salario actualizado del empleado.',
          'Salario cambiado a 2.000.000 y pre-nómina recalculada', "Detalle nuevo muestra '$1.840.000'")
    def test_detalle_nuevo_usa_salario_actualizado(self):
        _, nueva = self._rechazar_y_recalcular()
        html = self.client.get(reverse('prenomina_detalle', args=[nueva.pk])).content.decode()
        self.obtenido(f"'$1.840.000' visible: {'$1.840.000' in html}")
        self.assertIn('$1.840.000', html)

    @caso('RF-004', 'Validar que el empleado no vea montos de una nómina aún en revisión.',
          'Pre-nómina PENDIENTE; el empleado consulta', "Mensaje 'está en revisión' sin mostrar '$1.000.000'")
    def test_nomina_pendiente_no_expone_montos(self):
        self._calcular()
        self.client.force_login(self.empleado)
        html = self.client.get(reverse('nomina_consultar'), {'periodo': self.periodo}).content.decode()
        self.obtenido(f"'está en revisión' visible: {'está en revisión' in html}; '$1.000.000' visible: {'$1.000.000' in html}")
        self.assertTrue('está en revisión' in html and '$1.000.000' not in html)

    @caso('RF-008', 'Validar el mensaje de periodo inválido en la pantalla de cálculo.',
          "periodo: '2026/09'", "Mensaje con 'formato AAAA-MM'")
    def test_calculo_periodo_invalido(self):
        self.client.force_login(self.gerente)
        respuesta = self.client.post(reverse('calculo_nomina'), {'periodo': '2026/09'}, follow=True)
        self.obtenido(f"Mensaje visible: {'formato AAAA-MM' in respuesta.content.decode()}")
        self.assertContains(respuesta, 'formato AAAA-MM')
