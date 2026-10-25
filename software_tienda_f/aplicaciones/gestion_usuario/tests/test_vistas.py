from django.test import TestCase
from django.contrib.auth.models import Group
from django.urls import reverse
from ..models import Usuario, Auditoria
from ..forms import UsuarioCrearForm, UsuarioActualizarForm, RolForm


class GestionUsuariosTest(TestCase):
    def setUp(self):
        self.gerente_group, _ = Group.objects.get_or_create(name='Gerente')
        self.vendedor_group, _ = Group.objects.get_or_create(name='Vendedor')
        self.gerente = Usuario.objects.create_user(
            username='gerente-t16', email='gerente-t16@example.com', password='ClaveSegura#2026')
        self.gerente.groups.add(self.gerente_group)
        self.client.force_login(self.gerente)

    def test_gerente_crea_usuario_y_registra_auditoria(self):
        respuesta = self.client.post(reverse('usuario_crear'), {
            'username': 'vendedor-t16', 'first_name': 'Violeta', 'last_name': 'Prueba',
            'email': 'vendedor-t16@example.com', 'identificacion': '9160616',
            'fecha_ingreso': '2026-01-15', 'salario_base': '1500000',
            'estado': 'ACTIVO', 'frecuencia_pago': 'MENSUAL',
            'metodo_pago': 'EFECTIVO', 'groups': [self.vendedor_group.pk],
            'password1': 'ClaveSegura#2026', 'password2': 'ClaveSegura#2026',
        })
        self.assertEqual(respuesta.status_code, 302)
        usuario = Usuario.objects.get(username='vendedor-t16')
        self.assertTrue(Auditoria.objects.filter(
            usuario=self.gerente, accion=Auditoria.Accion.CREAR,
            detalle__contains='Violeta Prueba').exists())

        respuesta = self.client.post(reverse('usuario_eliminar', args=[usuario.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Usuario.objects.filter(pk=usuario.pk).exists())
        self.assertTrue(Auditoria.objects.filter(
            usuario=self.gerente, accion=Auditoria.Accion.ELIMINAR,
            detalle__contains='vendedor-t16').exists())

    def test_gerente_edita_rol_y_auditoria_se_formatea(self):
        respuesta = self.client.post(reverse('rol_editar', args=[self.vendedor_group.pk]), {
            'name': 'Vendedor', 'permissions': [],
        })
        self.assertEqual(respuesta.status_code, 302)
        registro = Auditoria.objects.create(
            usuario=self.gerente, accion=Auditoria.Accion.CREAR, detalle='Prueba de formato')
        self.assertIn('Prueba de formato', str(registro))


class AuditoriaFiltroValidacionTest(TestCase):
    def test_fecha_invalida_muestra_error_y_responde_200(self):
        gerente_group, _ = Group.objects.get_or_create(name='Gerente')
        gerente = Usuario.objects.create_user(
            username='auditoria-filtro-gerente',
            email='auditoria-filtro-gerente@example.com',
            password='clave',
        )
        gerente.groups.add(gerente_group)
        self.client.force_login(gerente)

        response = self.client.get(reverse('auditoria'), {'fecha': 'xx'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Escribe una fecha válida en el filtro.')
