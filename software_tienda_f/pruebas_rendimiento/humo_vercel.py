import re
from locust import HttpUser, between, task


class HumoAnonimo(HttpUser):
    wait_time = between(1, 2)

    @task
    def login_y_css(self):
        with self.client.get('/login/', name='/login/', catch_response=True) as respuesta:
            coincidencia = re.search(r'<link[^>]+href=["\']([^"\']+\.css(?:\?[^"\']*)?)["\']', respuesta.text, re.IGNORECASE)
            if not coincidencia:
                respuesta.failure('No se encontr? una hoja CSS enlazada desde /login/.')
                return
            self.client.get(coincidencia.group(1), name='/static/[css]')
