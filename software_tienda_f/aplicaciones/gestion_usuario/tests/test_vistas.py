from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from django.test import TestCase
from django.contrib.auth.models import Group
from django.urls import reverse
from ..models import Usuario, Auditoria


class GestionUsuariosTest(CasoPruebaMixin, TestCase):
    def setUp(self):
        self.gerente_group, _ = Group.objects.get_or_create(name='Gerente')
        self.vendedor_group, _ = Group.objects.get_or_create(name='Vendedor')
        self.gerente = Usuario.objects.create_user(username='gerente-t16', email='gerente-t16@example.com', password='ClaveSegura#2026')
        self.gerente.groups.add(self.gerente_group)
        self.client.force_login(self.gerente)

    def crea_usuario(self):
        return self.client.post(reverse('usuario_crear'), {'username': 'vendedor-t16', 'first_name': 'Violeta', 'last_name': 'Prueba', 'email': 'vendedor-t16@example.com', 'identificacion': '9160616', 'fecha_ingreso': '2026-01-15', 'salario_base': '1500000', 'estado': 'ACTIVO', 'frecuencia_pago': 'MENSUAL', 'metodo_pago': 'EFECTIVO', 'groups': [self.vendedor_group.pk], 'password1': 'ClaveSegura#2026', 'password2': 'ClaveSegura#2026'})

    @caso('RF-001', 'Validar que gerente cree usuario empleado.', 'POST /usuarios/crear/ con usuario vendedor-t16', 'La respuesta HTTP 302 y el usuario queda registrado.')
    def test_gerente_crea_usuario(self):
        respuesta = self.crea_usuario()
        existe = Usuario.objects.filter(username='vendedor-t16').exists()
        self.obtenido(f'HTTP {respuesta.status_code}; usuario creado: {existe}')
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(existe)

    @caso('RF-017', 'Validar auditoría al crear usuario.', 'POST de creación de vendedor-t16 por gerente', 'Auditoría registra acción CREAR y el nombre Violeta Prueba.')
    def test_crear_usuario_registra_auditoria(self):
        self.crea_usuario()
        existe = Auditoria.objects.filter(usuario=self.gerente, accion=Auditoria.Accion.CREAR, detalle__contains='Violeta Prueba').exists()
        self.obtenido(f'Registro de auditoría encontrado: {existe}')
        self.assertTrue(existe)

    @caso('RF-001', 'Validar que gerente elimine usuario empleado.', 'POST eliminar usuario vendedor-t16 existente', 'La respuesta HTTP 302 y el usuario deja de existir.')
    def test_gerente_elimina_usuario(self):
        self.crea_usuario()
        usuario = Usuario.objects.get(username='vendedor-t16')
        respuesta = self.client.post(reverse('usuario_eliminar', args=[usuario.pk]))
        existe = Usuario.objects.filter(pk=usuario.pk).exists()
        self.obtenido(f'HTTP {respuesta.status_code}; usuario existente: {existe}')
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(existe)

    @caso('RF-017', 'Validar auditoría al eliminar usuario.', 'POST eliminar usuario vendedor-t16 por gerente', 'Auditoría registra acción ELIMINAR y el username vendedor-t16.')
    def test_eliminar_usuario_registra_auditoria(self):
        self.crea_usuario()
        usuario = Usuario.objects.get(username='vendedor-t16')
        self.client.post(reverse('usuario_eliminar', args=[usuario.pk]))
        existe = Auditoria.objects.filter(usuario=self.gerente, accion=Auditoria.Accion.ELIMINAR, detalle__contains='vendedor-t16').exists()
        self.obtenido(f'Registro de auditoría encontrado: {existe}')
        self.assertTrue(existe)

    @caso('RF-014', 'Validar edición de rol por gerente.', 'POST editar rol Vendedor sin permisos', 'La respuesta HTTP 302.')
    def test_gerente_edita_rol(self):
        respuesta = self.client.post(reverse('rol_editar', args=[self.vendedor_group.pk]), {'name': 'Vendedor', 'permissions': []})
        self.obtenido(f'HTTP {respuesta.status_code}; redirige a {respuesta.url}')
        self.assertEqual(respuesta.status_code, 302)

    @caso('RF-017', 'Validar representación textual de auditoría.', "registro con detalle 'Prueba de formato'", 'La representación incluye Prueba de formato.')
    def test_auditoria_se_formatea(self):
        registro = Auditoria.objects.create(usuario=self.gerente, accion=Auditoria.Accion.CREAR, detalle='Prueba de formato')
        real = str(registro)
        self.obtenido(f'Representación: {real}')
        self.assertIn('Prueba de formato', real)


class AuditoriaFiltroValidacionTest(CasoPruebaMixin, TestCase):
    def setUp(self):
        gerente_group, _ = Group.objects.get_or_create(name='Gerente')
        gerente = Usuario.objects.create_user(username='auditoria-filtro-gerente', email='auditoria-filtro-gerente@example.com', password='clave')
        gerente.groups.add(gerente_group)
        self.client.force_login(gerente)

    @caso('RF-017', 'Validar respuesta HTTP del filtro de auditoría con fecha inválida.', "GET /auditoria/?fecha=xx como Gerente", 'La respuesta es HTTP 200.')
    def test_fecha_invalida_responde_200(self):
        response = self.client.get(reverse('auditoria'), {'fecha': 'xx'})
        self.obtenido(f'HTTP {response.status_code}')
        self.assertEqual(response.status_code, 200)

    @caso('RF-017', 'Validar mensaje de fecha inválida en auditoría.', "GET /auditoria/?fecha=xx como Gerente", 'La respuesta muestra Escribe una fecha válida en el filtro.')
    def test_fecha_invalida_muestra_mensaje(self):
        response = self.client.get(reverse('auditoria'), {'fecha': 'xx'})
        real = 'Escribe una fecha válida en el filtro.' if b'Escribe una fecha v' in response.content else 'Mensaje no encontrado'
        self.obtenido(f'Mensaje mostrado: {real}')
        self.assertContains(response, 'Escribe una fecha válida en el filtro.')
