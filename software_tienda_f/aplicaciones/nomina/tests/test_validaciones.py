from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from datetime import date, time, timedelta
from decimal import Decimal
from django.test import TestCase, SimpleTestCase
from django.db import IntegrityError, transaction
from django.contrib.auth.models import Group
from aplicaciones.nomina.reportes import nombre_periodo
from django.urls import reverse
from django.utils import timezone
from aplicaciones.gestion_usuario.models import Usuario
from ..models import ConfiguracionBonificacion, HoraExtra, Nomina, Solicitud
from ..forms import BonificacionForm, ReporteFiltroForm, HoraExtraForm, SolicitudVacacionesForm, SolicitudCertificadoForm, HistorialFiltroForm
from aplicaciones.validaciones import validar_solo_letras, validar_usuario, validar_texto_seguro, validar_solo_digitos, validar_fecha_no_futura, normalizar_espacios
from django.core.exceptions import ValidationError


class ReporteFiltroFormTest(CasoPruebaMixin, TestCase):
    @caso('RF-004', 'Validar que se exija el período del reporte.', "período: ''", 'Selecciona un período para generar el reporte.')
    def test_periodo_vacio(self):
        form = ReporteFiltroForm(data={'periodo': ''})
        valido = form.is_valid()
        self.obtenido(f"Mensaje mostrado: {form.errors['periodo'][0]}")
        self.assertFalse(valido)
        self.assertEqual(form.errors['periodo'][0], 'Selecciona un período para generar el reporte.')

    @caso('RF-004', 'Validar que el período use el formato AAAA-MM.', "período: '2026/09'", 'El período debe tener el formato AAAA-MM (ej: 2026-09).')
    def test_periodo_formato_invalido(self):
        form = ReporteFiltroForm(data={'periodo': '2026/09'})
        valido = form.is_valid()
        self.obtenido(f"Mensaje mostrado: {form.errors['periodo'][0]}")
        self.assertFalse(valido)
        self.assertEqual(form.errors['periodo'][0], 'El período debe tener el formato AAAA-MM (ej: 2026-09).')

    @caso('RF-004', 'Validar que el mes del período esté entre 01 y 12.', "período: '2026-13'", 'El mes debe estar entre 01 y 12.')
    def test_periodo_mes_invalido(self):
        form = ReporteFiltroForm(data={'periodo': '2026-13'})
        valido = form.is_valid()
        self.obtenido(f"Mensaje mostrado: {form.errors['periodo'][0]}")
        self.assertFalse(valido)
        self.assertEqual(form.errors['periodo'][0], 'El mes debe estar entre 01 y 12.')

    @caso('RF-004', 'Validar que no existan reportes anteriores a enero de 2020.', "período: '2019-12'", 'No hay reportes anteriores a enero de 2020.')
    def test_periodo_anterior_a_2020(self):
        form = ReporteFiltroForm(data={'periodo': '2019-12'})
        valido = form.is_valid()
        self.obtenido(f"Mensaje mostrado: {form.errors['periodo'][0]}")
        self.assertFalse(valido)
        self.assertEqual(form.errors['periodo'][0], 'No hay reportes anteriores a enero de 2020.')

    @caso('RF-004', 'Validar que se acepte un período válido.', "período: '2026-09'", "período limpio: '2026-09'")
    def test_periodo_valido(self):
        pasado = ReporteFiltroForm(data={'periodo': '2026-09'})
        self.assertTrue(pasado.is_valid(), pasado.errors)
        self.obtenido(f"Período validado: {pasado.cleaned_data['periodo']}")
        self.assertEqual(pasado.cleaned_data['periodo'], '2026-09')

    @caso('RF-004', 'Validar que se rechace un período futuro.', 'período: mes calendario siguiente a hoy', 'No se puede generar el reporte de un mes futuro.')
    def test_periodo_futuro(self):
        hoy = date.today()
        if hoy.month == 12:
            ano_futuro, mes_futuro = hoy.year + 1, 1
        else:
            ano_futuro, mes_futuro = hoy.year, hoy.month + 1
        periodo_futuro = '{0:04d}-{1:02d}'.format(ano_futuro, mes_futuro)
        form_futuro = ReporteFiltroForm(data={'periodo': periodo_futuro})
        valido = form_futuro.is_valid()
        self.obtenido(f"Mensaje mostrado: {form_futuro.errors['periodo'][0]}")
        self.assertFalse(valido)
        self.assertEqual(
            form_futuro.errors['periodo'][0],
            'No se puede generar el reporte de un mes futuro.',
        )


class ValidacionesServidorNominaTest(CasoPruebaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gerente_group, _ = Group.objects.get_or_create(name='Gerente')
        cls.auxiliar_group, _ = Group.objects.get_or_create(name='Auxiliar Administrativo')
        cls.vendedor_group, _ = Group.objects.get_or_create(name='Vendedor')
        cls.gerente = Usuario.objects.create_user(
            username='val-gerente', email='val-gerente@example.com', password='clave')
        cls.auxiliar = Usuario.objects.create_user(
            username='val-auxiliar', email='val-auxiliar@example.com', password='clave')
        cls.empleado = Usuario.objects.create_user(
            username='val-empleado', email='val-empleado@example.com', password='clave',
            first_name='Ana', last_name='Prueba', identificacion=91606161,
            salario_base=Decimal('1000000'))
        cls.gerente.groups.add(cls.gerente_group)
        cls.auxiliar.groups.add(cls.auxiliar_group)
        cls.empleado.groups.add(cls.vendedor_group)

    def hora_form(self, **overrides):
        hoy = timezone.localdate()
        datos = {
            'usuario': self.empleado.pk, 'fecha': hoy.isoformat(),
            'hora_ingreso': '08:00', 'hora_salida': '18:00', 'motivo': 'Trabajo extra',
        }
        datos.update(overrides)
        return HoraExtraForm(data=datos)

    def errores(self, form, campo):
        form.is_valid()
        if campo == '__all__':
            return list(form.non_field_errors())
        return list(form.errors.get(campo, []))

    @caso('RF-002', 'Validar que no se registren horas extra con fecha futura.', 'fecha: mañana; ingreso 08:00; salida 18:00',
          'La fecha de las horas extra no puede ser posterior a hoy.')
    def test_horas_extra_fecha_futura(self):
        fecha = timezone.localdate() + timedelta(days=1)
        errores = self.errores(self.hora_form(fecha=fecha.isoformat()), 'fecha')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'La fecha de las horas extra no puede ser posterior a hoy.')

    @caso('RF-002', 'Validar que no se registren horas extra de hace más de 60 días.', 'fecha: hoy menos 61 días',
          'Solo se pueden registrar horas extra de los últimos 60 días.')
    def test_horas_extra_fecha_mayor_a_60_dias(self):
        fecha = timezone.localdate() - timedelta(days=61)
        errores = self.errores(self.hora_form(fecha=fecha.isoformat()), 'fecha')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'Solo se pueden registrar horas extra de los últimos 60 días.')

    @caso('RF-002', 'Validar que la hora de salida sea posterior a la de ingreso.', 'ingreso: 08:00; salida: 08:00',
          'La hora de salida debe ser posterior a la hora de ingreso.')
    def test_horas_extra_salida_no_posterior(self):
        errores = self.errores(self.hora_form(hora_salida='08:00'), 'hora_salida')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'La hora de salida debe ser posterior a la hora de ingreso.')

    @caso('RF-002', 'Validar la longitud mínima del motivo de horas extra.', "motivo: 'abc'",
          'El motivo debe tener entre 5 y 200 caracteres.')
    def test_horas_extra_motivo_corto(self):
        errores = self.errores(self.hora_form(motivo='abc'), 'motivo')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'El motivo debe tener entre 5 y 200 caracteres.')

    @caso('RF-002', 'Validar que el motivo de horas extra rechace caracteres especiales.', "motivo: 'malo <x>'",
          'El motivo contiene caracteres no permitidos.')
    def test_horas_extra_motivo_caracter_no_permitido(self):
        errores = self.errores(self.hora_form(motivo='malo <x>'), 'motivo')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'El motivo contiene caracteres no permitidos.')

    @caso('RF-002', 'Validar que no se dupliquen horas extra del mismo empleado y día.',
          'Empleado Ana Prueba con horas extra ya registradas hoy; nuevo registro para hoy',
          'Ya hay horas extra registradas para Ana Prueba el <fecha de hoy>.')
    def test_horas_extra_duplicadas_mismo_dia(self):
        fecha = timezone.localdate()
        HoraExtra.objects.create(usuario=self.empleado, fecha=fecha,
            hora_ingreso=time(8), hora_salida=time(18), tipo=HoraExtra.Tipo.DIURNA,
            cantidad_horas=Decimal('1.60'), valor=0, motivo='Trabajo extra',
            periodo=fecha.strftime('%Y-%m'))
        errores = self.errores(self.hora_form(), '__all__')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0],
            'Ya hay horas extra registradas para Ana Prueba el {0}.'.format(fecha.strftime('%d/%m/%Y')))

    @caso('RF-002', 'Validar que no se registren horas extra de un mes con nómina ya calculada.',
          'Nómina del mes actual ya calculada; nuevo registro de horas extra hoy',
          'La nómina de <mes> ya fue calculada; no se pueden registrar más horas extra de ese mes.')
    def test_horas_extra_bloqueadas_por_nomina_calculada(self):
        fecha = timezone.localdate()
        Nomina.objects.create(usuario=self.empleado, periodo=fecha.strftime('%Y-%m'),
            salario_bruto=1000000, deducciones=0, total_pagar=1000000)
        errores = self.errores(self.hora_form(), '__all__')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0],
            'La nómina de {0} ya fue calculada; no se pueden registrar más horas extra de ese mes.'.format(
                nombre_periodo(fecha.strftime('%Y-%m'))))

    def post_horas_duplicadas(self):
        hoy = timezone.localdate()
        HoraExtra.objects.create(usuario=self.empleado, fecha=hoy,
            hora_ingreso=time(8), hora_salida=time(18), tipo=HoraExtra.Tipo.DIURNA,
            cantidad_horas=Decimal('1.60'), valor=0, motivo='Trabajo extra',
            periodo=hoy.strftime('%Y-%m'))
        self.client.force_login(self.gerente)
        return hoy, self.client.post(reverse('horas_extra'), {
            'usuario': self.empleado.pk, 'fecha': hoy.isoformat(),
            'hora_ingreso': '08:00', 'hora_salida': '18:00',
            'motivo': 'Inventario de bodega',
        })

    @caso('RF-002', 'Validar que la vista no guarde un registro duplicado de horas extra.',
          'POST horas extra para Ana Prueba hoy, ya existe un registro ese día',
          'Se mantiene 1 registro de horas extra')
    def test_vista_horas_extra_no_duplica(self):
        self.post_horas_duplicadas()
        cantidad = HoraExtra.objects.filter(usuario=self.empleado).count()
        self.obtenido(f'Registros de horas extra: {cantidad}')
        self.assertEqual(cantidad, 1)

    @caso('RF-002', 'Validar que la vista muestre el error de duplicado de horas extra.',
          'POST horas extra para Ana Prueba hoy, ya existe un registro ese día',
          'HTTP 200 con el mensaje: Ya hay horas extra registradas para Ana Prueba el <fecha>.')
    def test_vista_horas_extra_muestra_error_duplicado(self):
        hoy, response = self.post_horas_duplicadas()
        mensaje = 'Ya hay horas extra registradas para Ana Prueba el {0}.'.format(hoy.strftime('%d/%m/%Y'))
        self.obtenido(f'HTTP {response.status_code}; mensaje presente: {mensaje in response.content.decode()}')
        self.assertContains(response, mensaje)

    @caso('RF-002', 'Validar que la vista conserve los datos digitados cuando hay error.',
          "POST duplicado con motivo: 'Inventario de bodega'",
          "El formulario vuelve a mostrar 'Inventario de bodega'")
    def test_vista_horas_extra_conserva_datos(self):
        _, response = self.post_horas_duplicadas()
        presente = 'Inventario de bodega' in response.content.decode()
        self.obtenido(f'Motivo conservado en el formulario: {presente}')
        self.assertContains(response, 'Inventario de bodega')

    @caso('RF-002', 'Validar que la vista bloquee horas extra cuando la nómina del mes ya existe.',
          'Nómina PENDIENTE del mes actual; POST horas extra hoy',
          'No se crea ningún registro de horas extra (0)')
    def test_vista_horas_extra_bloqueada_por_nomina(self):
        hoy = timezone.localdate()
        Nomina.objects.create(usuario=self.empleado, periodo=hoy.strftime('%Y-%m'),
            salario_bruto=1000000, deducciones=0, total_pagar=1000000,
            estado=Nomina.Estado.PENDIENTE)
        self.client.force_login(self.gerente)
        self.client.post(reverse('horas_extra'), {
            'usuario': self.empleado.pk, 'fecha': hoy.isoformat(),
            'hora_ingreso': '08:00', 'hora_salida': '18:00',
            'motivo': 'Inventario de bodega',
        })
        cantidad = HoraExtra.objects.filter(usuario=self.empleado).count()
        self.obtenido(f'Registros de horas extra: {cantidad}')
        self.assertEqual(cantidad, 0)

    @caso('RF-002', 'Validar que un registro válido de horas extra se guarde.',
          'POST ayer, ingreso 07:00, salida 19:00, motivo Inventario de bodega',
          'Se guarda 1 registro de horas extra')
    def test_vista_horas_extra_valida_guarda(self):
        ayer = timezone.localdate() - timedelta(days=1)
        self.client.force_login(self.gerente)
        self.client.post(reverse('horas_extra'), {
            'usuario': self.empleado.pk, 'fecha': ayer.isoformat(),
            'hora_ingreso': '07:00', 'hora_salida': '19:00',
            'motivo': 'Inventario de bodega',
        })
        cantidad = HoraExtra.objects.filter(usuario=self.empleado).count()
        self.obtenido(f'Registros de horas extra: {cantidad}')
        self.assertEqual(cantidad, 1)

    @caso('RF-002', 'Validar que tras guardar horas extra se regrese a la ventana Novedades.',
          'POST válido de horas extra',
          'HTTP 302 a /nomina/novedades/?seccion=horas-extra#horas-extra')
    def test_vista_horas_extra_valida_redirige(self):
        ayer = timezone.localdate() - timedelta(days=1)
        self.client.force_login(self.gerente)
        response = self.client.post(reverse('horas_extra'), {
            'usuario': self.empleado.pk, 'fecha': ayer.isoformat(),
            'hora_ingreso': '07:00', 'hora_salida': '19:00',
            'motivo': 'Inventario de bodega',
        })
        self.obtenido(f"HTTP {response.status_code}; redirección a {response.get('Location')}")
        self.assertEqual(response['Location'],
            reverse('novedades') + '?seccion=horas-extra#horas-extra')

    def errores_bonificacion(self, porcentaje='10', meta='100'):
        return self.errores(BonificacionForm(data={
            'usuario': self.empleado.pk, 'porcentaje': porcentaje, 'meta_mensual': meta}),
            'meta_mensual' if porcentaje == '10' else 'porcentaje')

    @caso('RF-005', 'Validar que el porcentaje de bonificación sea mayor que cero.', "porcentaje: '0'; meta: 100",
          'El porcentaje debe ser mayor que 0 y máximo 100.')
    def test_bonificacion_porcentaje_cero(self):
        errores = self.errores_bonificacion(porcentaje='0')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'El porcentaje debe ser mayor que 0 y máximo 100.')

    @caso('RF-005', 'Validar que el porcentaje de bonificación no supere 100.', "porcentaje: '100.5'; meta: 100",
          'El porcentaje debe ser mayor que 0 y máximo 100.')
    def test_bonificacion_porcentaje_superior_a_100(self):
        errores = self.errores_bonificacion(porcentaje='100.5')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'El porcentaje debe ser mayor que 0 y máximo 100.')

    @caso('RF-005', 'Validar que el porcentaje admita máximo dos decimales.', "porcentaje: '10,555'; meta: 100",
          'El porcentaje admite máximo 2 decimales.')
    def test_bonificacion_porcentaje_tres_decimales(self):
        errores = self.errores_bonificacion(porcentaje='10,555')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'El porcentaje admite máximo 2 decimales.')

    @caso('RF-005', 'Validar que la meta mensual sea mayor que cero.', "porcentaje: 10; meta: '0'",
          'La meta mensual debe ser mayor que cero.')
    def test_bonificacion_meta_cero(self):
        errores = self.errores_bonificacion(meta='0')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'La meta mensual debe ser mayor que cero.')

    @caso('RF-005', 'Validar el valor máximo de la meta mensual.', "porcentaje: 10; meta: '1000000000'",
          'La meta mensual no puede superar $999.999.999.')
    def test_bonificacion_meta_excesiva(self):
        errores = self.errores_bonificacion(meta='1000000000')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'La meta mensual no puede superar $999.999.999.')

    @caso('RF-005', 'Validar que se acepte un porcentaje con coma decimal.', "porcentaje: '12,5'; meta: 100",
          'Formulario válido')
    def test_bonificacion_porcentaje_con_coma_valido(self):
        form = BonificacionForm(data={'usuario': self.empleado.pk, 'porcentaje': '12,5', 'meta_mensual': '100'})
        valido = form.is_valid()
        self.obtenido(f'Formulario válido: {valido}' + ('' if valido else f'; errores: {dict(form.errors)}'))
        self.assertTrue(valido)

    def datos_vacaciones(self, desde=None, hasta=None, motivo='Descanso familiar'):
        hoy = timezone.localdate()
        return {'fecha_desde': (desde or hoy).isoformat(), 'fecha_hasta': (hasta or hoy).isoformat(), 'motivo': motivo}

    def errores_vacaciones(self, campo, **fechas):
        return self.errores(SolicitudVacacionesForm(data=self.datos_vacaciones(**fechas), usuario=self.empleado), campo)

    @caso('RF-007', 'Validar que las vacaciones no inicien en una fecha pasada.', 'desde: ayer; hasta: hoy',
          'La fecha de inicio no puede ser anterior a hoy.')
    def test_vacaciones_inicio_ayer(self):
        errores = self.errores_vacaciones('fecha_desde', desde=timezone.localdate() - timedelta(days=1))
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'La fecha de inicio no puede ser anterior a hoy.')

    @caso('RF-007', 'Validar que la fecha de fin no sea anterior a la de inicio.', 'desde: hoy+2; hasta: hoy+1',
          'La fecha de fin no puede ser anterior a la fecha de inicio.')
    def test_vacaciones_fin_antes_del_inicio(self):
        hoy = timezone.localdate()
        errores = self.errores_vacaciones('fecha_hasta', desde=hoy + timedelta(days=2), hasta=hoy + timedelta(days=1))
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'La fecha de fin no puede ser anterior a la fecha de inicio.')

    @caso('RF-007', 'Validar el máximo de 30 días calendario de vacaciones.', 'desde: hoy; hasta: hoy+30 (31 días)',
          'Las vacaciones no pueden superar 30 días calendario.')
    def test_vacaciones_31_dias(self):
        hoy = timezone.localdate()
        errores = self.errores_vacaciones('fecha_hasta', desde=hoy, hasta=hoy + timedelta(days=30))
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'Las vacaciones no pueden superar 30 días calendario.')

    def errores_traslape(self, estado):
        hoy = timezone.localdate()
        Solicitud.objects.create(usuario=self.empleado, tipo=Solicitud.Tipo.VACACIONES,
            fecha_desde=hoy + timedelta(days=2), fecha_hasta=hoy + timedelta(days=4),
            estado=estado, motivo='Descanso')
        return self.errores_vacaciones('__all__', desde=hoy + timedelta(days=3), hasta=hoy + timedelta(days=5))

    @caso('RF-007', 'Validar que no se crucen vacaciones con otras ya aprobadas.',
          'Vacaciones ACEPTADAS hoy+2..hoy+4; nueva solicitud hoy+3..hoy+5',
          'Ya tienes vacaciones solicitadas o aprobadas que se cruzan con esas fechas.')
    def test_vacaciones_traslape_aceptada(self):
        errores = self.errores_traslape(Solicitud.Estado.ACEPTADA)
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'Ya tienes vacaciones solicitadas o aprobadas que se cruzan con esas fechas.')

    @caso('RF-007', 'Validar que no se crucen vacaciones con otras pendientes.',
          'Vacaciones PENDIENTES hoy+2..hoy+4; nueva solicitud hoy+3..hoy+5',
          'Ya tienes vacaciones solicitadas o aprobadas que se cruzan con esas fechas.')
    def test_vacaciones_traslape_pendiente(self):
        errores = self.errores_traslape(Solicitud.Estado.PENDIENTE)
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'Ya tienes vacaciones solicitadas o aprobadas que se cruzan con esas fechas.')

    @caso('RF-007', 'Validar que una solicitud de vacaciones válida quede registrada.',
          'POST vacaciones desde hoy+2 hasta hoy+5, motivo Descanso familiar',
          'Se crea la solicitud de vacaciones del empleado')
    def test_vacaciones_rango_valido_por_post(self):
        self.client.force_login(self.empleado)
        hoy = timezone.localdate()
        self.client.post(reverse('vacaciones'), self.datos_vacaciones(
            desde=hoy + timedelta(days=2), hasta=hoy + timedelta(days=5)), follow=True)
        existe = Solicitud.objects.filter(usuario=self.empleado, tipo=Solicitud.Tipo.VACACIONES).exists()
        self.obtenido(f'Solicitud de vacaciones creada: {existe}')
        self.assertTrue(existe)

    @caso('RF-003', 'Validar la longitud mínima del motivo del certificado.', "motivo: 'abc'",
          'El motivo debe tener entre 5 y 200 caracteres.')
    def test_certificado_motivo_corto(self):
        errores = self.errores(SolicitudCertificadoForm(data={'motivo': 'abc'}), 'motivo')
        self.obtenido(f'Mensaje mostrado: {errores[0]}' if errores else 'Formulario aceptado sin error')
        self.assertEqual(errores[0], 'El motivo debe tener entre 5 y 200 caracteres.')

    @caso('RF-003', 'Validar que la solicitud de certificado quede registrada.',
          "POST consultar nómina con motivo 'Trámite laboral'",
          'Se crea una solicitud de tipo CERTIFICADO')
    def test_post_certificado_crea_solicitud(self):
        self.client.force_login(self.empleado)
        self.client.post(reverse('nomina_consultar'), {'tipo': 'NOMINA', 'motivo': 'Trámite laboral'})
        existe = Solicitud.objects.filter(usuario=self.empleado, tipo=Solicitud.Tipo.CERTIFICADO).exists()
        self.obtenido(f'Solicitud de certificado creada: {existe}')
        self.assertTrue(existe)

    @caso('RF-003', 'Validar que el empleado no pueda forzar una solicitud de tipo NOMINA.',
          "POST consultar nómina con tipo manipulado 'NOMINA'",
          'No se crea ninguna solicitud de tipo NOMINA')
    def test_post_tipo_nomina_no_crea_solicitud_nomina(self):
        self.client.force_login(self.empleado)
        self.client.post(reverse('nomina_consultar'), {'tipo': 'NOMINA', 'motivo': 'Trámite laboral'})
        existe = Solicitud.objects.filter(usuario=self.empleado, tipo=Solicitud.Tipo.NOMINA).exists()
        self.obtenido(f'Solicitud de tipo NOMINA creada: {existe}')
        self.assertFalse(existe)

    @caso('RF-007', 'Validar que el motivo de rechazo rechace etiquetas HTML.',
          "Rechazo de certificado con motivo '<b>malo</b>'",
          'El motivo del rechazo contiene caracteres no permitidos.')
    def test_bandeja_rechazo_con_texto_no_permitido_muestra_error(self):
        solicitud = Solicitud.objects.create(usuario=self.empleado, tipo=Solicitud.Tipo.CERTIFICADO,
            motivo='Certificado', estado=Solicitud.Estado.PENDIENTE)
        self.client.force_login(self.auxiliar)
        response = self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': solicitud.pk, 'accion': 'rechazar', 'motivo_rechazo': '<b>malo</b>'}, follow=True)
        mensaje = 'El motivo del rechazo contiene caracteres no permitidos.'
        self.obtenido(f'Mensaje presente: {mensaje in response.content.decode()}')
        self.assertContains(response, mensaje)

    @caso('RF-007', 'Validar que un rechazo con motivo inválido no cambie el estado de la solicitud.',
          "Rechazo de certificado con motivo '<b>malo</b>'",
          'La solicitud sigue en estado PENDIENTE')
    def test_bandeja_rechazo_con_texto_no_permitido_no_cambia_estado(self):
        solicitud = Solicitud.objects.create(usuario=self.empleado, tipo=Solicitud.Tipo.CERTIFICADO,
            motivo='Certificado', estado=Solicitud.Estado.PENDIENTE)
        self.client.force_login(self.auxiliar)
        self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': solicitud.pk, 'accion': 'rechazar', 'motivo_rechazo': '<b>malo</b>'}, follow=True)
        solicitud.refresh_from_db()
        self.obtenido(f'Estado de la solicitud: {solicitud.estado}')
        self.assertEqual(solicitud.estado, Solicitud.Estado.PENDIENTE)

    @caso('RF-007', 'Validar que la bandeja rechace un identificador de solicitud no numérico.',
          "solicitud_id: 'abc'; acción: rechazar", 'La solicitud indicada no es válida.')
    def test_bandeja_rechaza_id_no_numerico(self):
        self.client.force_login(self.auxiliar)
        response = self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': 'abc', 'accion': 'rechazar'}, follow=True)
        mensaje = 'La solicitud indicada no es válida.'
        self.obtenido(f'Mensaje presente: {mensaje in response.content.decode()}')
        self.assertContains(response, mensaje)

    @caso('RF-004', 'Validar que el filtro del historial no acepte "desde" posterior a "hasta".',
          'desde: 2026-10-10; hasta: 2026-10-01',
          'La fecha "desde" no puede ser posterior a la fecha "hasta".')
    def test_historial_fecha_desde_posterior(self):
        self.client.force_login(self.empleado)
        response = self.client.get(reverse('nomina_historial'), {'desde': '2026-10-10', 'hasta': '2026-10-01'})
        mensajes = [str(m) for m in response.context['messages']]
        self.obtenido('Mensaje mostrado: ' + ('; '.join(mensajes) or 'ninguno'))
        self.assertIn('La fecha "desde" no puede ser posterior a la fecha "hasta".', mensajes)

    @caso('RF-005', 'Validar que la base de datos rechace un porcentaje de bonificación de 150.',
          'Inserción directa: porcentaje 150, meta 100', 'IntegrityError (restricción CHECK)')
    def test_constraint_bonificacion_porcentaje_150(self):
        try:
            with transaction.atomic():
                ConfiguracionBonificacion.objects.create(
                    usuario=self.empleado, porcentaje=150, meta_mensual=100)
            obtenido = 'Registro guardado sin error'
        except IntegrityError:
            obtenido = 'IntegrityError (restricción CHECK)'
        self.obtenido(obtenido)
        self.assertEqual(obtenido, 'IntegrityError (restricción CHECK)')

    @caso('RF-002', 'Validar que la base de datos rechace horas extra con salida antes del ingreso.',
          'Inserción directa: ingreso 18:00, salida 08:00', 'IntegrityError (restricción CHECK)')
    def test_constraint_hora_salida_antes_de_ingreso(self):
        hoy = timezone.localdate()
        try:
            with transaction.atomic():
                HoraExtra.objects.create(usuario=self.empleado, fecha=hoy,
                    hora_ingreso=time(18), hora_salida=time(8), tipo=HoraExtra.Tipo.DIURNA,
                    cantidad_horas=1, valor=0, motivo='Trabajo extra', periodo=hoy.strftime('%Y-%m'))
            obtenido = 'Registro guardado sin error'
        except IntegrityError:
            obtenido = 'IntegrityError (restricción CHECK)'
        self.obtenido(obtenido)
        self.assertEqual(obtenido, 'IntegrityError (restricción CHECK)')


class ValidadoresCompartidosTest(CasoPruebaMixin, SimpleTestCase):
    def resultado(self, validador, valor):
        try:
            validador(valor)
            return 'Aceptado'
        except ValidationError as error:
            return f'Rechazado: {error.messages[0]}'

    @caso('RF-001', 'Validar que los nombres acepten tildes y eñe.', "valor: 'María Núñez'", 'Aceptado')
    def test_solo_letras_acepta_tildes_y_ene(self):
        obtenido = self.resultado(validar_solo_letras, 'María Núñez')
        self.obtenido(obtenido)
        self.assertEqual(obtenido, 'Aceptado')

    @caso('RF-001', 'Validar que los nombres rechacen dígitos.', "valor: 'María 2'", 'Rechazado con mensaje de error')
    def test_solo_letras_rechaza_digitos(self):
        obtenido = self.resultado(validar_solo_letras, 'María 2')
        self.obtenido(obtenido)
        self.assertTrue(obtenido.startswith('Rechazado'))

    @caso('RF-009', 'Validar que el nombre de usuario acepte letras, números, punto, guion y guion bajo.',
          "valor: 'ana.perez-2_x'", 'Aceptado')
    def test_usuario_acepta_formato(self):
        obtenido = self.resultado(validar_usuario, 'ana.perez-2_x')
        self.obtenido(obtenido)
        self.assertEqual(obtenido, 'Aceptado')

    @caso('RF-009', 'Validar que el nombre de usuario rechace espacios.', "valor: 'ana perez'", 'Rechazado con mensaje de error')
    def test_usuario_rechaza_espacios(self):
        obtenido = self.resultado(validar_usuario, 'ana perez')
        self.obtenido(obtenido)
        self.assertTrue(obtenido.startswith('Rechazado'))

    @caso('RF-009', 'Validar que el nombre de usuario rechace tildes y eñe.', "valor: 'niño'", 'Rechazado con mensaje de error')
    def test_usuario_rechaza_tildes(self):
        obtenido = self.resultado(validar_usuario, 'niño')
        self.obtenido(obtenido)
        self.assertTrue(obtenido.startswith('Rechazado'))

    @caso('RF-007', 'Validar que los textos libres acepten signos de puntuación permitidos.',
          "valor: '¿Pago: 100? Sí, #1 (bodega).'", 'Aceptado')
    def test_texto_seguro_acepta_signos_permitidos(self):
        obtenido = self.resultado(validar_texto_seguro, '¿Pago: 100? Sí, #1 (bodega).')
        self.obtenido(obtenido)
        self.assertEqual(obtenido, 'Aceptado')

    @caso('RF-007', 'Validar que los textos libres rechacen el signo $.', "valor: 'Valor $100'", 'Rechazado con mensaje de error')
    def test_texto_seguro_rechaza_signo_pesos(self):
        obtenido = self.resultado(validar_texto_seguro, 'Valor $100')
        self.obtenido(obtenido)
        self.assertTrue(obtenido.startswith('Rechazado'))

    @caso('RF-007', 'Validar que los textos libres rechacen etiquetas HTML.', "valor: 'Texto <script>'", 'Rechazado con mensaje de error')
    def test_texto_seguro_rechaza_html(self):
        obtenido = self.resultado(validar_texto_seguro, 'Texto <script>')
        self.obtenido(obtenido)
        self.assertTrue(obtenido.startswith('Rechazado'))

    @caso('RF-001', 'Validar que los campos numéricos acepten solo dígitos.', "valor: '012345'", 'Aceptado')
    def test_digitos_acepta_numeros(self):
        obtenido = self.resultado(validar_solo_digitos, '012345')
        self.obtenido(obtenido)
        self.assertEqual(obtenido, 'Aceptado')

    @caso('RF-001', 'Validar que los campos numéricos rechacen letras.', "valor: '12a'", 'Rechazado con mensaje de error')
    def test_digitos_rechaza_letras(self):
        obtenido = self.resultado(validar_solo_digitos, '12a')
        self.obtenido(obtenido)
        self.assertTrue(obtenido.startswith('Rechazado'))

    @caso('RF-001', 'Validar que una fecha igual a hoy sea aceptada.', 'fecha: hoy', 'Aceptado')
    def test_fecha_hoy_aceptada(self):
        obtenido = self.resultado(validar_fecha_no_futura, date.today())
        self.obtenido(obtenido)
        self.assertEqual(obtenido, 'Aceptado')

    @caso('RF-001', 'Validar que una fecha futura sea rechazada.', 'fecha: mañana', 'Rechazado con mensaje de error')
    def test_fecha_futura_rechazada(self):
        obtenido = self.resultado(validar_fecha_no_futura, date.today() + timedelta(days=1))
        self.obtenido(obtenido)
        self.assertTrue(obtenido.startswith('Rechazado'))

    @caso('RF-001', 'Validar que se eliminen los espacios repetidos de los textos.', "valor: '  Ana   María  '", "'Ana María'")
    def test_normaliza_espacios_dobles(self):
        normalizado = normalizar_espacios('  Ana   María  ')
        self.obtenido(repr(normalizado))
        self.assertEqual(normalizado, 'Ana María')
