import itertools
import os
import re
from datetime import date

from locust import HttpUser, between, task


PASSWORD = os.getenv('CARGA_PASSWORD', '')
CANTIDAD_EMPLEADOS = int(os.getenv('CARGA_EMPLEADOS', '50'))
_CONTADOR_EMPLEADOS = itertools.count(1)


def periodo_anterior():
    hoy = date.today()
    indice = hoy.year * 12 + hoy.month - 2
    return '{0:04d}-{1:02d}'.format(indice // 12, indice % 12 + 1)


def iniciar_sesion(usuario):
    with usuario.client.get('/login/', name='/login/', catch_response=True) as respuesta:
        html = respuesta.text
        coincidencia = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)', html)
        if not coincidencia:
            respuesta.failure('No se encontró csrfmiddlewaretoken en /login/.')
            return
        token = coincidencia.group(1)
    resultado = usuario.client.post(
        '/login/',
        {'username': usuario.username, 'password': PASSWORD, 'csrfmiddlewaretoken': token},
        headers={'Referer': usuario.client.base_url + '/login/'},
        name='/login/ [POST]',
        allow_redirects=False,
    )
    destino = resultado.headers.get('Location', '')
    if resultado.status_code >= 400 or destino.rstrip('/').endswith('/login'):
        resultado.failure('El inicio de sesión de {0} volvió a /login/.'.format(usuario.username))


class UsuarioBase(HttpUser):
    wait_time = between(1, 3)
    username = ''

    def on_start(self):
        iniciar_sesion(self)


class GerenteUser(UsuarioBase):
    weight = 2
    username = 'carga_gerente'

    @task(4)
    def reporte(self):
        self.client.get('/reportes/nomina/?periodo={0}'.format(periodo_anterior()), name='/reportes/nomina/?periodo=[mes]')

    @task(2)
    def pdf(self):
        with self.client.get('/reportes/nomina/pdf/?periodo={0}'.format(periodo_anterior()), name='/reportes/nomina/pdf/?periodo=[mes]', catch_response=True) as respuesta:
            if 'application/pdf' not in respuesta.headers.get('Content-Type', ''):
                respuesta.failure('La descarga no devolvi? application/pdf.')

    @task(2)
    def calculo(self):
        self.client.get('/nomina/calculo/?periodo={0}'.format(periodo_anterior()), name='/nomina/calculo/?periodo=[mes]')

    @task(2)
    def novedades(self):
        self.client.get('/nomina/novedades/', name='/nomina/novedades/')

    @task(1)
    def auditoria(self):
        self.client.get('/auditoria/', name='/auditoria/')


class AuxiliarUser(UsuarioBase):
    weight = 1
    username = 'carga_auxiliar'

    @task(3)
    def bandeja(self):
        self.client.get('/nomina/bandeja/', name='/nomina/bandeja/')

    @task(2)
    def reporte(self):
        self.client.get('/reportes/nomina/?periodo={0}'.format(periodo_anterior()), name='/reportes/nomina/?periodo=[mes]')


class EmpleadoUser(UsuarioBase):
    weight = 7

    def on_start(self):
        self.username = 'carga_emp_{0:03d}'.format((next(_CONTADOR_EMPLEADOS) - 1) % CANTIDAD_EMPLEADOS + 1)
        iniciar_sesion(self)

    @task(4)
    def nomina(self):
        self.client.get('/nomina/?periodo={0}'.format(periodo_anterior()), name='/nomina/?periodo=[mes]')

    @task(2)
    def perfil(self):
        self.client.get('/perfil/', name='/perfil/')

    @task(1)
    def historial(self):
        self.client.get('/nomina/historial/', name='/nomina/historial/')

    @task(1)
    def vacaciones(self):
        self.client.get('/nomina/vacaciones/', name='/nomina/vacaciones/')


if os.getenv('FORMA_CARGA') == 'carga':
    from formas_carga import CargaSostenida
elif os.getenv('FORMA_CARGA') == 'estres':
    from formas_carga import EstresEscalonado
