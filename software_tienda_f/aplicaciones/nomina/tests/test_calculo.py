from datetime import date, time
from decimal import Decimal
from django.test import TestCase, SimpleTestCase
from aplicaciones.gestion_usuario.models import Usuario
from ..models import ConfiguracionBonificacion, HoraExtra, Nomina, Solicitud
from ..services import calcular_nomina, calcular_horas_extra, generar_prenomina, aceptar_prenomina, rechazar_prenomina
from .utils import crear_usuario
from ..excepciones import HoraExtraInvalidaError, MotivoRechazoRequeridoError, NominaYaCalculadaError, PreNominaNoPendienteError, SinEmpleadosActivosError


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


from datetime import date, time
from django.test import TestCase
from aplicaciones.gestion_usuario.models import Usuario
from ..excepciones import HoraExtraInvalidaError
from ..services import calcular_horas_extra


class CalcularHorasExtraTest(TestCase):
    def setUp(self):
        self.usuario = crear_usuario('extra-unit', salario_base=Decimal('1000000'))

    def test_jornada_hasta_8_4_no_crea_registro(self):
        self.assertIsNone(calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(16, 24), 'turno'))

    def test_calcula_extra_diurna_y_periodo(self):
        extra = calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(18), 'turno')
        self.assertEqual(extra.tipo, 'DIURNA')
        self.assertEqual(extra.cantidad_horas, Decimal('1.6'))
        self.assertEqual(extra.valor, Decimal('9600'))
        self.assertEqual(extra.periodo, '2026-05')

    def test_calcula_extra_nocturna(self):
        extra = calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(21), 'turno')
        self.assertEqual(extra.tipo, 'NOCTURNA')
        self.assertEqual(extra.cantidad_horas, Decimal('4.6'))
        self.assertEqual(extra.valor, Decimal('36800'))

    def test_salida_igual_ingreso_tiene_mensaje(self):
        with self.assertRaises(HoraExtraInvalidaError) as error:
            calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(8), 'turno')
        self.assertEqual(str(error.exception), 'La hora de salida debe ser posterior a la hora de ingreso.')


class CalcularNominaAdicionalTest(TestCase):
    def setUp(self):
        self.usuario = crear_usuario('calc-adicional', salario_base=Decimal('1423500'))

    def test_redondeo_salud_y_pension_para_salario_impar(self):
        nomina = calcular_nomina(self.usuario, '2026-05')
        self.assertEqual(nomina.deduccion_salud, Decimal('56940'))
        self.assertEqual(nomina.deduccion_pension, Decimal('56940'))
        self.assertEqual(nomina.deducciones, nomina.deduccion_salud + nomina.deduccion_pension)

    def test_bonificacion_porcentaje_de_meta_y_redondeo(self):
        ConfiguracionBonificacion.objects.create(usuario=self.usuario, porcentaje=Decimal('10'), meta_mensual=Decimal('125.55'))
        nomina = calcular_nomina(self.usuario, '2026-05')
        self.assertEqual(nomina.valor_bonificacion, Decimal('13'))

    def test_sin_configuracion_bonificacion_es_cero(self):
        self.usuario.salario_base = Decimal('1000001')
        self.usuario.save(update_fields=['salario_base'])
        nomina = calcular_nomina(self.usuario, '2026-05')
        self.assertEqual(nomina.valor_bonificacion, Decimal('0'))
        self.assertEqual(nomina.deduccion_salud, Decimal('40000'))
        self.assertEqual(nomina.deduccion_pension, Decimal('40000'))

    def test_bono_y_extras_del_periodo_sin_afectar_deducciones(self):
        self.usuario.salario_base = Decimal('1000000')
        self.usuario.save(update_fields=['salario_base'])
        ConfiguracionBonificacion.objects.create(usuario=self.usuario, porcentaje=Decimal('50'), meta_mensual=Decimal('2000000'))
        for periodo, valor in [('2026-05', '100'), ('2026-05', '200'), ('2026-04', '9000')]:
            HoraExtra.objects.create(usuario=self.usuario, fecha=date(2026, 5, 1), hora_ingreso=time(8), hora_salida=time(17), tipo=HoraExtra.Tipo.DIURNA, cantidad_horas=Decimal('1'), valor=Decimal(valor), motivo='Prueba', periodo=periodo)
        nomina = calcular_nomina(self.usuario, '2026-05')
        self.assertEqual(nomina.valor_bonificacion, Decimal('1000000'))
        self.assertEqual(nomina.valor_horas_extra, Decimal('300'))
        self.assertEqual(nomina.deduccion_salud, Decimal('40000'))
        self.assertEqual(nomina.deduccion_pension, Decimal('40000'))
        self.assertEqual(nomina.total_pagar, Decimal('1920300'))

    def test_total_pagar_cumple_identidad_para_cinco_salarios(self):
        for indice, salario in enumerate(('100000', '1423500', '1000001', '2500000', '9876543')):
            with self.subTest(salario=salario):
                usuario = crear_usuario('propiedad-{0}'.format(indice), salario_base=Decimal(salario))
                nomina = calcular_nomina(usuario, '2026-06')
                self.assertEqual(nomina.total_pagar, nomina.salario_bruto + nomina.valor_bonificacion + nomina.valor_horas_extra - nomina.deducciones)
