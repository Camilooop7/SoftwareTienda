from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from aplicaciones.gestion_usuario.forms import UsuarioCrearForm
from aplicaciones.gestion_usuario.models import Usuario


class PagoEmpleadoTest(TestCase):
    def setUp(self):
        self.gerente = Usuario.objects.create_user(username='gerente-pago', email='gerente-pago@example.com', password='ClaveSegura1')
        self.gerente.groups.add(Group.objects.get_or_create(name='Gerente')[0])

    def datos(self, **cambios):
        datos = {
            'username': 'nuevo-pago', 'first_name': 'Ana', 'last_name': 'Perez',
            'email': 'ana-pago@example.com', 'identificacion': '12345678',
            'fecha_ingreso': '2020-01-15', 'salario_base': '1500000',
            'estado': 'ACTIVO', 'groups': [str(Group.objects.get_or_create(name='Vendedor')[0].pk)],
            'password1': 'ClaveSegura1', 'password2': 'ClaveSegura1',
            'frecuencia_pago': 'MENSUAL', 'metodo_pago': 'TRANSFERENCIA',
            'banco': 'Banco Andino', 'numero_cuenta': '12345678',
        }
        datos.update(cambios)
        return datos

    def test_validaciones_de_transferencia(self):
        for cambios, campo, mensaje in (
            ({'banco': ''}, 'banco', 'Indica el banco para pagos por transferencia.'),
            ({'numero_cuenta': ''}, 'numero_cuenta', 'Indica el número de cuenta para pagos por transferencia.'),
            ({'numero_cuenta': '123abc'}, 'numero_cuenta', 'El número de cuenta solo puede contener números.'),
            ({'numero_cuenta': '12345'}, 'numero_cuenta', 'El número de cuenta debe tener entre 6 y 20 dígitos.'),
            ({'banco': 'Banco 1'}, 'banco', 'El banco solo puede contener letras y espacios.'),
        ):
            form = UsuarioCrearForm(data=self.datos(**cambios))
            self.assertFalse(form.is_valid())
            self.assertIn(mensaje, form.errors[campo])

    def test_efectivo_limpia_banco_y_cuenta_y_valores_por_defecto(self):
        form = UsuarioCrearForm(data=self.datos(metodo_pago='EFECTIVO', banco='', numero_cuenta=''))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['banco'], '')
        self.assertEqual(form.cleaned_data['numero_cuenta'], '')
        usuario = Usuario.objects.create_user(username='defaults-pago', email='defaults@example.com', password='ClaveSegura1')
        self.assertEqual(usuario.frecuencia_pago, Usuario.FrecuenciaPago.MENSUAL)
        self.assertEqual(usuario.metodo_pago, Usuario.MetodoPago.TRANSFERENCIA)

    def test_perfil_muestra_metodo_y_cuenta_enmascarada(self):
        usuario = Usuario.objects.create_user(username='empleado-pago', email='empleado@example.com', password='ClaveSegura1', numero_cuenta='12345678', banco='Banco Andino')
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('perfil_actual'))
        self.assertContains(respuesta, 'Transferencia bancaria')
        self.assertContains(respuesta, '****5678')
        self.assertNotContains(respuesta, '12345678')
