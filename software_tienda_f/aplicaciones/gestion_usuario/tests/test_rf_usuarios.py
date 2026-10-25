from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from aplicaciones.gestion_usuario.forms import PerfilForm
from aplicaciones.gestion_usuario.models import Auditoria, Usuario


class BaseGestionUsuariosT61(TestCase):
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


class LoginT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        self.usuario = self.crear_usuario(username="login-t61", email="login-t61@example.com")

    def test_login_con_correo_en_minusculas_mayusculas_y_usuario(self):
        for credencial in (self.usuario.email, self.usuario.email.upper(), self.usuario.username):
            with self.subTest(credencial=credencial):
                respuesta = self.client.post(reverse("login"), {
                    "username": credencial, "password": "ClaveSegura1",
                })
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta.url, reverse("perfil_actual"))
                self.client.logout()

    def test_contrasena_incorrecta_muestra_mensaje_y_crea_auditoria(self):
        respuesta = self.client.post(reverse("login"), {
            "username": self.usuario.email, "password": "Incorrecta1",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Correo/usuario o contrase\u00f1a incorrectos.")
        self.assertTrue(Auditoria.objects.filter(
            accion=Auditoria.Accion.ERROR_ACCESO,
            detalle__contains=self.usuario.email,
        ).exists())


class CambioContrasenaT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        self.usuario = self.crear_usuario(username="password-t61")
        self.client.force_login(self.usuario)

    def test_cambio_valido_conserva_sesion_y_registra_auditoria(self):
        respuesta = self.client.post(reverse("cambiar_contrasena"), {
            "old_password": "ClaveSegura1",
            "new_password1": "NuevaClave2",
            "new_password2": "NuevaClave2",
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("perfil_actual"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("NuevaClave2"))
        self.assertEqual(self.client.get(reverse("perfil_actual")).status_code, 200)
        self.assertTrue(Auditoria.objects.filter(
            usuario=self.usuario, detalle="Cambi\u00f3 su contrase\u00f1a").exists())

    def test_contrasena_actual_incorrecta_muestra_error(self):
        respuesta = self.client.post(reverse("cambiar_contrasena"), {
            "old_password": "Incorrecta1", "new_password1": "NuevaClave2",
            "new_password2": "NuevaClave2",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Tu contrase\u00f1a actual es incorrecta.")

    def test_nueva_contrasena_sin_mayuscula_muestra_mensaje(self):
        self.assert_error_password("clavesegura2", "La contrase\u00f1a debe contener al menos una letra may\u00fascula.")

    def test_nueva_contrasena_sin_minuscula_muestra_mensaje(self):
        self.assert_error_password("CLAVESEGURA2", "La contrase\u00f1a debe contener al menos una letra min\u00fascula.")

    def test_nueva_contrasena_sin_numero_muestra_mensaje(self):
        self.assert_error_password("ClaveSegura", "La contrase\u00f1a debe contener al menos un n\u00famero.")

    def test_nueva_contrasena_de_siete_caracteres_muestra_mensaje(self):
        self.assert_error_password("Clave12", "La contrase\u00f1a debe tener al menos 8 caracteres.")

    def assert_error_password(self, nueva, mensaje):
        respuesta = self.client.post(reverse("cambiar_contrasena"), {
            "old_password": "ClaveSegura1", "new_password1": nueva,
            "new_password2": nueva,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, mensaje)


class PerfilPropioT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        self.usuario = self.crear_usuario(username="perfil-t61", roles=[self.vendedor_rol])
        self.client.force_login(self.usuario)

    def test_vendedor_actualiza_nombres_y_correo(self):
        respuesta = self.client.post(reverse("perfil_editar"), {
            "first_name": "Nombre Nuevo", "last_name": "Apellido Nuevo",
            "email": "nuevo-perfil@example.com",
        })
        self.assertEqual(respuesta.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, "Nombre Nuevo")
        self.assertEqual(self.usuario.last_name, "Apellido Nuevo")
        self.assertEqual(self.usuario.email, "nuevo-perfil@example.com")

    def test_correo_duplicado_muestra_mensaje(self):
        otro = self.crear_usuario(username="otro-perfil-t61")
        respuesta = self.client.post(reverse("perfil_editar"), {
            "first_name": "Nombre", "last_name": "Apellido", "email": otro.email,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya existe un usuario con ese correo electr\u00f3nico.")

    def test_nombre_con_numeros_muestra_mensaje(self):
        respuesta = self.client.post(reverse("perfil_editar"), {
            "first_name": "Nombre2", "last_name": "Apellido", "email": self.usuario.email,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "El campo nombres solo puede contener letras y espacios.")

    def test_formulario_no_expone_campos_administrativos(self):
        form = PerfilForm(instance=self.usuario)
        for campo in ("salario_base", "groups", "identificacion", "estado"):
            with self.subTest(campo=campo):
                self.assertNotIn(campo, form.fields)


class RolesMultiplesT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        self.gerente = self.crear_usuario(username="gerente-multiples-t61", roles=[self.gerente_rol])
        self.client.force_login(self.gerente)

    def test_crear_usuario_con_dos_roles_y_accede_a_vistas_de_ambos(self):
        respuesta = self.post_usuario([self.vendedor_rol, self.auxiliar_rol])
        self.assertEqual(respuesta.status_code, 302)
        usuario = Usuario.objects.get(username="nuevo-t61")
        self.assertEqual(usuario.obtener_rol(), "Auxiliar Administrativo, Vendedor")
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse("bandeja_aprobacion")).status_code, 200)
        self.assertEqual(self.client.get(reverse("nomina_consultar")).status_code, 200)

    def test_crear_usuario_sin_roles_muestra_mensaje(self):
        respuesta = self.post_usuario([])
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Selecciona al menos un rol para el usuario.")


class GestionRolesT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        self.gerente = self.crear_usuario(username="gerente-roles-t61", roles=[self.gerente_rol])
        self.client.force_login(self.gerente)

    def test_crear_rol_registra_auditoria(self):
        respuesta = self.client.post(reverse("rol_crear"), {"name": "Supervisor", "permissions": []})
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Group.objects.filter(name="Supervisor").exists())
        self.assertTrue(Auditoria.objects.filter(
            usuario=self.gerente, accion=Auditoria.Accion.CREAR,
            detalle="Cre\u00f3 el rol Supervisor").exists())

    def test_crear_rol_duplicado_muestra_mensaje(self):
        respuesta = self.client.post(reverse("rol_crear"), {"name": "Vendedor", "permissions": []})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya existe un rol con ese nombre.")

    def test_eliminar_rol_vacio_registra_auditoria(self):
        rol = Group.objects.create(name="Temporal")
        respuesta = self.client.post(reverse("rol_eliminar", args=[rol.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Group.objects.filter(pk=rol.pk).exists())
        self.assertTrue(Auditoria.objects.filter(
            usuario=self.gerente, accion=Auditoria.Accion.ELIMINAR,
            detalle="Elimin\u00f3 el rol Temporal").exists())

    def test_no_elimina_rol_base(self):
        respuesta = self.client.post(reverse("rol_eliminar", args=[self.vendedor_rol.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertContains(self.client.get(reverse("roles")), "No se puede eliminar el rol Vendedor porque es un rol base del sistema.")
        self.assertTrue(Group.objects.filter(pk=self.vendedor_rol.pk).exists())

    def test_no_elimina_rol_con_usuarios_asignados(self):
        rol = Group.objects.create(name="Con usuarios")
        usuario = self.crear_usuario(username="asignado-rol-t61", roles=[rol])
        respuesta = self.client.post(reverse("rol_eliminar", args=[rol.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertContains(self.client.get(reverse("roles")),
            "No se puede eliminar el rol Con usuarios porque tiene 1 usuario(s) asignado(s).")
        self.assertTrue(Group.objects.filter(pk=rol.pk).exists())
        self.assertTrue(usuario.groups.filter(pk=rol.pk).exists())

    def test_vendedor_no_puede_crear_ni_eliminar_roles(self):
        vendedor = self.crear_usuario(username="vendedor-roles-t61", roles=[self.vendedor_rol])
        self.client.force_login(vendedor)
        crear = self.client.post(reverse("rol_crear"), {"name": "Supervisor", "permissions": []})
        eliminar = self.client.post(reverse("rol_eliminar", args=[self.gerente_rol.pk]))
        self.assertEqual(crear.status_code, 403)
        self.assertEqual(eliminar.status_code, 403)


class FiltrosUsuariosT61Test(BaseGestionUsuariosT61):
    def setUp(self):
        gerente = self.crear_usuario(username="gerente-filtros-t61", roles=[self.gerente_rol])
        self.client.force_login(gerente)
        self.ana = self.crear_usuario(username="AnaFiltro", first_name="Ana Maria", last_name="Lopez", roles=[self.vendedor_rol], estado=Usuario.Estado.ACTIVO)
        self.aux = self.crear_usuario(username="AuxFiltro", first_name="Carlos", last_name="Auxiliar", roles=[self.auxiliar_rol], estado=Usuario.Estado.INACTIVO)
        self.ambos = self.crear_usuario(username="AmbosFiltro", first_name="Ana", last_name="Aux", roles=[self.vendedor_rol, self.auxiliar_rol], estado=Usuario.Estado.INACTIVO)

    def ids(self, **filtros):
        respuesta = self.client.get(reverse("usuario_usuarios"), filtros)
        self.assertEqual(respuesta.status_code, 200)
        return {u.pk for u in respuesta.context["usuarios"]}

    def test_filtro_por_rol(self):
        self.assertEqual(self.ids(rol=self.vendedor_rol.pk), {self.ana.pk, self.ambos.pk})

    def test_filtro_por_estado(self):
        self.assertEqual(self.ids(estado=Usuario.Estado.INACTIVO), {self.aux.pk, self.ambos.pk})

    def test_filtro_por_nombre_parcial_sin_distinguir_mayusculas(self):
        self.assertEqual(self.ids(nombre="aNa mA"), {self.ana.pk})

    def test_filtros_combinados(self):
        self.assertEqual(self.ids(rol=self.auxiliar_rol.pk, estado=Usuario.Estado.INACTIVO, nombre="ana"), {self.ambos.pk})

    def test_nombre_con_menor_muestra_error_y_responde_200(self):
        respuesta = self.client.get(reverse("usuario_usuarios"), {"nombre": "<"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "El filtro de nombre contiene caracteres no permitidos.")
