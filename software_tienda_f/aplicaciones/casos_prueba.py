"""Metadatos y captura de resultados para el plan académico."""
from functools import wraps
from threading import RLock

_resultados = {}
_lock = RLock()


def caso(rf, descripcion, entrada, esperado, observacion=None, observacion_estado=False):
    def decorar(funcion):
        @wraps(funcion)
        def ejecuta(self, *args, **kwargs):
            ultimo = []
            nombres = ('assertEqual', 'assertNotEqual', 'assertTrue', 'assertFalse',
                       'assertIn', 'assertNotIn', 'assertContains', 'assertNotContains',
                       'assertRedirects', 'assertTemplateUsed', 'assertRaises')
            originales = {}
            for nombre in nombres:
                original = getattr(self, nombre, None)
                if original is None:
                    continue
                originales[nombre] = original
                def envolver(*a, __original=original, __nombre=nombre, **kw):
                    resultado = __original(*a, **kw)
                    if __nombre in ('assertEqual', 'assertNotEqual') and a:
                        ultimo[:] = [repr(a[0])[:240]]
                    elif __nombre in ('assertContains', 'assertNotContains') and len(a) > 1:
                        ultimo[:] = ['HTTP {0}; contenido validado: {1}'.format(getattr(a[0], 'status_code', '?'), str(a[1])[:200])]
                    elif __nombre == 'assertRedirects' and len(a) > 1:
                        ultimo[:] = ['HTTP {0}; redirección a {1}'.format(getattr(a[0], 'status_code', '?'), a[1])]
                    elif __nombre == 'assertTrue' and a:
                        ultimo[:] = [str(bool(a[0]))]
                    return resultado
                setattr(self, nombre, envolver)
            try:
                resultado = funcion(self, *args, **kwargs)
                if not _resultados.get(self.id()):
                    texto = ultimo[-1] if ultimo else 'La prueba terminó sin error; consulte las aserciones del caso.'
                    self.obtenido(texto)
                return resultado
            finally:
                for nombre, original in originales.items():
                    setattr(self, nombre, original)
        ejecuta._cp_rf = rf
        ejecuta._cp_descripcion = descripcion
        ejecuta._cp_entrada = entrada
        ejecuta._cp_esperado = esperado
        ejecuta._cp_observacion = observacion
        ejecuta._cp_observacion_estado = observacion_estado
        return ejecuta
    return decorar


class CasoPruebaMixin:
    def obtenido(self, texto):
        identificador = self.id()
        with _lock:
            _resultados[identificador] = str(texto)

    @classmethod
    def limpiar_resultados(cls):
        with _lock:
            _resultados.clear()

    @classmethod
    def resultados(cls):
        with _lock:
            return dict(_resultados)

