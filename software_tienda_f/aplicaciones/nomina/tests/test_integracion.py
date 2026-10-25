from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from aplicaciones.gestion_usuario.models import Auditoria, Usuario
from .utils import crear_grupos, crear_usuario
from ..models import HoraExtra, Nomina, Solicitud


class IntegracionNominaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupos = crear_grupos()
        cls.gerente = crear_usuario('gerente-integracion', 'Gerente', first_name='Gema', last_name='Gerente')
        cls.auxiliar = crear_usuario('auxiliar-integracion', 'Auxiliar Administrativo', first_name='Alicia', last_name='Auxiliar')
        cls.vendedor = crear_usuario('vendedor-integracion', 'Vendedor', first_name='Victor', last_name='Vendedor')
        cls.solicitud_detalle = Solicitud.objects.create(
            usuario=cls.gerente, tipo=Solicitud.Tipo.NOMINA, periodo='2020-01',
            motivo='Prenomina de prueba',
        )

    def iniciar_sesion(self, usuario):
        self.client.force_login(usuario)

    def crear_empleado(self, nombre='Elena', usuario='empleada-integracion'):
        self.iniciar_sesion(self.gerente)
        respuesta = self.client.post(reverse('usuario_crear'), {
            'username': usuario, 'first_name': nombre, 'last_name': 'Vendedora',
            'email': usuario + '@example.com', 'identificacion': '12345678',
            'fecha_ingreso': '2020-01-15', 'salario_base': '2000000',
            'estado': 'ACTIVO', 'frecuencia_pago': 'MENSUAL',
            'metodo_pago': 'EFECTIVO', 'groups': [self.grupos['Vendedor'].pk],
            'password1': 'Clave#2026', 'password2': 'Clave#2026',
        }, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        empleado = Usuario.objects.get(username=usuario)
        return empleado

    def calcular(self, periodo):
        return self.client.post(reverse('calculo_nomina'), {'periodo': periodo}, follow=True)

    def periodo_ayer(self):
        ayer = date.today() - timedelta(days=1)
        return ayer, ayer.strftime('%Y-%m')

    def registrar_bonificacion(self, empleado, meta='1000000'):
        return self.client.post(reverse('bonificaciones'), {
            'usuario': empleado.pk, 'porcentaje': '10', 'meta_mensual': meta,
        }, follow=True)

    def aprobar(self, solicitud):
        return self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': solicitud.pk, 'accion': 'aprobar', 'motivo_rechazo': '',
        }, follow=True)

    def test_ciclo_completo_novedades_prenomina_aprobacion_reporte(self):
        """Recorre creación, novedades, revisión auxiliar, reporte y auditoría."""
        empleado = self.crear_empleado()
        ayer, periodo = self.periodo_ayer()
        self.registrar_bonificacion(empleado)
        self.client.post(reverse('horas_extra'), {
            'usuario': empleado.pk, 'fecha': ayer.isoformat(), 'hora_ingreso': '07:00',
            'hora_salida': '19:00', 'motivo': 'Inventario mensual',
        }, follow=True)
        self.calcular(periodo)

        nomina = Nomina.objects.get(usuario=empleado, periodo=periodo)
        solicitud = Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=periodo)
        self.assertEqual(nomina.estado, Nomina.Estado.PENDIENTE)
        self.assertEqual(solicitud.estado, Solicitud.Estado.PENDIENTE)
        reporte = self.client.get(reverse('reporte_mensual'), {'periodo': periodo})
        self.assertNotContains(reporte, 'Elena Vendedora')
        self.client.force_login(empleado)
        consulta = self.client.get(reverse('nomina_consultar'), {'periodo': periodo})
        self.assertContains(consulta, 'en revisi')

        self.client.force_login(self.auxiliar)
        bandeja = self.client.get(reverse('bandeja_aprobacion'), follow=True)
        self.assertContains(bandeja, 'Pre-nómina')
        detalle = self.client.get(reverse('prenomina_detalle', args=[solicitud.pk]), follow=True)
        self.assertContains(detalle, 'Elena Vendedora')
        self.aprobar(solicitud)

        self.client.force_login(self.gerente)
        reporte = self.client.get(reverse('reporte_mensual'), {'periodo': periodo})
        self.assertContains(reporte, 'Elena Vendedora')
        self.assertContains(reporte, '$')
        nomina.refresh_from_db()
        self.assertEqual(nomina.deduccion_salud, Decimal('80000'))
        self.assertEqual(nomina.deduccion_pension, Decimal('80000'))
        pdf = self.client.get(reverse('reporte_mensual_pdf'), {'periodo': periodo})
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.client.force_login(empleado)
        self.assertContains(self.client.get(reverse('nomina_consultar'), {'periodo': periodo}), '$')
        self.assertContains(self.client.get(reverse('perfil_actual')), 'Último pago')
        auditorias = Auditoria.objects.values_list('accion', 'detalle')
        self.assertTrue(auditorias.filter(accion=Auditoria.Accion.CREAR, detalle__contains='usuario').exists())
        self.assertTrue(auditorias.filter(accion=Auditoria.Accion.ACTUALIZAR, detalle__contains='bonificación').exists())
        self.assertTrue(auditorias.filter(accion=Auditoria.Accion.ACTUALIZAR, detalle__contains='Aceptó').exists())
        self.assertTrue(auditorias.filter(accion=Auditoria.Accion.CALCULAR).exists())
        self.assertTrue(auditorias.filter(accion=Auditoria.Accion.EXPORTAR).exists())

    def test_rechazo_y_recalculo_con_novedad_corregida(self):
        """Rechaza una pre-nómina, corrige la novedad y acepta el nuevo cálculo."""
        empleado = self.crear_empleado()
        _, periodo = self.periodo_ayer()
        self.registrar_bonificacion(empleado)
        self.calcular(periodo)
        solicitud = Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=periodo)
        self.client.force_login(self.auxiliar)
        sin_motivo = self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': solicitud.pk, 'accion': 'rechazar', 'motivo_rechazo': '',
        }, follow=True)
        self.assertContains(sin_motivo, 'Debes escribir el motivo del rechazo de la pre-nómina.')
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, Solicitud.Estado.PENDIENTE)
        self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': solicitud.pk, 'accion': 'rechazar', 'motivo_rechazo': 'Corregir meta',
        }, follow=True)

        self.client.force_login(self.gerente)
        calculo = self.client.get(reverse('calculo_nomina'), {'periodo': periodo}, follow=True)
        self.assertContains(calculo, 'Corregir meta')
        self.assertContains(calculo, 'Calcular')
        self.registrar_bonificacion(empleado, '2000000')
        self.calcular(periodo)
        nuevo = Nomina.objects.get(usuario=empleado, periodo=periodo)
        self.assertEqual(nuevo.valor_bonificacion, Decimal('200000'))
        self.client.force_login(self.auxiliar)
        detalle = self.client.get(reverse('prenomina_detalle', args=[solicitud.pk]), follow=True)
        self.assertContains(detalle, 'se reemplazaron')
        nueva_solicitud = Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=periodo, estado=Solicitud.Estado.PENDIENTE)
        self.client.force_login(self.auxiliar)
        self.aprobar(nueva_solicitud)
        self.client.force_login(self.gerente)
        reporte = self.client.get(reverse('reporte_mensual'), {'periodo': periodo})
        self.assertContains(reporte, 'Elena Vendedora')
        self.assertContains(reporte, '$200.000')

    def test_novedades_bloqueadas_despues_de_calcular(self):
        """Impide registrar horas del período después de generar la pre-nómina."""
        empleado = self.crear_empleado()
        ayer, periodo = self.periodo_ayer()
        self.calcular(periodo)
        nomina = Nomina.objects.get(usuario=empleado, periodo=periodo)
        extra_antes = HoraExtra.objects.count()
        respuesta = self.client.post(reverse('horas_extra'), {
            'usuario': empleado.pk, 'fecha': ayer.isoformat(), 'hora_ingreso': '07:00',
            'hora_salida': '19:00', 'motivo': 'Inventario mensual',
        }, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ya fue calculada')
        self.assertEqual(HoraExtra.objects.count(), extra_antes)
        nomina.refresh_from_db()
        self.assertEqual(nomina.valor_horas_extra, Decimal('0'))

    def test_permisos_por_rol_en_modulos_nuevos(self):
        """Comprueba los permisos de cada ruta para roles y visitantes."""
        rutas = [
            ('reporte_mensual', {}, 200, 200, 403, 302),
            ('reporte_mensual_pdf', {}, 200, 200, 403, 302),
            ('novedades', {}, 200, 403, 403, 302),
            ('calculo_nomina', {}, 200, 403, 403, 302),
            ('bandeja_aprobacion', {}, 403, 200, 403, 302),
            ('prenomina_detalle', {'pk': self.solicitud_detalle.pk}, 403, 200, 403, 302),
        ]
        roles = [('Gerente', self.gerente), ('Auxiliar', self.auxiliar), ('Vendedor', self.vendedor), ('anónimo', None)]
        for nombre, kwargs, gerente, auxiliar, vendedor, anonimo in rutas:
            esperados = (gerente, auxiliar, vendedor, anonimo)
            for (rol, usuario), esperado in zip(roles, esperados):
                with self.subTest(ruta=nombre, rol=rol):
                    self.client.logout()
                    if usuario:
                        self.client.force_login(usuario)
                    respuesta = self.client.get(reverse(nombre, kwargs=kwargs))
                    self.assertEqual(respuesta.status_code, esperado)

    def test_vacaciones_aprobadas_en_bandeja_conviven_con_prenomina(self):
        """Verifica que aprobar vacaciones y pre-nómina no mezcle sus estados."""
        empleado = self.crear_empleado()
        hoy = date.today()
        self.client.force_login(empleado)
        respuesta = self.client.post(reverse('vacaciones'), {
            'motivo': 'Descanso familiar', 'fecha_desde': (hoy + timedelta(days=10)).isoformat(),
            'fecha_hasta': (hoy + timedelta(days=12)).isoformat(),
        }, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        vacaciones = Solicitud.objects.get(usuario=empleado, tipo=Solicitud.Tipo.VACACIONES)
        _, periodo = self.periodo_ayer()
        self.client.force_login(self.gerente)
        self.calcular(periodo)
        prenomina = Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=periodo)
        self.client.force_login(self.auxiliar)
        bandeja = self.client.get(reverse('bandeja_aprobacion'), follow=True)
        self.assertContains(bandeja, 'Vacaciones')
        self.assertContains(bandeja, 'Pre-nómina')
        self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': vacaciones.pk, 'accion': 'aprobar',
        }, follow=True)
        prenomina.refresh_from_db()
        vacaciones.refresh_from_db()
        self.assertEqual(prenomina.estado, Solicitud.Estado.PENDIENTE)
        self.assertEqual(vacaciones.estado, Solicitud.Estado.ACEPTADA)
        self.aprobar(prenomina)
        vacaciones.refresh_from_db()
        self.assertEqual(vacaciones.estado, Solicitud.Estado.ACEPTADA)

    def test_validacion_formulario_usuario_no_guarda_datos_invalidos(self):
        """Rechaza nombres e identificación con caracteres no permitidos."""
        self.iniciar_sesion(self.gerente)
        respuesta = self.client.post(reverse('usuario_crear'), {
            'username': 'invalido-integracion', 'first_name': 'Ana2', 'last_name': 'Vendedora',
            'email': 'invalido-integracion@example.com', 'identificacion': '12ABC678',
            'fecha_ingreso': '2020-01-15', 'salario_base': '2000000',
            'estado': 'ACTIVO', 'groups': [self.grupos['Vendedor'].pk],
            'password1': 'Clave#2026', 'password2': 'Clave#2026',
        }, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'El campo nombres solo puede contener letras y espacios.')
        self.assertContains(respuesta, 'La identificación solo puede contener números.')
        self.assertFalse(Usuario.objects.filter(username='invalido-integracion').exists())
