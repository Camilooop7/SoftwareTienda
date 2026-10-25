import re
from locust import HttpUser, between, task


class HumoAnonimo(HttpUser):
    wait_time = between(1, 2)

    @task
    def login_y_css(self):
        with self.client.get('/login/', name='/login/', catch_response=True) as respuesta:
            if respuesta.status_code != 200:
                respuesta.failure(f'El login respondió con estado {respuesta.status_code}.')
                return

            coincidencia = re.search(r'<link[^>]+href=["\']([^"\']+\.css(?:\?[^"\']*)?)["\']', respuesta.text, re.IGNORECASE)
            if not coincidencia:
                respuesta.failure('No se encontró una hoja CSS enlazada desde /login/.')
                return

            with self.client.get(coincidencia.group(1), name='/static/[css]', catch_response=True) as respuesta_css:
                if respuesta_css.status_code != 200:
                    respuesta_css.failure(f'El CSS respondió con estado {respuesta_css.status_code}.')
                elif 'text/css' not in respuesta_css.headers.get('Content-Type', '').lower():
                    respuesta_css.failure('El recurso enlazado no es una hoja CSS.')
                else:
                    respuesta_css.success()
