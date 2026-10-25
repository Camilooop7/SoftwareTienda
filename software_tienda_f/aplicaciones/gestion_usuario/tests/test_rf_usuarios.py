from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from aplicaciones.gestion_usuario.forms import PerfilForm
from aplicaciones.gestion_usuario.models import Auditoria, Usuario


class BaseGestionUsuariosT61(CasoPruebaMixin, TestCase):
    secuencia = 0

    @classmethod
    def setUpTestData(cls):
        cls.gerente_rol, _ = Group.objects.get_or_create(name="Gerente")
        cls.vendedor_rol, _ = Group.objects.get_or_create(name="Vendedor")
        cls.auxiliar_rol, _ = Group.objects.get_or_create(name="Auxiliar Administrativo")

    def crear_usuario(self, username=None, roles=(), **campos):
        type(self).secuencia += 1
        username = username or "usuario-t61-{0}".format(self.secuencia)
        campos.setdefault("email", "{0}@example.com".format(username))
        campos.setdefault("password", "ClaveSegura1")
        campos.setdefault("first_name", "Nombre")
        campos.setdefault("last_name", "Apellido")
        campos.setdefault("identificacion", 10000 + self.secuencia)
        usuario = Usuario.objects.create_user(username=username, **campos)
        usuario.groups.add(*roles)
        return usuario

    def post_usuario(self, roles):
        return self.client.post(reverse("usuario_crear"), {
            "username": "nuevo-t61",
            "first_name": "Nueva",
            "last_name": "Persona",
            "email": "nueva-t61@example.com",
            "identificacion": "89000123",
            "fecha_ingreso": "2020-01-15",
            "salario_base": "1500000",
            "estado": "ACTIVO",
            "frecuencia_pago": "MENSUAL",
            "metodo_pago": "EFECTIVO",
            "groups": [str(rol.pk) for rol in roles],
            "password1": "ClaveSegura1",
            "password2": "ClaveSegura1",
        })

    def mensaje_visible(self, respuesta, mensaje):
        self.obtenido(f"HTTP {respuesta.status_code}; mensaje visible: {mensaje in respuesta.content.decode()}")
        self.assertContains(respuesta, mensaje)


class LoginT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        self.usuario = self.crear_usuario(username="login-t61", email="login-t61@example.com")

    def iniciar(self, credencial, clave="ClaveSegura1"):
        respuesta = self.client.post(reverse("login"), {"username": credencial, "password": clave})
        self.obtenido(f"HTTP {respuesta.status_code}; redirección a {respuesta.get('Location')}")
        return respuesta

    @caso('RF-010', 'Validar el inicio de sesión con el correo electrónico.',
          "correo: 'login-t61@example.com'; contraseña válida", 'HTTP 302 al perfil (/usuarios/perfil/)')
    def test_login_con_correo(self):
        respuesta = self.iniciar(self.usuario.email)
        self.assertEqual(respuesta.get("Location"), reverse("perfil_actual"))

    @caso('RF-010', 'Validar que el correo no distinga mayúsculas al iniciar sesión.',
          "correo: 'LOGIN-T61@EXAMPLE.COM'; contraseña válida", 'HTTP 302 al perfil')
    def test_login_con_correo_en_mayusculas(self):
        respuesta = self.iniciar(self.usuario.email.upper())
        self.assertEqual(respuesta.get("Location"), reverse("perfil_actual"))

    @caso('RF-010', 'Validar el inicio de sesión con el nombre de usuario.',
          "usuario: 'login-t61'; contraseña válida", 'HTTP 302 al perfil')
    def test_login_con_usuario(self):
        respuesta = self.iniciar(self.usuario.username)
        self.assertEqual(respuesta.get("Location"), reverse("perfil_actual"))

    @caso('RF-010', 'Validar el mensaje de credenciales incorrectas.',
          "correo válido; contraseña 'Incorrecta1'", 'Correo/usuario o contraseña incorrectos.')
    def test_contrasena_incorrecta_muestra_mensaje(self):
        respuesta = self.client.post(reverse("login"), {"username": self.usuario.email, "password": "Incorrecta1"})
        self.mensaje_visible(respuesta, "Correo/usuario o contraseña incorrectos.")

    @caso('RF-017', 'Validar que un intento de acceso fallido quede en la auditoría.',
          "correo válido; contraseña 'Incorrecta1'", 'Registro ERROR_ACCESO con el correo usado')
    def test_contrasena_incorrecta_crea_auditoria(self):
        self.client.post(reverse("login"), {"username": self.usuario.email, "password": "Incorrecta1"})
        existe = Auditoria.objects.filter(accion=Auditoria.Accion.ERROR_ACCESO, detalle__contains=self.usuario.email).exists()
        self.obtenido(f"Auditoría ERROR_ACCESO registrada: {existe}")
        self.assertTrue(existe)


class CambioContrasenaT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        self.usuario = self.crear_usuario(username="password-t61")
        self.client.force_login(self.usuario)

    def cambiar(self, actual="ClaveSegura1", nueva="NuevaClave2"):
        return self.client.post(reverse("cambiar_contrasena"), {
            "old_password": actual, "new_password1": nueva, "new_password2": nueva,
        })

    @caso('RF-011', 'Validar que el cambio de contraseña guarde la nueva clave.',
          "actual: 'ClaveSegura1'; nueva: 'NuevaClave2'", 'La nueva contraseña queda activa')
    def test_cambio_valido_guarda_clave(self):
        self.cambiar()
        self.usuario.refresh_from_db()
        activa = self.usuario.check_password("NuevaClave2")
        self.obtenido(f"Nueva contraseña activa: {activa}")
        self.assertTrue(activa)

    @caso('RF-011', 'Validar que tras cambiar la contraseña la sesión siga abierta.',
          "actual: 'ClaveSegura1'; nueva: 'NuevaClave2'", 'Redirección al perfil y el perfil responde HTTP 200')
    def test_cambio_valido_conserva_sesion(self):
        respuesta = self.cambiar()
        estado_perfil = self.client.get(reverse("perfil_actual")).status_code
        self.obtenido(f"Redirección a {respuesta.get('Location')}; perfil HTTP {estado_perfil}")
        self.assertEqual((respuesta.get("Location"), estado_perfil), (reverse("perfil_actual"), 200))

    @caso('RF-017', 'Validar que el cambio de contraseña quede en la auditoría.',
          "Cambio de contraseña válido", "Registro 'Cambió su contraseña' del usuario")
    def test_cambio_valido_registra_auditoria(self):
        self.cambiar()
        existe = Auditoria.objects.filter(usuario=self.usuario, detalle="Cambió su contraseña").exists()
        self.obtenido(f"Auditoría registrada: {existe}")
        self.assertTrue(existe)

    @caso('RF-011', 'Validar el mensaje cuando la contraseña actual es incorrecta.',
          "actual: 'Incorrecta1'; nueva: 'NuevaClave2'", 'Tu contraseña actual es incorrecta.')
    def test_contrasena_actual_incorrecta_muestra_error(self):
        self.mensaje_visible(self.cambiar(actual="Incorrecta1"), "Tu contraseña actual es incorrecta.")

    @caso('RNF-004', 'Validar que la nueva contraseña exija una mayúscula.',
          "nueva: 'clavesegura2'", 'La contraseña debe contener al menos una letra mayúscula.')
    def test_nueva_contrasena_sin_mayuscula_muestra_mensaje(self):
        self.mensaje_visible(self.cambiar(nueva="clavesegura2"), "La contraseña debe contener al menos una letra mayúscula.")

    @caso('RNF-004', 'Validar que la nueva contraseña exija una minúscula.',
          "nueva: 'CLAVESEGURA2'", 'La contraseña debe contener al menos una letra minúscula.')
    def test_nueva_contrasena_sin_minuscula_muestra_mensaje(self):
        self.mensaje_visible(self.cambiar(nueva="CLAVESEGURA2"), "La contraseña debe contener al menos una letra minúscula.")

    @caso('RNF-004', 'Validar que la nueva contraseña exija un número.',
          "nueva: 'ClaveSegura'", 'La contraseña debe contener al menos un número.')
    def test_nueva_contrasena_sin_numero_muestra_mensaje(self):
        self.mensaje_visible(self.cambiar(nueva="ClaveSegura"), "La contraseña debe contener al menos un número.")

    @caso('RNF-004', 'Validar que la nueva contraseña tenga mínimo 8 caracteres.',
          "nueva: 'Clave12' (7 caracteres)", 'La contraseña debe tener al menos 8 caracteres.')
    def test_nueva_contrasena_de_siete_caracteres_muestra_mensaje(self):
        self.mensaje_visible(self.cambiar(nueva="Clave12"), "La contraseña debe tener al menos 8 caracteres.")


class PerfilPropioT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        self.usuario = self.crear_usuario(username="perfil-t61", roles=[self.vendedor_rol])
        self.client.force_login(self.usuario)

    @caso('RF-012', 'Validar que el empleado actualice sus nombres y apellidos.',
          "nombres: 'Nombre Nuevo'; apellidos: 'Apellido Nuevo'", "Perfil guardado con 'Nombre Nuevo Apellido Nuevo'")
    def test_vendedor_actualiza_nombres(self):
        self.client.post(reverse("perfil_editar"), {
            "first_name": "Nombre Nuevo", "last_name": "Apellido Nuevo", "email": self.usuario.email,
        })
        self.usuario.refresh_from_db()
        nombre = f"{self.usuario.first_name} {self.usuario.last_name}"
        self.obtenido(f"Nombre guardado: {nombre}")
        self.assertEqual(nombre, "Nombre Nuevo Apellido Nuevo")

    @caso('RF-012', 'Validar que el empleado actualice su correo.',
          "correo: 'nuevo-perfil@example.com'", "Correo guardado 'nuevo-perfil@example.com'")
    def test_vendedor_actualiza_correo(self):
        self.client.post(reverse("perfil_editar"), {
            "first_name": "Nombre", "last_name": "Apellido", "email": "nuevo-perfil@example.com",
        })
        self.usuario.refresh_from_db()
        self.obtenido(f"Correo guardado: {self.usuario.email}")
        self.assertEqual(self.usuario.email, "nuevo-perfil@example.com")

    @caso('RF-012', 'Validar que el perfil no acepte un correo de otro usuario.',
          'correo de otro usuario registrado', 'Ya existe un usuario con ese correo electrónico.')
    def test_correo_duplicado_muestra_mensaje(self):
        otro = self.crear_usuario(username="otro-perfil-t61")
        respuesta = self.client.post(reverse("perfil_editar"), {
            "first_name": "Nombre", "last_name": "Apellido", "email": otro.email,
        })
        self.mensaje_visible(respuesta, "Ya existe un usuario con ese correo electrónico.")

    @caso('RF-012', 'Validar que el perfil no acepte nombres con números.',
          "nombres: 'Nombre2'", 'El campo nombres solo puede contener letras y espacios.')
    def test_nombre_con_numeros_muestra_mensaje(self):
        respuesta = self.client.post(reverse("perfil_editar"), {
            "first_name": "Nombre2", "last_name": "Apellido", "email": self.usuario.email,
        })
        self.mensaje_visible(respuesta, "El campo nombres solo puede contener letras y espacios.")

    @caso('RF-012', 'Validar que el empleado no pueda editar datos administrativos desde su perfil.',
          'Formulario de perfil propio', 'Sin campos salario_base, groups, identificacion ni estado')
    def test_formulario_no_expone_campos_administrativos(self):
        campos = PerfilForm(instance=self.usuario).fields
        expuestos = [c for c in ("salario_base", "groups", "identificacion", "estado") if c in campos]
        self.obtenido(f"Campos del formulario: {list(campos)}; administrativos expuestos: {expuestos or 'ninguno'}")
        self.assertEqual(expuestos, [])


class RolesMultiplesT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        self.gerente = self.crear_usuario(username="gerente-multiples-t61", roles=[self.gerente_rol])
        self.client.force_login(self.gerente)

    def crear_con_dos_roles(self):
        self.post_usuario([self.vendedor_rol, self.auxiliar_rol])
        return Usuario.objects.get(username="nuevo-t61")

    @caso('RF-015', 'Validar que un usuario pueda registrarse con dos roles.',
          'Registro con roles Vendedor y Auxiliar Administrativo', "Roles: 'Auxiliar Administrativo, Vendedor'")
    def test_crear_usuario_con_dos_roles(self):
        roles = self.crear_con_dos_roles().obtener_rol()
        self.obtenido(f"Roles asignados: {roles}")
        self.assertEqual(roles, "Auxiliar Administrativo, Vendedor")

    @caso('RF-015', 'Validar que un usuario con dos roles acceda a la bandeja del Auxiliar.',
          'Usuario Vendedor + Auxiliar abre la bandeja de aprobación', 'HTTP 200')
    def test_dos_roles_accede_bandeja(self):
        self.client.force_login(self.crear_con_dos_roles())
        estado = self.client.get(reverse("bandeja_aprobacion")).status_code
        self.obtenido(f"HTTP {estado}")
        self.assertEqual(estado, 200)

    @caso('RF-015', 'Validar que un usuario con dos roles acceda a la consulta de nómina del Vendedor.',
          'Usuario Vendedor + Auxiliar abre la consulta de nómina', 'HTTP 200')
    def test_dos_roles_accede_consulta(self):
        self.client.force_login(self.crear_con_dos_roles())
        estado = self.client.get(reverse("nomina_consultar")).status_code
        self.obtenido(f"HTTP {estado}")
        self.assertEqual(estado, 200)

    @caso('RF-015', 'Validar que no se registre un usuario sin roles.',
          'Registro sin seleccionar roles', 'Selecciona al menos un rol para el usuario.')
    def test_crear_usuario_sin_roles_muestra_mensaje(self):
        self.mensaje_visible(self.post_usuario([]), "Selecciona al menos un rol para el usuario.")


class GestionRolesT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        self.gerente = self.crear_usuario(username="gerente-roles-t61", roles=[self.gerente_rol])
        self.client.force_login(self.gerente)

    @caso('RF-014', 'Validar la creación de un rol nuevo.', "nombre del rol: 'Supervisor'", 'El rol Supervisor existe')
    def test_crear_rol(self):
        self.client.post(reverse("rol_crear"), {"name": "Supervisor", "permissions": []})
        existe = Group.objects.filter(name="Supervisor").exists()
        self.obtenido(f"Rol creado: {existe}")
        self.assertTrue(existe)

    @caso('RF-017', 'Validar que la creación de un rol quede en la auditoría.',
          "nombre del rol: 'Supervisor'", "Registro CREAR 'Creó el rol Supervisor'")
    def test_crear_rol_registra_auditoria(self):
        self.client.post(reverse("rol_crear"), {"name": "Supervisor", "permissions": []})
        existe = Auditoria.objects.filter(usuario=self.gerente, accion=Auditoria.Accion.CREAR, detalle="Creó el rol Supervisor").exists()
        self.obtenido(f"Auditoría registrada: {existe}")
        self.assertTrue(existe)

    @caso('RF-014', 'Validar que no se cree un rol con nombre repetido.', "nombre del rol: 'Vendedor'",
          'Ya existe un rol con ese nombre.')
    def test_crear_rol_duplicado_muestra_mensaje(self):
        respuesta = self.client.post(reverse("rol_crear"), {"name": "Vendedor", "permissions": []})
        self.mensaje_visible(respuesta, "Ya existe un rol con ese nombre.")

    @caso('RF-014', 'Validar la eliminación de un rol sin usuarios.', "rol 'Temporal' sin usuarios", 'El rol deja de existir')
    def test_eliminar_rol_vacio(self):
        rol = Group.objects.create(name="Temporal")
        self.client.post(reverse("rol_eliminar", args=[rol.pk]))
        existe = Group.objects.filter(pk=rol.pk).exists()
        self.obtenido(f"Rol sigue existiendo: {existe}")
        self.assertFalse(existe)

    @caso('RF-017', 'Validar que la eliminación de un rol quede en la auditoría.',
          "rol 'Temporal' eliminado", "Registro ELIMINAR 'Eliminó el rol Temporal'")
    def test_eliminar_rol_vacio_registra_auditoria(self):
        rol = Group.objects.create(name="Temporal")
        self.client.post(reverse("rol_eliminar", args=[rol.pk]))
        existe = Auditoria.objects.filter(usuario=self.gerente, accion=Auditoria.Accion.ELIMINAR, detalle="Eliminó el rol Temporal").exists()
        self.obtenido(f"Auditoría registrada: {existe}")
        self.assertTrue(existe)

    @caso('RF-014', 'Validar que no se pueda eliminar un rol base del sistema.', "eliminar rol 'Vendedor'",
          'No se puede eliminar el rol Vendedor porque es un rol base del sistema.')
    def test_no_elimina_rol_base(self):
        self.client.post(reverse("rol_eliminar", args=[self.vendedor_rol.pk]))
        respuesta = self.client.get(reverse("roles"))
        existe = Group.objects.filter(pk=self.vendedor_rol.pk).exists()
        mensaje = "No se puede eliminar el rol Vendedor porque es un rol base del sistema."
        self.obtenido(f"Mensaje visible: {mensaje in respuesta.content.decode()}; rol conservado: {existe}")
        self.assertContains(respuesta, mensaje)
        self.assertTrue(existe)

    @caso('RF-014', 'Validar que no se pueda eliminar un rol con usuarios asignados.',
          "rol 'Con usuarios' con 1 usuario", 'No se puede eliminar el rol Con usuarios porque tiene 1 usuario(s) asignado(s).')
    def test_no_elimina_rol_con_usuarios_asignados(self):
        rol = Group.objects.create(name="Con usuarios")
        self.crear_usuario(username="asignado-rol-t61", roles=[rol])
        self.client.post(reverse("rol_eliminar", args=[rol.pk]))
        respuesta = self.client.get(reverse("roles"))
        existe = Group.objects.filter(pk=rol.pk).exists()
        mensaje = "No se puede eliminar el rol Con usuarios porque tiene 1 usuario(s) asignado(s)."
        self.obtenido(f"Mensaje visible: {mensaje in respuesta.content.decode()}; rol conservado: {existe}")
        self.assertContains(respuesta, mensaje)
        self.assertTrue(existe)

    @caso('RNF-003', 'Validar que un Vendedor no pueda crear roles.', "Vendedor envía rol 'Supervisor'", 'HTTP 403')
    def test_vendedor_no_puede_crear_roles(self):
        self.client.force_login(self.crear_usuario(username="vendedor-roles-t61", roles=[self.vendedor_rol]))
        estado = self.client.post(reverse("rol_crear"), {"name": "Supervisor", "permissions": []}).status_code
        self.obtenido(f"HTTP {estado}")
        self.assertEqual(estado, 403)

    @caso('RNF-003', 'Validar que un Vendedor no pueda eliminar roles.', 'Vendedor intenta eliminar el rol Gerente', 'HTTP 403')
    def test_vendedor_no_puede_eliminar_roles(self):
        self.client.force_login(self.crear_usuario(username="vendedor-roles-t61", roles=[self.vendedor_rol]))
        estado = self.client.post(reverse("rol_eliminar", args=[self.gerente_rol.pk])).status_code
        self.obtenido(f"HTTP {estado}")
        self.assertEqual(estado, 403)


class FiltrosUsuariosT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        gerente = self.crear_usuario(username="gerente-filtros-t61", roles=[self.gerente_rol])
        self.client.force_login(gerente)
        self.ana = self.crear_usuario(username="AnaFiltro", first_name="Ana Maria", last_name="Lopez", roles=[self.vendedor_rol], estado=Usuario.Estado.ACTIVO)
        self.aux = self.crear_usuario(username="AuxFiltro", first_name="Carlos", last_name="Auxiliar", roles=[self.auxiliar_rol], estado=Usuario.Estado.INACTIVO)
        self.ambos = self.crear_usuario(username="AmbosFiltro", first_name="Ana", last_name="Aux", roles=[self.vendedor_rol, self.auxiliar_rol], estado=Usuario.Estado.INACTIVO)

    def usuarios(self, **filtros):
        respuesta = self.client.get(reverse("usuario_usuarios"), filtros)
        nombres = sorted(u.username for u in respuesta.context["usuarios"])
        self.obtenido(f"Usuarios listados: {nombres}")
        return nombres

    @caso('RF-016', 'Validar el filtro de usuarios por rol.', 'rol: Vendedor', 'AmbosFiltro y AnaFiltro')
    def test_filtro_por_rol(self):
        self.assertEqual(self.usuarios(rol=self.vendedor_rol.pk), ["AmbosFiltro", "AnaFiltro"])

    @caso('RF-016', 'Validar el filtro de usuarios por estado.', 'estado: INACTIVO', 'AmbosFiltro y AuxFiltro')
    def test_filtro_por_estado(self):
        self.assertEqual(self.usuarios(estado=Usuario.Estado.INACTIVO), ["AmbosFiltro", "AuxFiltro"])

    @caso('RF-016', 'Validar el filtro por nombre parcial sin distinguir mayúsculas.', "nombre: 'aNa mA'", 'AnaFiltro')
    def test_filtro_por_nombre_parcial_sin_distinguir_mayusculas(self):
        self.assertEqual(self.usuarios(nombre="aNa mA"), ["AnaFiltro"])

    @caso('RF-016', 'Validar la combinación de filtros de rol, estado y nombre.',
          "rol: Auxiliar; estado: INACTIVO; nombre: 'ana'", 'AmbosFiltro')
    def test_filtros_combinados(self):
        self.assertEqual(self.usuarios(rol=self.auxiliar_rol.pk, estado=Usuario.Estado.INACTIVO, nombre="ana"), ["AmbosFiltro"])

    @caso('RF-016', 'Validar que el filtro de nombre rechace caracteres especiales.', "nombre: '<'",
          'HTTP 200 con: El filtro de nombre contiene caracteres no permitidos.')
    def test_nombre_con_menor_muestra_error_y_responde_200(self):
        respuesta = self.client.get(reverse("usuario_usuarios"), {"nombre": "<"})
        self.mensaje_visible(respuesta, "El filtro de nombre contiene caracteres no permitidos.")
