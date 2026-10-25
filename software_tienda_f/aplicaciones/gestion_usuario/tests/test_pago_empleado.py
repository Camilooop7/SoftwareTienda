from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from aplicaciones.gestion_usuario.forms import UsuarioCrearForm
from aplicaciones.gestion_usuario.models import Usuario


class PagoEmpleadoTest(CasoPruebaMixin, TestCase):
    def setUp(self):
        self.gerente = Usuario.objects.create_user(username='gerente-pago', email='gerente-pago@example.com', password='ClaveSegura1')
        self.gerente.groups.add(Group.objects.get_or_create(name='Gerente')[0])

    def datos(self, **cambios):
        datos = {'username': 'nuevo-pago', 'first_name': 'Ana', 'last_name': 'Perez', 'email': 'ana-pago@example.com', 'identificacion': '12345678', 'fecha_ingreso': '2020-01-15', 'salario_base': '1500000', 'estado': 'ACTIVO', 'groups': [str(Group.objects.get_or_create(name='Vendedor')[0].pk)], 'password1': 'ClaveSegura1', 'password2': 'ClaveSegura1', 'frecuencia_pago': 'MENSUAL', 'metodo_pago': 'TRANSFERENCIA', 'banco': 'Banco Andino', 'numero_cuenta': '12345678'}
        datos.update(cambios)
        return datos

    def valida_error(self, cambios, campo, mensaje):
        form = UsuarioCrearForm(data=self.datos(**cambios))
        form.is_valid()
        real = form.errors[campo][0]
        self.obtenido(f'Mensaje mostrado: {real}')
        self.assertEqual(real, mensaje)

    @caso('RF-006', 'Validar que transferencia requiera banco.', "método: TRANSFERENCIA; banco: ''", 'El formulario solicita indicar el banco.')
    def test_transferencia_sin_banco(self):
        self.valida_error({'banco': ''}, 'banco', 'Indica el banco para pagos por transferencia.')

    @caso('RF-006', 'Validar que transferencia requiera número de cuenta.', "método: TRANSFERENCIA; número de cuenta: ''", 'El formulario solicita indicar el número de cuenta.')
    def test_transferencia_sin_cuenta(self):
        self.valida_error({'numero_cuenta': ''}, 'numero_cuenta', 'Indica el número de cuenta para pagos por transferencia.')

    @caso('RF-006', 'Validar que número de cuenta solo acepte dígitos.', "número de cuenta: '123abc'", 'El formulario informa que la cuenta solo puede contener números.')
    def test_cuenta_con_letras(self):
        self.valida_error({'numero_cuenta': '123abc'}, 'numero_cuenta', 'El número de cuenta solo puede contener números.')

    @caso('RF-006', 'Validar longitud mínima de número de cuenta.', "número de cuenta: '12345'", 'El formulario informa que la cuenta debe tener entre 6 y 20 dígitos.')
    def test_cuenta_corta(self):
        self.valida_error({'numero_cuenta': '12345'}, 'numero_cuenta', 'El número de cuenta debe tener entre 6 y 20 dígitos.')

    @caso('RF-006', 'Validar que banco solo admita letras y espacios.', "banco: 'Banco 1'", 'El formulario informa que el banco solo puede contener letras y espacios.')
    def test_banco_con_numero(self):
        self.valida_error({'banco': 'Banco 1'}, 'banco', 'El banco solo puede contener letras y espacios.')

    @caso('RF-006', 'Validar que pago en efectivo no requiera datos bancarios.', "método: EFECTIVO; banco y cuenta vacíos", 'El formulario acepta el método efectivo sin datos bancarios.')
    def test_efectivo_sin_datos_bancarios_es_valido(self):
        form = UsuarioCrearForm(data=self.datos(metodo_pago='EFECTIVO', banco='', numero_cuenta=''))
        valido = form.is_valid()
        self.obtenido(f'Formulario válido: {valido}')
        self.assertTrue(valido, form.errors)

    @caso('RF-006', 'Validar limpieza del banco para pago en efectivo.', "método: EFECTIVO; banco: ''", 'El banco queda vacío en los datos validados.')
    def test_efectivo_limpia_banco(self):
        form = UsuarioCrearForm(data=self.datos(metodo_pago='EFECTIVO', banco='', numero_cuenta=''))
        form.is_valid()
        real = form.cleaned_data['banco']
        self.obtenido(f'Banco validado: {real!r}')
        self.assertEqual(real, '')

    @caso('RF-006', 'Validar limpieza de cuenta para pago en efectivo.', "método: EFECTIVO; número de cuenta: ''", 'El número de cuenta queda vacío en los datos validados.')
    def test_efectivo_limpia_cuenta(self):
        form = UsuarioCrearForm(data=self.datos(metodo_pago='EFECTIVO', banco='', numero_cuenta=''))
        form.is_valid()
        real = form.cleaned_data['numero_cuenta']
        self.obtenido(f'Cuenta validada: {real!r}')
        self.assertEqual(real, '')

    @caso('RF-006', 'Validar frecuencia de pago predeterminada del usuario.', "usuario: 'defaults-pago' sin frecuencia explícita", 'La frecuencia predeterminada es MENSUAL.')
    def test_frecuencia_pago_predeterminada(self):
        usuario = Usuario.objects.create_user(username='defaults-pago', email='defaults@example.com', password='ClaveSegura1')
        real = usuario.frecuencia_pago
        self.obtenido(f'Frecuencia: {real}')
        self.assertEqual(real, Usuario.FrecuenciaPago.MENSUAL)

    @caso('RF-006', 'Validar método de pago predeterminado del usuario.', "usuario: 'defaults-pago' sin método explícito", 'El método predeterminado es TRANSFERENCIA.')
    def test_metodo_pago_predeterminado(self):
        usuario = Usuario.objects.create_user(username='defaults-pago', email='defaults@example.com', password='ClaveSegura1')
        real = usuario.metodo_pago
        self.obtenido(f'Método: {real}')
        self.assertEqual(real, Usuario.MetodoPago.TRANSFERENCIA)

    @caso('RF-012', 'Validar que perfil muestre método de pago.', "GET /perfil/ como empleado con transferencia", 'La respuesta muestra Transferencia bancaria.')
    def test_perfil_muestra_metodo_pago(self):
        usuario = Usuario.objects.create_user(username='empleado-pago', email='empleado@example.com', password='ClaveSegura1', numero_cuenta='12345678', banco='Banco Andino')
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('perfil_actual'))
        self.obtenido(f'HTTP {respuesta.status_code}; texto: Transferencia bancaria')
        self.assertContains(respuesta, 'Transferencia bancaria')

    @caso('RF-012', 'Validar que perfil enmascare número de cuenta.', "GET /perfil/ con cuenta '12345678'", 'La respuesta muestra ****5678.')
    def test_perfil_enmascara_cuenta(self):
        usuario = Usuario.objects.create_user(username='empleado-pago', email='empleado@example.com', password='ClaveSegura1', numero_cuenta='12345678', banco='Banco Andino')
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('perfil_actual'))
        self.obtenido(f'HTTP {respuesta.status_code}; texto: ****5678')
        self.assertContains(respuesta, '****5678')

    @caso('RF-012', 'Validar que perfil no exponga la cuenta completa.', "GET /perfil/ con cuenta '12345678'", 'La respuesta no contiene 12345678.')
    def test_perfil_no_muestra_cuenta_completa(self):
        usuario = Usuario.objects.create_user(username='empleado-pago', email='empleado@example.com', password='ClaveSegura1', numero_cuenta='12345678', banco='Banco Andino')
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('perfil_actual'))
        self.obtenido(f'HTTP {respuesta.status_code}; cuenta completa presente: {"12345678" in respuesta.content.decode()}')
        self.assertNotContains(respuesta, '12345678')
