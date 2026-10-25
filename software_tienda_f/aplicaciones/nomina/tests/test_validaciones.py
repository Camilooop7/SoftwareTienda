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


class ValidacionesServidorNominaTest(TestCase):
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

    def test_horas_extra_fecha_futura(self):
        fecha = timezone.localdate() + timedelta(days=1)
        form = self.hora_form(fecha=fecha.isoformat())
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['fecha'][0], 'La fecha de las horas extra no puede ser posterior a hoy.')

    def test_horas_extra_fecha_mayor_a_60_dias(self):
        fecha = timezone.localdate() - timedelta(days=61)
        form = self.hora_form(fecha=fecha.isoformat())
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['fecha'][0], 'Solo se pueden registrar horas extra de los últimos 60 días.')

    def test_horas_extra_salida_no_posterior(self):
        form = self.hora_form(hora_salida='08:00')
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['hora_salida'][0], 'La hora de salida debe ser posterior a la hora de ingreso.')

    def test_horas_extra_motivo_corto(self):
        form = self.hora_form(motivo='abc')
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['motivo'][0], 'El motivo debe tener entre 5 y 200 caracteres.')

    def test_horas_extra_motivo_caracter_no_permitido(self):
        form = self.hora_form(motivo='malo <x>')
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['motivo'][0], 'El motivo contiene caracteres no permitidos.')

    def test_horas_extra_duplicadas_mismo_dia(self):
        fecha = timezone.localdate()
        HoraExtra.objects.create(usuario=self.empleado, fecha=fecha,
            hora_ingreso=time(8), hora_salida=time(18), tipo=HoraExtra.Tipo.DIURNA,
            cantidad_horas=Decimal('1.60'), valor=0, motivo='Trabajo extra',
            periodo=fecha.strftime('%Y-%m'))
        form = self.hora_form()
        self.assertFalse(form.is_valid())
        self.assertEqual(form.non_field_errors()[0],
            'Ya hay horas extra registradas para Ana Prueba el {0}.'.format(fecha.strftime('%d/%m/%Y')))

    def test_horas_extra_bloqueadas_por_nomina_calculada(self):
        fecha = timezone.localdate()
        Nomina.objects.create(usuario=self.empleado, periodo=fecha.strftime('%Y-%m'),
            salario_bruto=1000000, deducciones=0, total_pagar=1000000)
        form = self.hora_form()
        self.assertFalse(form.is_valid())
        self.assertEqual(form.non_field_errors()[0],
            'La nómina de {0} ya fue calculada; no se pueden registrar más horas extra de ese mes.'.format(
                nombre_periodo(fecha.strftime('%Y-%m'))))

    def test_vista_horas_extra_no_duplica_y_muestra_error(self):
        hoy = timezone.localdate()
        HoraExtra.objects.create(usuario=self.empleado, fecha=hoy,
            hora_ingreso=time(8), hora_salida=time(18), tipo=HoraExtra.Tipo.DIURNA,
            cantidad_horas=Decimal('1.60'), valor=0, motivo='Trabajo extra',
            periodo=hoy.strftime('%Y-%m'))
        self.client.force_login(self.gerente)
        response = self.client.post(reverse('horas_extra'), {
            'usuario': self.empleado.pk, 'fecha': hoy.isoformat(),
            'hora_ingreso': '08:00', 'hora_salida': '18:00',
            'motivo': 'Inventario de bodega',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(HoraExtra.objects.filter(usuario=self.empleado).count(), 1)
        self.assertContains(response,
            'Ya hay horas extra registradas para Ana Prueba el {0}.'.format(hoy.strftime('%d/%m/%Y')))
        self.assertContains(response, 'Inventario de bodega')

    def test_vista_horas_extra_bloqueada_por_nomina(self):
        hoy = timezone.localdate()
        Nomina.objects.create(usuario=self.empleado, periodo=hoy.strftime('%Y-%m'),
            salario_bruto=1000000, deducciones=0, total_pagar=1000000,
            estado=Nomina.Estado.PENDIENTE)
        self.client.force_login(self.gerente)
        response = self.client.post(reverse('horas_extra'), {
            'usuario': self.empleado.pk, 'fecha': hoy.isoformat(),
            'hora_ingreso': '08:00', 'hora_salida': '18:00',
            'motivo': 'Inventario de bodega',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(HoraExtra.objects.filter(usuario=self.empleado).count(), 0)
        self.assertContains(response,
            'La nómina de {0} ya fue calculada; no se pueden registrar más horas extra de ese mes.'.format(
                nombre_periodo(hoy.strftime('%Y-%m'))))

    def test_vista_horas_extra_valida_redirige(self):
        ayer = timezone.localdate() - timedelta(days=1)
        self.client.force_login(self.gerente)
        response = self.client.post(reverse('horas_extra'), {
            'usuario': self.empleado.pk, 'fecha': ayer.isoformat(),
            'hora_ingreso': '07:00', 'hora_salida': '19:00',
            'motivo': 'Inventario de bodega',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'],
            reverse('novedades') + '?seccion=horas-extra#horas-extra')
        self.assertEqual(HoraExtra.objects.filter(usuario=self.empleado).count(), 1)

    def test_bonificacion_porcentaje_cero(self):
        form = BonificacionForm(data={'usuario': self.empleado.pk, 'porcentaje': '0', 'meta_mensual': '100'})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['porcentaje'][0], 'El porcentaje debe ser mayor que 0 y máximo 100.')

    def test_bonificacion_porcentaje_superior_a_100(self):
        form = BonificacionForm(data={'usuario': self.empleado.pk, 'porcentaje': '100.5', 'meta_mensual': '100'})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['porcentaje'][0], 'El porcentaje debe ser mayor que 0 y máximo 100.')

    def test_bonificacion_porcentaje_tres_decimales(self):
        form = BonificacionForm(data={'usuario': self.empleado.pk, 'porcentaje': '10,555', 'meta_mensual': '100'})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['porcentaje'][0], 'El porcentaje admite máximo 2 decimales.')

    def test_bonificacion_meta_cero(self):
        form = BonificacionForm(data={'usuario': self.empleado.pk, 'porcentaje': '10', 'meta_mensual': '0'})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['meta_mensual'][0], 'La meta mensual debe ser mayor que cero.')

    def test_bonificacion_meta_excesiva(self):
        form = BonificacionForm(data={'usuario': self.empleado.pk, 'porcentaje': '10', 'meta_mensual': '1000000000'})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['meta_mensual'][0], 'La meta mensual no puede superar $999.999.999.')

    def test_bonificacion_porcentaje_con_coma_valido(self):
        form = BonificacionForm(data={'usuario': self.empleado.pk, 'porcentaje': '12,5', 'meta_mensual': '100'})
        self.assertTrue(form.is_valid(), form.errors)

    def datos_vacaciones(self, desde=None, hasta=None, motivo='Descanso familiar'):
        hoy = timezone.localdate()
        return {'fecha_desde': (desde or hoy).isoformat(), 'fecha_hasta': (hasta or hoy).isoformat(), 'motivo': motivo}

    def test_vacaciones_inicio_ayer(self):
        ayer = timezone.localdate() - timedelta(days=1)
        form = SolicitudVacacionesForm(data=self.datos_vacaciones(desde=ayer), usuario=self.empleado)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['fecha_desde'][0], 'La fecha de inicio no puede ser anterior a hoy.')

    def test_vacaciones_fin_antes_del_inicio(self):
        hoy = timezone.localdate()
        form = SolicitudVacacionesForm(data=self.datos_vacaciones(desde=hoy + timedelta(days=2), hasta=hoy + timedelta(days=1)), usuario=self.empleado)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['fecha_hasta'][0], 'La fecha de fin no puede ser anterior a la fecha de inicio.')

    def test_vacaciones_31_dias(self):
        hoy = timezone.localdate()
        form = SolicitudVacacionesForm(data=self.datos_vacaciones(desde=hoy, hasta=hoy + timedelta(days=30)), usuario=self.empleado)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['fecha_hasta'][0], 'Las vacaciones no pueden superar 30 días calendario.')

    def test_vacaciones_traslape_aceptada_y_pendiente(self):
        hoy = timezone.localdate()
        for estado in (Solicitud.Estado.ACEPTADA, Solicitud.Estado.PENDIENTE):
            with self.subTest(estado=estado):
                Solicitud.objects.create(usuario=self.empleado, tipo=Solicitud.Tipo.VACACIONES,
                    fecha_desde=hoy + timedelta(days=2), fecha_hasta=hoy + timedelta(days=4),
                    estado=estado, motivo='Descanso')
                form = SolicitudVacacionesForm(data=self.datos_vacaciones(
                    desde=hoy + timedelta(days=3), hasta=hoy + timedelta(days=5)), usuario=self.empleado)
                self.assertFalse(form.is_valid())
                self.assertEqual(form.non_field_errors()[0],
                    'Ya tienes vacaciones solicitadas o aprobadas que se cruzan con esas fechas.')
                Solicitud.objects.filter(usuario=self.empleado).delete()

    def test_vacaciones_rango_valido_por_post(self):
        self.client.force_login(self.empleado)
        hoy = timezone.localdate()
        response = self.client.post(reverse('vacaciones'), self.datos_vacaciones(
            desde=hoy + timedelta(days=2), hasta=hoy + timedelta(days=5)), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Solicitud.objects.filter(usuario=self.empleado, tipo=Solicitud.Tipo.VACACIONES).exists())

    def test_certificado_motivo_corto(self):
        form = SolicitudCertificadoForm(data={'motivo': 'abc'})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['motivo'][0], 'El motivo debe tener entre 5 y 200 caracteres.')

    def test_post_tipo_nomina_crea_solo_certificado(self):
        self.client.force_login(self.empleado)
        response = self.client.post(reverse('nomina_consultar'), {'tipo': 'NOMINA', 'motivo': 'Trámite laboral'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Solicitud.objects.filter(usuario=self.empleado, tipo=Solicitud.Tipo.CERTIFICADO).exists())
        self.assertFalse(Solicitud.objects.filter(usuario=self.empleado, tipo=Solicitud.Tipo.NOMINA).exists())

    def test_bandeja_rechazo_con_texto_no_permitido_no_cambia_estado(self):
        solicitud = Solicitud.objects.create(usuario=self.empleado, tipo=Solicitud.Tipo.CERTIFICADO,
            motivo='Certificado', estado=Solicitud.Estado.PENDIENTE)
        self.client.force_login(self.auxiliar)
        response = self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': solicitud.pk, 'accion': 'rechazar', 'motivo_rechazo': '<b>malo</b>'}, follow=True)
        self.assertContains(response, 'El motivo del rechazo contiene caracteres no permitidos.')
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, Solicitud.Estado.PENDIENTE)

    def test_bandeja_rechaza_id_no_numerico(self):
        self.client.force_login(self.auxiliar)
        response = self.client.post(reverse('bandeja_aprobacion'), {
            'solicitud_id': 'abc', 'accion': 'rechazar'}, follow=True)
        self.assertContains(response, 'La solicitud indicada no es válida.')

    def test_historial_fecha_desde_posterior(self):
        self.client.force_login(self.empleado)
        response = self.client.get(reverse('nomina_historial'), {'desde': '2026-10-10', 'hasta': '2026-10-01'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(str(message) == 'La fecha "desde" no puede ser posterior a la fecha "hasta".'
                            for message in response.context['messages']))

    def test_constraint_bonificacion_porcentaje_150(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ConfiguracionBonificacion.objects.create(
                    usuario=self.empleado, porcentaje=150, meta_mensual=100)

    def test_constraint_hora_salida_antes_de_ingreso(self):
        hoy = timezone.localdate()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                HoraExtra.objects.create(usuario=self.empleado, fecha=hoy,
                    hora_ingreso=time(18), hora_salida=time(8), tipo=HoraExtra.Tipo.DIURNA,
                    cantidad_horas=1, valor=0, motivo='Trabajo extra', periodo=hoy.strftime('%Y-%m'))


class ValidadoresCompartidosTest(SimpleTestCase):
    def test_solo_letras_acepta_tildes_ene_y_rechaza_digitos(self):
        validar_solo_letras('María Núñez')
        with self.assertRaises(ValidationError): validar_solo_letras('María 2')

    def test_usuario_acepta_formato_y_rechaza_espacios_y_tildes(self):
        validar_usuario('ana.perez-2_x')
        for valor in ('ana pérez', 'niño'):
            with self.subTest(valor=valor), self.assertRaises(ValidationError): validar_usuario(valor)

    def test_texto_seguro_acepta_signos_permitidos_y_rechaza_caracteres(self):
        validar_texto_seguro('¿Pago: 100? Sí, #1 (bodega).')
        with self.assertRaises(ValidationError): validar_texto_seguro('Valor $100')
        with self.assertRaises(ValidationError): validar_texto_seguro('Texto <script>')

    def test_digitos_y_fecha_no_futura(self):
        validar_solo_digitos('012345')
        with self.assertRaises(ValidationError): validar_solo_digitos('12a')
        validar_fecha_no_futura(date.today())
        with self.assertRaises(ValidationError): validar_fecha_no_futura(date.today() + timedelta(days=1))

    def test_normaliza_espacios_dobles(self):
        self.assertEqual(normalizar_espacios('  Ana   María  '), 'Ana María')
