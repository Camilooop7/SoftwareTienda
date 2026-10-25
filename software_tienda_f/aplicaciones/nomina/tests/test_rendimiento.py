import time
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from aplicaciones.casos_prueba import CasoPruebaMixin, caso
from aplicaciones.gestion_usuario.models import Auditoria, Usuario
from aplicaciones.nomina.models import Nomina, Solicitud
from aplicaciones.nomina.services import generar_prenomina


class RendimientoNominaTest(CasoPruebaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gerente_rol, _ = Group.objects.get_or_create(name='Gerente')
        cls.gerente = Usuario.objects.create_user(username='perf-gerente', email='perf@example.com',
            password='ClaveSegura1', identificacion=99000001, first_name='Perf', last_name='Gerente')
        cls.gerente.groups.add(cls.gerente_rol)

    def crear_200(self):
        usuarios = [Usuario(username='vol-{0}'.format(i), email='vol{0}@example.com'.format(i),
            password=make_password('ClaveSegura1'), identificacion=98000000+i,
            first_name='Usuario', last_name=str(i), salario_base=Decimal(1000000 + i * 1000),
            fecha_ingreso=date(2020, 1, 1), is_active=True) for i in range(200)]
        Usuario.objects.bulk_create(usuarios)
        return list(Usuario.objects.filter(username__startswith='vol-').order_by('pk'))

    @caso('RNF-006', 'Validar que la pre-nómina de 200 empleados tarde como máximo 60 segundos.',
          '200 usuarios activos con salarios variados; período 2026-09', 'Tiempo <= 60,00 s',
          observacion='Primera ejecución: No aprobado (69,13 s) por 3 consultas por empleado. Defecto corregido: bonificaciones y horas extra se leen en 2 consultas y las nóminas se insertan con bulk_create.')
    def test_generacion_prenomina_200_empleados_hasta_60_segundos(self):
        self.crear_200()
        inicio = time.perf_counter()
        generar_prenomina('2026-09', self.gerente)
        segundos = time.perf_counter() - inicio
        self.obtenido('Tiempo medido: {0:.2f} s para 200 empleados'.format(segundos))
        self.assertLessEqual(segundos, 60)

    @caso('RNF-005', 'Validar que un inicio de sesión válido responda en hasta 2 segundos.',
          'POST login con correo perf@example.com y contraseña ClaveSegura1', 'HTTP 302 en <= 2,00 s')
    def test_login_valido_hasta_2_segundos(self):
        inicio = time.perf_counter()
        respuesta = self.client.post(reverse('login'), {'username':'perf@example.com','password':'ClaveSegura1'})
        segundos = time.perf_counter() - inicio
        self.obtenido('HTTP {0}; tiempo medido: {1:.3f} s'.format(respuesta.status_code, segundos))
        self.assertEqual(respuesta.status_code, 302)
        self.assertLessEqual(segundos, 2)

    @caso('RNF-007', 'Validar que la lista filtrada de usuarios responda en hasta 3 segundos.',
          '200 usuarios; filtro nombre=Usuario', 'HTTP 200 en <= 3,00 s',
          observacion='Primera ejecución: No aprobado (23,03 s) porque cada fila consultaba sus roles (N+1). Defecto corregido: obtener_rol usa los grupos precargados.')
    def test_lista_usuarios_filtrada_hasta_3_segundos(self):
        self.crear_200(); self.client.force_login(self.gerente)
        inicio=time.perf_counter(); respuesta=self.client.get(reverse('usuario_usuarios'), {'nombre':'Usuario'}); segundos=time.perf_counter()-inicio
        self.obtenido('HTTP {0}; tiempo medido: {1:.3f} s'.format(respuesta.status_code, segundos))
        self.assertEqual(respuesta.status_code,200); self.assertLessEqual(segundos,3)

    @caso('RNF-007', 'Validar que el historial filtrado responda en hasta 3 segundos.',
          '200 usuarios; empleado con rol Vendedor; filtro de período 2026-09', 'HTTP 200 en <= 3,00 s',
          observacion='Primera ejecución: HTTP 403 por un error de la prueba (el empleado no tenía rol). Se corrigió la prueba.')
    def test_historial_filtrado_hasta_3_segundos(self):
        usuarios=self.crear_200(); usuarios[0].groups.add(Group.objects.get_or_create(name='Vendedor')[0]); self.client.force_login(usuarios[0])
        inicio=time.perf_counter(); respuesta=self.client.get(reverse('nomina_historial'), {'periodo':'2026-09'}); segundos=time.perf_counter()-inicio
        self.obtenido('HTTP {0}; tiempo medido: {1:.3f} s'.format(respuesta.status_code, segundos))
        self.assertEqual(respuesta.status_code,200); self.assertLessEqual(segundos,3)

    @caso('RNF-007', 'Validar que la auditoría filtrada responda en hasta 3 segundos.',
          '300 registros de auditoría; filtro de acción CREAR', 'HTTP 200 en <= 3,00 s')
    def test_auditoria_filtrada_hasta_3_segundos(self):
        self.client.force_login(self.gerente)
        Auditoria.objects.bulk_create([Auditoria(usuario=self.gerente,accion=Auditoria.Accion.CREAR,detalle='Carga {0}'.format(i)) for i in range(300)])
        inicio=time.perf_counter(); respuesta=self.client.get(reverse('auditoria'), {'accion':'CREAR'}); segundos=time.perf_counter()-inicio
        self.obtenido('HTTP {0}; tiempo medido: {1:.3f} s'.format(respuesta.status_code, segundos))
        self.assertEqual(respuesta.status_code,200); self.assertLessEqual(segundos,3)

    @caso('RNF-001', 'Validar que las contraseñas almacenadas usen algoritmos de hash.',
          'Usuario creado mediante create_user', 'Todas las contraseñas empiezan con prefijo de hash')
    def test_contrasenas_de_usuarios_no_estan_en_texto_plano(self):
        self.assertTrue(all(u.password.startswith(('pbkdf2_', 'argon2', 'bcrypt', 'scrypt')) for u in Usuario.objects.all()))
        self.obtenido('Se encontraron {0} usuarios y todos usan contraseñas con hash.'.format(Usuario.objects.count()))

    @caso('RNF-011', 'Validar rollback si falla el cálculo de un empleado durante la pre-nómina.',
          '200 empleados activos; el cálculo falla en el tercer empleado', 'No quedan nóminas ni solicitud del período')
    def test_generar_prenomina_revierte_todo_ante_error_intermedio(self):
        self.crear_200()
        from aplicaciones.nomina import services
        llamada={'n':0}; original=services.construir_nomina
        def falla_en_tercero(*args,**kwargs):
            llamada['n']+=1
            if llamada['n']==3: raise RuntimeError('Fallo simulado')
            return original(*args,**kwargs)
        with patch('aplicaciones.nomina.services.construir_nomina', side_effect=falla_en_tercero):
            with self.assertRaises(RuntimeError): generar_prenomina('2026-09',self.gerente)
        nominas=Nomina.objects.filter(periodo='2026-09').count(); solicitudes=Solicitud.objects.filter(periodo='2026-09',tipo=Solicitud.Tipo.NOMINA).count()
        self.obtenido('Nóminas restantes: {0}; solicitudes restantes: {1}'.format(nominas,solicitudes))
        self.assertEqual((nominas,solicitudes),(0,0))
