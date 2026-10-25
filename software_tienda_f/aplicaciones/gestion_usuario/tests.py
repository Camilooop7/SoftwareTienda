from django.test import TestCase
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from datetime import timedelta

from .forms import UsuarioCrearForm, UsuarioActualizarForm, RolForm
from .validators import ComplejidadContrasenaValidator

# Create your tests here.


from django.contrib.auth.models import Group
from django.urls import reverse
from .models import Usuario, Auditoria


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
            'estado': 'ACTIVO', 'groups': [self.vendedor_group.pk],
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


class ValidacionesGestionUsuarioTest(TestCase):
    def setUp(self):
        self.rol = Group.objects.create(name='Vendedor')

    def datos(self, **cambios):
        datos = {
            'username': 'usuario.test', 'first_name': 'María José',
            'last_name': 'Pérez Gómez', 'email': 'persona@example.com',
            'identificacion': '9160616', 'fecha_ingreso': '2020-01-15',
            'salario_base': '1500000,50', 'estado': 'ACTIVO',
            'groups': [str(self.rol.pk)], 'password1': 'ClaveSegura#2026',
            'password2': 'ClaveSegura#2026',
        }
        datos.update(cambios)
        return datos

    def error_form(self, cambios, campo, mensaje, form_class=UsuarioCrearForm,
                   instance=None):
        form = form_class(data=self.datos(**cambios), instance=instance)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors[campo], [mensaje])

    def test_username_invalido_longitud_y_duplicado(self):
        self.error_form({'username': 'usuario con espacio'}, 'username',
            'El nombre de usuario solo puede tener letras sin tilde, números, punto, guion y guion bajo, sin espacios.')
        self.error_form({'username': 'usuário'}, 'username',
            'El nombre de usuario solo puede tener letras sin tilde, números, punto, guion y guion bajo, sin espacios.')
        self.error_form({'username': 'abc'}, 'username',
            'El nombre de usuario debe tener entre 4 y 150 caracteres.')
        Usuario.objects.create_user(username='Duplicado', email='otro@example.com', password='Clave#123')
        self.error_form({'username': 'duplicado'}, 'username',
            'Ya existe un usuario con ese nombre de usuario.')

    def test_nombres_solo_letras(self):
        self.error_form({'first_name': 'Ana2'}, 'first_name',
                        'Los nombres solo puede contener letras y espacios.')

    def test_email_formato_y_unicidad(self):
        self.error_form({'email': 'correo-malo'}, 'email',
            'Escribe un correo electrónico válido, por ejemplo nombre@dominio.com.')
        Usuario.objects.create_user(username='otro', email='Repetido@example.com', password='Clave#123')
        self.error_form({'email': 'REPETIDO@example.com'}, 'email',
                        'Ya existe un usuario con ese correo electrónico.')

    def test_identificacion_reglas(self):
        for valor, mensaje in [
            ('91A0616', 'La identificación solo puede contener números.'),
            ('1234', 'La identificación debe tener entre 5 y 12 dígitos.'),
            ('01234', 'La identificación no puede empezar con cero.'),
        ]:
            self.error_form({'identificacion': valor}, 'identificacion', mensaje)
        Usuario.objects.create_user(username='otro', email='otro@example.com',
                                    password='Clave#123', identificacion=9160616)
        self.error_form({'identificacion': '9160616'}, 'identificacion',
                        'Ya existe un usuario con esa identificación.')

    def test_creacion_guarda_identificacion_de_12_digitos(self):
        form = UsuarioCrearForm(data=self.datos(identificacion='123456789012'))
        self.assertTrue(form.is_valid(), form.errors)
        usuario = form.save()
        usuario_guardado = Usuario.objects.get(pk=usuario.pk)
        self.assertEqual(usuario_guardado.identificacion, 123456789012)

    def test_fecha_ingreso_rangos(self):
        futura = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.error_form({'fecha_ingreso': futura}, 'fecha_ingreso',
                        'La fecha de ingreso no puede ser posterior a hoy.')
        self.error_form({'fecha_ingreso': '1949-12-31'}, 'fecha_ingreso',
                        'La fecha de ingreso no puede ser anterior a 1950.')

    def test_salario_rangos_y_decimales(self):
        for valor, mensaje in [
            ('0', 'El salario base debe ser mayor que cero.'),
            ('-1', 'El salario base debe ser mayor que cero.'),
            ('1000000000', 'El salario base no puede superar $999.999.999.'),
            ('10,123', 'El salario base admite máximo 2 decimales.'),
        ]:
            self.error_form({'salario_base': valor}, 'salario_base', mensaje)
        form = UsuarioCrearForm(data=self.datos())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(str(form.cleaned_data['salario_base']), '1500000.50')

    def test_roles_obligatorio_y_unico(self):
        self.error_form({'groups': []}, 'groups', 'Selecciona el rol del usuario.')
        segundo = Group.objects.create(name='Auxiliar')
        self.error_form({'groups': [str(self.rol.pk), str(segundo.pk)]}, 'groups',
                        'Un usuario solo puede tener un rol.')

    def test_complejidad_contrasena(self):
        validator = ComplejidadContrasenaValidator()
        with self.assertRaises(ValidationError) as error:
            validator.validate('ClaveSegura#')
        self.assertEqual(error.exception.messages, ['La contraseña debe contener al menos un número.'])
        with self.assertRaises(ValidationError) as error:
            validator.validate('ClaveSegura2026')
        self.assertEqual(error.exception.messages,
            ['La contraseña debe contener al menos un carácter especial (por ejemplo # $ % &).'])

    def test_rol_reglas(self):
        form = RolForm(data={'name': 'Rol2', 'permissions': []}, instance=Group(name=''))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['name'], ['El nombre del rol solo puede contener letras y espacios.'])
        Group.objects.create(name='Gerente')
        form = RolForm(data={'name': 'gerente', 'permissions': []}, instance=Group(name=''))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['name'], ['Ya existe un rol con ese nombre.'])

    def test_edicion_conserva_identificacion_y_correo(self):
        usuario = Usuario.objects.create_user(username='editar', email='editar@example.com',
            password='Clave#123', first_name='Ana', last_name='Pérez',
            identificacion=9160616, fecha_ingreso='2020-01-15', salario_base=100)
        usuario.groups.add(self.rol)
        form = UsuarioActualizarForm(data=self.datos(username='editar',
            email='EDITAR@example.com', identificacion='9160616'), instance=usuario)
        self.assertTrue(form.is_valid(), form.errors)

    def test_constraint_impide_salario_negativo_por_orm(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Usuario.objects.create_user(username='negativo', email='neg@example.com',
                                            password='Clave#123', salario_base=-1)


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
