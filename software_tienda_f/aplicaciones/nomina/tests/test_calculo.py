from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from datetime import date, time
from decimal import Decimal
from django.test import TestCase
from aplicaciones.gestion_usuario.models import Usuario
from ..models import ConfiguracionBonificacion, HoraExtra, Nomina
from ..services import calcular_nomina, calcular_horas_extra
from .utils import crear_usuario
from ..excepciones import HoraExtraInvalidaError


class CalcularNominaTest(CasoPruebaMixin, TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='nomina-test',
            email='nomina-test@example.com',
            password='test-password',
            salario_base=Decimal('1000000'),
        )
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

    @caso('RF-008', 'Validar que salud se calcule como el 4% del salario base.',
          'Salario base 1.000.000; bonificación 50.000; horas extra 30.000; periodo 2026-09',
          'Deducción salud = 40000')
    def test_deduccion_salud_sobre_salario_base(self):
        nomina = calcular_nomina(self.usuario, '2026-09')
        self.obtenido(f'Deducción salud = {nomina.deduccion_salud}')
        self.assertEqual(nomina.deduccion_salud, Decimal('40000'))

    @caso('RF-008', 'Validar que pensión se calcule como el 4% del salario base.',
          'Salario base 1.000.000; bonificación 50.000; horas extra 30.000; periodo 2026-09',
          'Deducción pensión = 40000')
    def test_deduccion_pension_sobre_salario_base(self):
        nomina = calcular_nomina(self.usuario, '2026-09')
        self.obtenido(f'Deducción pensión = {nomina.deduccion_pension}')
        self.assertEqual(nomina.deduccion_pension, Decimal('40000'))

    @caso('RF-008', 'Validar que el total a pagar sume salario, bonificación y horas extra menos deducciones.',
          'Salario base 1.000.000; bonificación 50.000; horas extra 30.000; periodo 2026-09',
          'Total a pagar = 1000000 (1.000.000 + 50.000 + 30.000 - 80.000)')
    def test_total_pagar(self):
        nomina = calcular_nomina(self.usuario, '2026-09')
        self.obtenido(f'Total a pagar = {nomina.total_pagar}')
        self.assertEqual(nomina.total_pagar, Decimal('1000000'))

    @caso('RF-008', 'Validar que la nómina recién calculada quede en estado pendiente.',
          'Cálculo de nómina del periodo 2026-09', 'Estado = PENDIENTE')
    def test_nomina_nueva_queda_pendiente(self):
        nomina = calcular_nomina(self.usuario, '2026-09')
        self.obtenido(f'Estado = {nomina.estado}')
        self.assertEqual(nomina.estado, Nomina.Estado.PENDIENTE)

    @caso('RF-008', 'Validar que un salario de cero genere deducciones en cero.',
          'Salario base 0; periodo 2026-09', 'Deducciones totales = 0')
    def test_salario_cero_da_deducciones_cero(self):
        self.usuario.salario_base = Decimal('0')
        self.usuario.save()
        nomina = calcular_nomina(self.usuario, '2026-09')
        self.obtenido(f'Salud = {nomina.deduccion_salud}; pensión = {nomina.deduccion_pension}; total = {nomina.deducciones}')
        self.assertEqual(nomina.deducciones, Decimal('0'))


class CalcularHorasExtraTest(CasoPruebaMixin, TestCase):
    def setUp(self):
        self.usuario = crear_usuario('extra-unit', salario_base=Decimal('1000000'))

    @caso('RF-002', 'Validar que una jornada de hasta 8,4 horas no genere horas extra.',
          'Ingreso 08:00; salida 16:24 (8,4 h)', 'No se crea registro (None)')
    def test_jornada_hasta_8_4_no_crea_registro(self):
        extra = calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(16, 24), 'turno')
        self.obtenido(f'Resultado: {extra}')
        self.assertIsNone(extra)

    @caso('RF-002', 'Validar que una salida antes de las 19:00 se clasifique como hora extra diurna.',
          'Ingreso 08:00; salida 18:00', 'Tipo = DIURNA')
    def test_calcula_extra_diurna_tipo(self):
        extra = calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(18), 'turno')
        self.obtenido(f'Tipo = {extra.tipo}')
        self.assertEqual(extra.tipo, 'DIURNA')

    @caso('RF-002', 'Validar la cantidad de horas extra sobre la jornada de 8,4 horas.',
          'Ingreso 08:00; salida 18:00 (10 h)', 'Cantidad de horas = 1.6')
    def test_calcula_extra_diurna_cantidad(self):
        extra = calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(18), 'turno')
        self.obtenido(f'Cantidad de horas = {extra.cantidad_horas}')
        self.assertEqual(extra.cantidad_horas, Decimal('1.6'))

    @caso('RF-002', 'Validar el valor de las horas extra diurnas.',
          'Salario 1.000.000; ingreso 08:00; salida 18:00', 'Valor = 9600')
    def test_calcula_extra_diurna_valor(self):
        extra = calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(18), 'turno')
        self.obtenido(f'Valor = {extra.valor}')
        self.assertEqual(extra.valor, Decimal('9600'))

    @caso('RF-002', 'Validar que las horas extra se asignen al periodo de su fecha.',
          'Fecha 2026-05-03; ingreso 08:00; salida 18:00', 'Periodo = 2026-05')
    def test_calcula_extra_periodo(self):
        extra = calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(18), 'turno')
        self.obtenido(f'Periodo = {extra.periodo}')
        self.assertEqual(extra.periodo, '2026-05')

    @caso('RF-002', 'Validar que una salida después de las 19:00 se clasifique como hora extra nocturna.',
          'Ingreso 08:00; salida 21:00', 'Tipo = NOCTURNA')
    def test_calcula_extra_nocturna_tipo(self):
        extra = calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(21), 'turno')
        self.obtenido(f'Tipo = {extra.tipo}')
        self.assertEqual(extra.tipo, 'NOCTURNA')

    @caso('RF-002', 'Validar el valor de las horas extra nocturnas.',
          'Salario 1.000.000; ingreso 08:00; salida 21:00 (4,6 h extra)', 'Valor = 36800')
    def test_calcula_extra_nocturna_valor(self):
        extra = calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(21), 'turno')
        self.obtenido(f'Cantidad = {extra.cantidad_horas}; valor = {extra.valor}')
        self.assertEqual(extra.valor, Decimal('36800'))

    @caso('RF-002', 'Validar el mensaje cuando la salida es igual al ingreso.',
          'Ingreso 08:00; salida 08:00', 'La hora de salida debe ser posterior a la hora de ingreso.')
    def test_salida_igual_ingreso_tiene_mensaje(self):
        try:
            calcular_horas_extra(self.usuario, date(2026, 5, 3), time(8), time(8), 'turno')
            mensaje = 'No se lanzó excepción'
        except HoraExtraInvalidaError as error:
            mensaje = str(error)
        self.obtenido(f'Mensaje: {mensaje}')
        self.assertEqual(mensaje, 'La hora de salida debe ser posterior a la hora de ingreso.')


class CalcularNominaAdicionalTest(CasoPruebaMixin, TestCase):
    def setUp(self):
        self.usuario = crear_usuario('calc-adicional', salario_base=Decimal('1423500'))

    @caso('RF-008', 'Validar el redondeo de salud y pensión con un salario que no da valor entero.',
          'Salario base 1.423.500', 'Salud = 56940; pensión = 56940')
    def test_redondeo_salud_y_pension_para_salario_impar(self):
        nomina = calcular_nomina(self.usuario, '2026-05')
        self.obtenido(f'Salud = {nomina.deduccion_salud}; pensión = {nomina.deduccion_pension}')
        self.assertEqual((nomina.deduccion_salud, nomina.deduccion_pension), (Decimal('56940'), Decimal('56940')))

    @caso('RF-008', 'Validar que las deducciones totales sean la suma de salud y pensión.',
          'Salario base 1.423.500', 'Deducciones = 113880')
    def test_deducciones_suman_salud_y_pension(self):
        nomina = calcular_nomina(self.usuario, '2026-05')
        self.obtenido(f'Deducciones = {nomina.deducciones}')
        self.assertEqual(nomina.deducciones, Decimal('113880'))

    @caso('RF-005', 'Validar que la bonificación sea el porcentaje de la meta, redondeado.',
          'Porcentaje 10; meta mensual 125,55', 'Bonificación = 13')
    def test_bonificacion_porcentaje_de_meta_y_redondeo(self):
        ConfiguracionBonificacion.objects.create(usuario=self.usuario, porcentaje=Decimal('10'), meta_mensual=Decimal('125.55'))
        nomina = calcular_nomina(self.usuario, '2026-05')
        self.obtenido(f'Bonificación = {nomina.valor_bonificacion}')
        self.assertEqual(nomina.valor_bonificacion, Decimal('13'))

    @caso('RF-005', 'Validar que sin bonificación configurada el valor sea cero.',
          'Empleado sin configuración de bonificación', 'Bonificación = 0')
    def test_sin_configuracion_bonificacion_es_cero(self):
        nomina = calcular_nomina(self.usuario, '2026-05')
        self.obtenido(f'Bonificación = {nomina.valor_bonificacion}')
        self.assertEqual(nomina.valor_bonificacion, Decimal('0'))

    @caso('RF-008', 'Validar que salud y pensión se redondeen al peso más cercano.',
          'Salario base 1.000.001', 'Salud = 40000; pensión = 40000')
    def test_redondeo_salario_1000001(self):
        self.usuario.salario_base = Decimal('1000001')
        self.usuario.save(update_fields=['salario_base'])
        nomina = calcular_nomina(self.usuario, '2026-05')
        self.obtenido(f'Salud = {nomina.deduccion_salud}; pensión = {nomina.deduccion_pension}')
        self.assertEqual((nomina.deduccion_salud, nomina.deduccion_pension), (Decimal('40000'), Decimal('40000')))

    def nomina_con_novedades(self):
        self.usuario.salario_base = Decimal('1000000')
        self.usuario.save(update_fields=['salario_base'])
        ConfiguracionBonificacion.objects.create(usuario=self.usuario, porcentaje=Decimal('50'), meta_mensual=Decimal('2000000'))
        for periodo, valor in [('2026-05', '100'), ('2026-05', '200'), ('2026-04', '9000')]:
            HoraExtra.objects.create(usuario=self.usuario, fecha=date(2026, 5, 1), hora_ingreso=time(8), hora_salida=time(17), tipo=HoraExtra.Tipo.DIURNA, cantidad_horas=Decimal('1'), valor=Decimal(valor), motivo='Prueba', periodo=periodo)
        return calcular_nomina(self.usuario, '2026-05')

    @caso('RF-002', 'Validar que solo se sumen las horas extra del periodo calculado.',
          'Horas extra 2026-05: 100 y 200; horas extra 2026-04: 9000; cálculo de 2026-05',
          'Valor horas extra = 300')
    def test_horas_extra_solo_del_periodo(self):
        nomina = self.nomina_con_novedades()
        self.obtenido(f'Valor horas extra = {nomina.valor_horas_extra}')
        self.assertEqual(nomina.valor_horas_extra, Decimal('300'))

    @caso('RF-008', 'Validar que bonificaciones y horas extra no aumenten las deducciones.',
          'Salario 1.000.000; bonificación 1.000.000; horas extra 300',
          'Deducciones = 80000 (solo sobre el salario base)')
    def test_novedades_no_afectan_deducciones(self):
        nomina = self.nomina_con_novedades()
        self.obtenido(f'Deducciones = {nomina.deducciones}')
        self.assertEqual(nomina.deducciones, Decimal('80000'))

    @caso('RF-008', 'Validar el total a pagar con bonificación y horas extra.',
          'Salario 1.000.000; bonificación 50% de 2.000.000; horas extra 300',
          'Total a pagar = 1920300')
    def test_total_con_novedades(self):
        nomina = self.nomina_con_novedades()
        self.obtenido(f'Total a pagar = {nomina.total_pagar}')
        self.assertEqual(nomina.total_pagar, Decimal('1920300'))

    @caso('RF-008', 'Validar la fórmula del total a pagar con distintos salarios.',
          'Salarios: 100.000; 1.423.500; 1.000.001; 2.500.000; 9.876.543',
          'En los 5 casos total = salario + bonificación + horas extra - deducciones')
    def test_total_pagar_cumple_identidad_para_cinco_salarios(self):
        cumplen = 0
        for indice, salario in enumerate(('100000', '1423500', '1000001', '2500000', '9876543')):
            usuario = crear_usuario('propiedad-{0}'.format(indice), salario_base=Decimal(salario))
            nomina = calcular_nomina(usuario, '2026-06')
            if nomina.total_pagar == nomina.salario_bruto + nomina.valor_bonificacion + nomina.valor_horas_extra - nomina.deducciones:
                cumplen += 1
        self.obtenido(f'Casos que cumplen la fórmula: {cumplen} de 5')
        self.assertEqual(cumplen, 5)
