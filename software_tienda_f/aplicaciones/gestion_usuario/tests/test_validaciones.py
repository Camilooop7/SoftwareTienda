from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from datetime import timedelta
from django.test import TestCase, SimpleTestCase
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..forms import UsuarioCrearForm, UsuarioActualizarForm, RolForm
from ..validators import ComplejidadContrasenaValidator
from ..models import Usuario


class ValidacionesGestionUsuarioTest(CasoPruebaMixin, TestCase):
    def setUp(self):
        self.rol = Group.objects.create(name='Vendedor')

    def datos(self, **cambios):
        datos = {'username': 'usuario.test', 'first_name': 'María José', 'last_name': 'Pérez Gómez', 'email': 'persona@example.com', 'identificacion': '9160616', 'fecha_ingreso': '2020-01-15', 'salario_base': '1500000,50', 'estado': 'ACTIVO', 'frecuencia_pago': 'MENSUAL', 'metodo_pago': 'EFECTIVO', 'groups': [str(self.rol.pk)], 'password1': 'ClaveSegura#2026', 'password2': 'ClaveSegura#2026'}
        datos.update(cambios)
        return datos

    def error_form(self, cambios, campo, mensaje, form_class=UsuarioCrearForm, instance=None):
        form = form_class(data=self.datos(**cambios), instance=instance)
        valido = form.is_valid()
        real = form.errors[campo][0]
        self.obtenido(f'Mensaje mostrado: {real}')
        self.assertFalse(valido)
        self.assertEqual(real, mensaje)

    @caso('RF-009', 'Validar que username rechace espacios.', "username: 'usuario con espacio'", 'El usuario recibe el mensaje de caracteres permitidos.')
    def test_username_con_espacio(self):
        self.error_form({'username': 'usuario con espacio'}, 'username', 'El nombre de usuario solo puede tener letras sin tilde, números, punto, guion y guion bajo, sin espacios.')

    @caso('RF-009', 'Validar que username rechace letras con tilde.', "username: 'usuário'", 'El usuario recibe el mensaje de caracteres permitidos.')
    def test_username_con_tilde(self):
        self.error_form({'username': 'usuário'}, 'username', 'El nombre de usuario solo puede tener letras sin tilde, números, punto, guion y guion bajo, sin espacios.')

    @caso('RF-009', 'Validar longitud mínima de username.', "username: 'abc'", 'El usuario recibe el mensaje de longitud entre 4 y 150 caracteres.')
    def test_username_corto(self):
        self.error_form({'username': 'abc'}, 'username', 'El nombre de usuario debe tener entre 4 y 150 caracteres.')

    @caso('RF-009', 'Validar que username duplicado no se registre.', "username: 'duplicado'; existe 'Duplicado'", 'El formulario informa que el nombre de usuario ya existe.')
    def test_username_duplicado(self):
        Usuario.objects.create_user(username='Duplicado', email='otro@example.com', password='Clave#123')
        self.error_form({'username': 'duplicado'}, 'username', 'Ya existe un usuario con ese nombre de usuario.')

    @caso('RF-001', 'Validar que nombres rechace números.', "nombres: 'Ana2'", 'El formulario informa que nombres solo admite letras y espacios.')
    def test_nombres_solo_letras(self):
        self.error_form({'first_name': 'Ana2'}, 'first_name', 'El campo nombres solo puede contener letras y espacios.')

    @caso('RF-009', 'Validar formato de correo electrónico.', "correo: 'correo-malo'", 'El formulario informa que el correo no tiene formato válido.')
    def test_email_formato(self):
        self.error_form({'email': 'correo-malo'}, 'email', 'Escribe un correo electrónico válido, por ejemplo nombre@dominio.com.')

    @caso('RF-009', 'Validar unicidad del correo electrónico.', "correo: 'REPETIDO@example.com'; existe 'Repetido@example.com'", 'El formulario informa que el correo ya existe.')
    def test_email_duplicado(self):
        Usuario.objects.create_user(username='otro', email='Repetido@example.com', password='Clave#123')
        self.error_form({'email': 'REPETIDO@example.com'}, 'email', 'Ya existe un usuario con ese correo electrónico.')

    @caso('RF-001', 'Validar que identificación rechace letras.', "identificación: '91A0616'", 'El formulario informa que identificación solo admite números.')
    def test_identificacion_con_letras(self):
        self.error_form({'identificacion': '91A0616'}, 'identificacion', 'La identificación solo puede contener números.')

    @caso('RF-001', 'Validar longitud mínima de identificación.', "identificación: '1234'", 'El formulario informa que identificación debe tener entre 5 y 12 dígitos.')
    def test_identificacion_corta(self):
        self.error_form({'identificacion': '1234'}, 'identificacion', 'La identificación debe tener entre 5 y 12 dígitos.')

    @caso('RF-001', 'Validar que identificación no empiece en cero.', "identificación: '01234'", 'El formulario informa que identificación no puede empezar con cero.')
    def test_identificacion_empieza_en_cero(self):
        self.error_form({'identificacion': '01234'}, 'identificacion', 'La identificación no puede empezar con cero.')

    @caso('RF-001', 'Validar que identificación duplicada sea rechazada.', "identificación: '9160616'; ya registrada", 'El formulario informa que identificación ya existe.')
    def test_identificacion_duplicada(self):
        Usuario.objects.create_user(username='otro', email='otro@example.com', password='Clave#123', identificacion=9160616)
        self.error_form({'identificacion': '9160616'}, 'identificacion', 'Ya existe un usuario con esa identificación.')

    @caso('RF-001', 'Validar que se guarde identificación de 12 dígitos.', "identificación: '123456789012'", 'El registro guarda identificación 123456789012.')
    def test_creacion_guarda_identificacion_de_12_digitos(self):
        form = UsuarioCrearForm(data=self.datos(identificacion='123456789012'))
        self.assertTrue(form.is_valid(), form.errors)
        usuario = form.save()
        usuario_guardado = Usuario.objects.get(pk=usuario.pk)
        self.obtenido(f'Identificación guardada: {usuario_guardado.identificacion}')
        self.assertEqual(usuario_guardado.identificacion, 123456789012)

    @caso('RF-001', 'Validar que fecha de ingreso futura sea rechazada.', 'fecha de ingreso: mañana', 'El formulario informa que la fecha no puede ser posterior a hoy.')
    def test_fecha_ingreso_futura(self):
        futura = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.error_form({'fecha_ingreso': futura}, 'fecha_ingreso', 'La fecha de ingreso no puede ser posterior a hoy.')

    @caso('RF-001', 'Validar fecha mínima de ingreso.', "fecha de ingreso: '1949-12-31'", 'El formulario informa que la fecha no puede ser anterior a 1950.')
    def test_fecha_ingreso_anterior_a_1950(self):
        self.error_form({'fecha_ingreso': '1949-12-31'}, 'fecha_ingreso', 'La fecha de ingreso no puede ser anterior a 1950.')

    @caso('RF-001', 'Validar salario base cero.', "salario base: '0'", 'El formulario informa que el salario debe ser mayor que cero.')
    def test_salario_cero(self):
        self.error_form({'salario_base': '0'}, 'salario_base', 'El salario base debe ser mayor que cero.')

    @caso('RF-001', 'Validar salario base negativo.', "salario base: '-1'", 'El formulario informa que el salario debe ser mayor que cero.')
    def test_salario_negativo(self):
        self.error_form({'salario_base': '-1'}, 'salario_base', 'El salario base debe ser mayor que cero.')

    @caso('RF-001', 'Validar límite máximo del salario base.', "salario base: '1000000000'", 'El formulario informa que el salario no puede superar $999.999.999.')
    def test_salario_supera_maximo(self):
        self.error_form({'salario_base': '1000000000'}, 'salario_base', 'El salario base no puede superar $999.999.999.')

    @caso('RF-001', 'Validar máximo de dos decimales del salario.', "salario base: '10,123'", 'El formulario informa que admite máximo 2 decimales.')
    def test_salario_tres_decimales(self):
        self.error_form({'salario_base': '10,123'}, 'salario_base', 'El salario base admite máximo 2 decimales.')

    @caso('RF-001', 'Validar conversión decimal del salario base.', "salario base: '1500000,50'", 'El valor normalizado es 1500000.50.')
    def test_salario_decimal_normalizado(self):
        form = UsuarioCrearForm(data=self.datos())
        self.assertTrue(form.is_valid(), form.errors)
        valor = str(form.cleaned_data['salario_base'])
        self.obtenido(f'Salario normalizado: {valor}')
        self.assertEqual(valor, '1500000.50')

    @caso('RF-009', 'Validar que el formulario requiera al menos un rol.', 'roles: []', 'El formulario informa que debe seleccionarse al menos un rol.')
    def test_roles_obligatorio(self):
        self.error_form({'groups': []}, 'groups', 'Selecciona al menos un rol para el usuario.')

    @caso('RF-015', 'Validar que un usuario pueda tener varios roles.', 'roles: Vendedor y Auxiliar', 'El formulario acepta ambos roles.')
    def test_varios_roles_permitidos(self):
        segundo = Group.objects.create(name='Auxiliar')
        form = UsuarioCrearForm(data=self.datos(groups=[str(self.rol.pk), str(segundo.pk)]))
        valido = form.is_valid()
        self.obtenido(f'Formulario válido: {valido}')
        self.assertTrue(valido, form.errors)

    @caso('RNF-004', 'Validar rechazo de contraseña sin mayúscula.', "contraseña: 'clavesegura1'", 'Se informa que falta una mayúscula.')
    def test_contrasena_sin_mayuscula(self):
        self.validar_password_error('clavesegura1', 'La contraseña debe contener al menos una letra mayúscula.')

    @caso('RNF-004', 'Validar rechazo de contraseña sin minúscula.', "contraseña: 'CLAVESEGURA1'", 'Se informa que falta una minúscula.')
    def test_contrasena_sin_minuscula(self):
        self.validar_password_error('CLAVESEGURA1', 'La contraseña debe contener al menos una letra minúscula.')

    @caso('RNF-004', 'Validar rechazo de contraseña sin número.', "contraseña: 'ClaveSegura'", 'Se informa que falta un número.')
    def test_contrasena_sin_numero(self):
        self.validar_password_error('ClaveSegura', 'La contraseña debe contener al menos un número.')

    def validar_password_error(self, password, mensaje):
        try:
            ComplejidadContrasenaValidator().validate(password)
        except ValidationError as error:
            real = error.messages[0]
        else:
            real = 'Sin error de validación'
        self.obtenido(f'Mensaje mostrado: {real}')
        self.assertEqual([real], [mensaje])

    @caso('RF-014', 'Validar que nombre de rol rechace números.', "rol: 'Rol2'", 'El formulario informa que el nombre solo admite letras y espacios.')
    def test_rol_nombre_con_numero(self):
        form = RolForm(data={'name': 'Rol2', 'permissions': []}, instance=Group(name=''))
        form.is_valid()
        real = form.errors['name'][0]
        self.obtenido(f'Mensaje mostrado: {real}')
        self.assertEqual(real, 'El nombre del rol solo puede contener letras y espacios.')

    @caso('RF-014', 'Validar que nombre de rol duplicado sea rechazado.', "rol: 'gerente'; ya existe 'Gerente'", 'El formulario informa que el rol ya existe.')
    def test_rol_nombre_duplicado(self):
        Group.objects.create(name='Gerente')
        form = RolForm(data={'name': 'gerente', 'permissions': []}, instance=Group(name=''))
        form.is_valid()
        real = form.errors['name'][0]
        self.obtenido(f'Mensaje mostrado: {real}')
        self.assertEqual(real, 'Ya existe un rol con ese nombre.')

    @caso('RF-012', 'Validar edición que conserva identificación y correo propios.', "correo: 'EDITAR@example.com'; identificación: '9160616'", 'El formulario de edición acepta los datos propios sin duplicidad.')
    def test_edicion_conserva_identificacion_y_correo(self):
        usuario = Usuario.objects.create_user(username='editar', email='editar@example.com', password='Clave#123', first_name='Ana', last_name='Pérez', identificacion=9160616, fecha_ingreso='2020-01-15', salario_base=100)
        usuario.groups.add(self.rol)
        form = UsuarioActualizarForm(data=self.datos(username='editar', email='EDITAR@example.com', identificacion='9160616'), instance=usuario)
        valido = form.is_valid()
        self.obtenido(f'Formulario válido: {valido}')
        self.assertTrue(valido, form.errors)

    @caso('RF-001', 'Validar restricción ORM contra salario negativo.', "salario base ORM: -1", 'La base de datos rechaza el registro con IntegrityError.')
    def test_constraint_impide_salario_negativo_por_orm(self):
        try:
            with transaction.atomic():
                Usuario.objects.create_user(username='negativo', email='neg@example.com', password='Clave#123', salario_base=-1)
        except IntegrityError as error:
            real = type(error).__name__
        else:
            real = 'Sin excepción'
        self.obtenido(f'Excepción: {real}')
        self.assertEqual(real, 'IntegrityError')


class ComplejidadContrasenaCasosTest(CasoPruebaMixin, SimpleTestCase):
    @caso('RNF-004', 'Validar aceptación de contraseña compleja.', "contraseña: 'Clave#2026'", 'El validador no genera error.')
    def test_contrasena_valida(self):
        resultado = ComplejidadContrasenaValidator().validate('Clave#2026')
        self.obtenido(f'Resultado: {resultado}')
        self.assertIsNone(resultado)

    @caso('RNF-004', 'Validar que el validador entregue ayuda.', 'solicitud de texto de ayuda', 'El texto de ayuda no está vacío.')
    def test_contrasena_ayuda(self):
        ayuda = ComplejidadContrasenaValidator().get_help_text()
        self.obtenido(f'Texto de ayuda: {ayuda}')
        self.assertTrue(ayuda)

    @caso('RNF-004', 'Validar que la contraseña requiera mayúscula.', "contraseña: 'clave2026'", 'Se produce ValidationError.')
    def test_requiere_mayuscula(self):
        self.registrar_error_password('clave2026')

    @caso('RNF-004', 'Validar que la contraseña requiera minúscula.', "contraseña: 'CLAVE2026'", 'Se produce ValidationError.')
    def test_requiere_minuscula(self):
        self.registrar_error_password('CLAVE2026')

    @caso('RNF-004', 'Validar que la contraseña requiera número.', "contraseña: 'ClaveSegura'", 'Se produce ValidationError.')
    def test_requiere_numero(self):
        self.registrar_error_password('ClaveSegura')

    def registrar_error_password(self, password):
        try:
            ComplejidadContrasenaValidator().validate(password)
            real = 'Sin excepción'
        except ValidationError as error:
            real = type(error).__name__
        self.obtenido(f'Excepción: {real}')
        self.assertEqual(real, 'ValidationError')
