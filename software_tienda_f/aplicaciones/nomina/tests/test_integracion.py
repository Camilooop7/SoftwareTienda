from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from aplicaciones.gestion_usuario.models import Auditoria, Usuario
from .utils import crear_grupos, crear_usuario
from ..models import HoraExtra, Nomina, Solicitud


class IntegracionNominaTest(CasoPruebaMixin, TestCase):
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


    def preparar_novedades_y_calcular(self):
        empleado = self.crear_empleado()
        ayer, periodo = self.periodo_ayer()
        self.registrar_bonificacion(empleado)
        self.client.post(reverse('horas_extra'), {
            'usuario': empleado.pk, 'fecha': ayer.isoformat(), 'hora_ingreso': '07:00',
            'hora_salida': '19:00', 'motivo': 'Inventario mensual',
        }, follow=True)
        self.calcular(periodo)
        return empleado, periodo, Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=periodo)

    def ciclo_completo(self):
        empleado, periodo, solicitud = self.preparar_novedades_y_calcular()
        self.client.force_login(self.auxiliar)
        self.client.get(reverse('prenomina_detalle', args=[solicitud.pk]), follow=True)
        self.aprobar(solicitud)
        self.client.force_login(self.gerente)
        return empleado, periodo

    @caso('RF-004', 'Integración: una pre-nómina pendiente no aparece en el reporte ni muestra montos al empleado.',
          'Gerente crea empleado, registra bonificación y horas extra y calcula; nadie aprueba aún',
          "Reporte sin 'Elena Vendedora'; el empleado ve 'en revisión'")
    def test_prenomina_pendiente_no_se_publica(self):
        empleado, periodo, _ = self.preparar_novedades_y_calcular()
        reporte = self.client.get(reverse('reporte_mensual'), {'periodo': periodo}).content.decode()
        self.client.force_login(empleado)
        consulta = self.client.get(reverse('nomina_consultar'), {'periodo': periodo}).content.decode()
        en_reporte = 'Elena Vendedora' in reporte
        en_revision = 'en revisi' in consulta
        self.obtenido(f'Empleado en el reporte: {en_reporte}; el empleado ve "en revisión": {en_revision}')
        self.assertEqual((en_reporte, en_revision), (False, True))

    @caso('RF-008', 'Integración: ciclo completo novedades → pre-nómina → aprobación → reporte.',
          'Empleado salario 2.000.000, bonificación, horas extra; Gerente calcula y Auxiliar aprueba',
          "Reporte con 'Elena Vendedora'; salud 80000; pensión 80000; nómina ACEPTADA")
    def test_ciclo_completo_novedades_prenomina_aprobacion_reporte(self):
        empleado, periodo = self.ciclo_completo()
        reporte = self.client.get(reverse('reporte_mensual'), {'periodo': periodo}).content.decode()
        nomina = Nomina.objects.get(usuario=empleado, periodo=periodo)
        self.obtenido(f"Empleado en el reporte: {'Elena Vendedora' in reporte}; estado {nomina.estado}; "
                      f"salud {nomina.deduccion_salud}; pensión {nomina.deduccion_pension}")
        self.assertEqual(('Elena Vendedora' in reporte, nomina.estado, nomina.deduccion_salud, nomina.deduccion_pension),
                         (True, Nomina.Estado.ACEPTADA, Decimal('80000'), Decimal('80000')))

    @caso('RF-012', 'Integración: tras la aprobación el empleado ve su nómina y su último pago.',
          'Ciclo completo aprobado; el empleado consulta nómina y perfil',
          "Consulta con montos ('$') y perfil con 'Último pago'")
    def test_ciclo_completo_empleado_ve_pago(self):
        empleado, periodo = self.ciclo_completo()
        self.client.force_login(empleado)
        consulta = self.client.get(reverse('nomina_consultar'), {'periodo': periodo}).content.decode()
        perfil = self.client.get(reverse('perfil_actual')).content.decode()
        self.obtenido(f"Montos en la consulta: {'$' in consulta}; 'Último pago' en el perfil: {'Último pago' in perfil}")
        self.assertTrue('$' in consulta and 'Último pago' in perfil)

    @caso('RF-017', 'Integración: el ciclo completo deja rastro en la auditoría.',
          'Ciclo completo y exportación del PDF',
          'Auditoría con CREAR usuario, ACTUALIZAR bonificación, ACTUALIZAR aceptación, CALCULAR y EXPORTAR')
    def test_ciclo_completo_auditoria(self):
        _, periodo = self.ciclo_completo()
        self.client.get(reverse('reporte_mensual_pdf'), {'periodo': periodo})
        acciones = {
            'CREAR usuario': Auditoria.objects.filter(accion=Auditoria.Accion.CREAR, detalle__contains='usuario').exists(),
            'ACTUALIZAR bonificación': Auditoria.objects.filter(accion=Auditoria.Accion.ACTUALIZAR, detalle__contains='bonificación').exists(),
            'ACTUALIZAR aceptación': Auditoria.objects.filter(accion=Auditoria.Accion.ACTUALIZAR, detalle__contains='Aceptó').exists(),
            'CALCULAR': Auditoria.objects.filter(accion=Auditoria.Accion.CALCULAR).exists(),
            'EXPORTAR': Auditoria.objects.filter(accion=Auditoria.Accion.EXPORTAR).exists(),
        }
        faltantes = [nombre for nombre, existe in acciones.items() if not existe]
        self.obtenido(f'Acciones registradas: {sum(acciones.values())} de 5; faltantes: {faltantes or "ninguna"}')
        self.assertEqual(faltantes, [])

    def rechazar(self, solicitud, motivo):
        self.client.force_login(self.auxiliar)
        return self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': solicitud.pk, 'accion': 'rechazar', 'motivo_rechazo': motivo,
        }, follow=True)

    def calcular_y_rechazar(self):
        empleado = self.crear_empleado()
        _, periodo = self.periodo_ayer()
        self.registrar_bonificacion(empleado)
        self.calcular(periodo)
        solicitud = Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=periodo)
        self.rechazar(solicitud, 'Corregir meta')
        self.client.force_login(self.gerente)
        return empleado, periodo, solicitud

    @caso('RF-007', 'Integración: el Gerente ve el motivo del rechazo en la pantalla de cálculo.',
          "Auxiliar rechaza la pre-nómina con motivo 'Corregir meta'",
          "La pantalla de cálculo muestra 'Corregir meta' y permite calcular de nuevo")
    def test_rechazo_motivo_visible_para_gerente(self):
        _, periodo, _ = self.calcular_y_rechazar()
        calculo = self.client.get(reverse('calculo_nomina'), {'periodo': periodo}, follow=True).content.decode()
        self.obtenido(f"Motivo visible: {'Corregir meta' in calculo}; botón Calcular: {'Calcular' in calculo}")
        self.assertTrue('Corregir meta' in calculo and 'Calcular' in calculo)

    @caso('RF-008', 'Integración: el recálculo tras el rechazo usa la novedad corregida y se publica al aprobar.',
          'Rechazo; meta corregida a 2.000.000; nuevo cálculo y aprobación',
          "Bonificación 200000 y reporte con '$200.000'")
    def test_rechazo_y_recalculo_con_novedad_corregida(self):
        empleado, periodo, _ = self.calcular_y_rechazar()
        self.registrar_bonificacion(empleado, '2000000')
        self.calcular(periodo)
        nueva = Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=periodo, estado=Solicitud.Estado.PENDIENTE)
        self.client.force_login(self.auxiliar)
        self.aprobar(nueva)
        self.client.force_login(self.gerente)
        reporte = self.client.get(reverse('reporte_mensual'), {'periodo': periodo}).content.decode()
        bonificacion = Nomina.objects.get(usuario=empleado, periodo=periodo).valor_bonificacion
        self.obtenido(f"Bonificación recalculada: {bonificacion}; '$200.000' en el reporte: {'$200.000' in reporte}")
        self.assertEqual((bonificacion, '$200.000' in reporte), (Decimal('200000'), True))

    @caso('RF-002', 'Integración: no se registran horas extra después de calcular la nómina del mes.',
          'Pre-nómina calculada; Gerente intenta registrar horas extra de ayer',
          "Mensaje 'ya fue calculada'; no se crea hora extra y la nómina no cambia")
    def test_novedades_bloqueadas_despues_de_calcular(self):
        empleado = self.crear_empleado()
        ayer, periodo = self.periodo_ayer()
        self.calcular(periodo)
        extra_antes = HoraExtra.objects.count()
        respuesta = self.client.post(reverse('horas_extra'), {
            'usuario': empleado.pk, 'fecha': ayer.isoformat(), 'hora_ingreso': '07:00',
            'hora_salida': '19:00', 'motivo': 'Inventario mensual',
        }, follow=True)
        nuevas = HoraExtra.objects.count() - extra_antes
        valor = Nomina.objects.get(usuario=empleado, periodo=periodo).valor_horas_extra
        self.obtenido(f"Mensaje visible: {'ya fue calculada' in respuesta.content.decode()}; horas extra nuevas: {nuevas}; valor en nómina: {valor}")
        self.assertEqual(('ya fue calculada' in respuesta.content.decode(), nuevas, valor), (True, 0, Decimal('0')))

    def estados_por_rol(self, nombre, kwargs=None):
        estados = []
        for usuario in (self.gerente, self.auxiliar, self.vendedor, None):
            self.client.logout()
            if usuario:
                self.client.force_login(usuario)
            estados.append(self.client.get(reverse(nombre, kwargs=kwargs or {})).status_code)
        self.obtenido('Gerente {0}; Auxiliar {1}; Vendedor {2}; anónimo {3}'.format(*estados))
        return estados

    @caso('RF-013', 'Integración: permisos de la pantalla de reportes por rol.',
          'GET /nomina/reportes/ con cada rol y sin sesión', 'Gerente 200; Auxiliar 200; Vendedor 403; anónimo 302')
    def test_permisos_reporte_mensual(self):
        self.assertEqual(self.estados_por_rol('reporte_mensual'), [200, 200, 403, 302])

    @caso('RF-013', 'Integración: permisos de la descarga del PDF por rol.',
          'GET /nomina/reportes/pdf/ con cada rol y sin sesión', 'Gerente 200; Auxiliar 200; Vendedor 403; anónimo 302')
    def test_permisos_reporte_pdf(self):
        self.assertEqual(self.estados_por_rol('reporte_mensual_pdf'), [200, 200, 403, 302])

    @caso('RF-013', 'Integración: permisos de la ventana Novedades por rol.',
          'GET /nomina/novedades/ con cada rol y sin sesión', 'Gerente 200; Auxiliar 403; Vendedor 403; anónimo 302')
    def test_permisos_novedades(self):
        self.assertEqual(self.estados_por_rol('novedades'), [200, 403, 403, 302])

    @caso('RF-013', 'Integración: permisos del cálculo de nómina por rol.',
          'GET /nomina/calculo/ con cada rol y sin sesión', 'Gerente 200; Auxiliar 403; Vendedor 403; anónimo 302')
    def test_permisos_calculo(self):
        self.assertEqual(self.estados_por_rol('calculo_nomina'), [200, 403, 403, 302])

    @caso('RF-013', 'Integración: permisos de la bandeja de aprobación por rol.',
          'GET /nomina/bandeja/ con cada rol y sin sesión', 'Gerente 403; Auxiliar 200; Vendedor 403; anónimo 302')
    def test_permisos_bandeja(self):
        self.assertEqual(self.estados_por_rol('bandeja_aprobacion'), [403, 200, 403, 302])

    @caso('RF-013', 'Integración: permisos del detalle de pre-nómina por rol.',
          'GET detalle de pre-nómina con cada rol y sin sesión', 'Gerente 403; Auxiliar 200; Vendedor 403; anónimo 302')
    def test_permisos_detalle_prenomina(self):
        self.assertEqual(self.estados_por_rol('prenomina_detalle', {'pk': self.solicitud_detalle.pk}), [403, 200, 403, 302])

    def vacaciones_y_prenomina(self):
        empleado = self.crear_empleado()
        hoy = date.today()
        self.client.force_login(empleado)
        self.client.post(reverse('vacaciones'), {
            'motivo': 'Descanso familiar', 'fecha_desde': (hoy + timedelta(days=10)).isoformat(),
            'fecha_hasta': (hoy + timedelta(days=12)).isoformat(),
        }, follow=True)
        vacaciones = Solicitud.objects.get(usuario=empleado, tipo=Solicitud.Tipo.VACACIONES)
        _, periodo = self.periodo_ayer()
        self.client.force_login(self.gerente)
        self.calcular(periodo)
        prenomina = Solicitud.objects.get(tipo=Solicitud.Tipo.NOMINA, periodo=periodo)
        self.client.force_login(self.auxiliar)
        return vacaciones, prenomina

    @caso('RF-007', 'Integración: la bandeja muestra a la vez vacaciones y pre-nómina pendientes.',
          'Empleado solicita vacaciones y el Gerente calcula la pre-nómina', "La bandeja lista 'Vacaciones' y 'Pre-nómina'")
    def test_bandeja_lista_vacaciones_y_prenomina(self):
        self.vacaciones_y_prenomina()
        html = self.client.get(reverse('bandeja_aprobacion'), follow=True).content.decode()
        self.obtenido(f"'Vacaciones' visible: {'Vacaciones' in html}; 'Pre-nómina' visible: {'Pre-nómina' in html}")
        self.assertTrue('Vacaciones' in html and 'Pre-nómina' in html)

    @caso('RF-007', 'Integración: aprobar vacaciones no cambia el estado de la pre-nómina.',
          'Auxiliar aprueba solo las vacaciones', 'Vacaciones ACEPTADA; pre-nómina PENDIENTE')
    def test_aprobar_vacaciones_no_afecta_prenomina(self):
        vacaciones, prenomina = self.vacaciones_y_prenomina()
        self.aprobar(vacaciones)
        vacaciones.refresh_from_db()
        prenomina.refresh_from_db()
        self.obtenido(f'Vacaciones: {vacaciones.estado}; pre-nómina: {prenomina.estado}')
        self.assertEqual((vacaciones.estado, prenomina.estado), (Solicitud.Estado.ACEPTADA, Solicitud.Estado.PENDIENTE))

    @caso('RF-007', 'Integración: aprobar la pre-nómina no altera las vacaciones ya aprobadas.',
          'Auxiliar aprueba vacaciones y luego la pre-nómina', 'Vacaciones siguen ACEPTADA; pre-nómina ACEPTADA')
    def test_aprobar_prenomina_no_afecta_vacaciones(self):
        vacaciones, prenomina = self.vacaciones_y_prenomina()
        self.aprobar(vacaciones)
        self.aprobar(prenomina)
        vacaciones.refresh_from_db()
        prenomina.refresh_from_db()
        self.obtenido(f'Vacaciones: {vacaciones.estado}; pre-nómina: {prenomina.estado}')
        self.assertEqual((vacaciones.estado, prenomina.estado), (Solicitud.Estado.ACEPTADA, Solicitud.Estado.ACEPTADA))

    def crear_invalido(self):
        self.iniciar_sesion(self.gerente)
        return self.client.post(reverse('usuario_crear'), {
            'username': 'invalido-integracion', 'first_name': 'Ana2', 'last_name': 'Vendedora',
            'email': 'invalido-integracion@example.com', 'identificacion': '12ABC678',
            'fecha_ingreso': '2020-01-15', 'salario_base': '2000000',
            'estado': 'ACTIVO', 'groups': [self.grupos['Vendedor'].pk],
            'password1': 'Clave#2026', 'password2': 'Clave#2026',
        }, follow=True)

    @caso('RF-001', 'Integración: el registro muestra el error de nombres con números.',
          "first_name: 'Ana2'", 'El campo nombres solo puede contener letras y espacios.')
    def test_registro_nombre_invalido(self):
        respuesta = self.crear_invalido()
        mensaje = 'El campo nombres solo puede contener letras y espacios.'
        self.obtenido(f'Mensaje visible: {mensaje in respuesta.content.decode()}')
        self.assertContains(respuesta, mensaje)

    @caso('RF-001', 'Integración: el registro muestra el error de identificación con letras.',
          "identificacion: '12ABC678'", 'La identificación solo puede contener números.')
    def test_registro_identificacion_invalida(self):
        respuesta = self.crear_invalido()
        mensaje = 'La identificación solo puede contener números.'
        self.obtenido(f'Mensaje visible: {mensaje in respuesta.content.decode()}')
        self.assertContains(respuesta, mensaje)

    @caso('RF-001', 'Integración: un registro con datos inválidos no se guarda.',
          "first_name 'Ana2' e identificación '12ABC678'", 'No existe el usuario invalido-integracion')
    def test_validacion_formulario_usuario_no_guarda_datos_invalidos(self):
        self.crear_invalido()
        existe = Usuario.objects.filter(username='invalido-integracion').exists()
        self.obtenido(f'Usuario guardado: {existe}')
        self.assertFalse(existe)
