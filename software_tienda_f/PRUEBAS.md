# Pruebas

## Herramientas

Las pruebas unitarias usan `unittest` mediante `django.test.TestCase` y el runner de Django, que integran las transacciones, clientes y base de datos de prueba del proyecto. `coverage.py` mide cobertura de líneas y ramas. Locust permite ejecutar pruebas de carga.

Instala las dependencias de desarrollo con:

```bash
pip install -r requirements-dev.txt
```

Ejecuta las pruebas unitarias con:

```bash
python manage.py test aplicaciones
```

Mide la cobertura con:

```bash
coverage run manage.py test aplicaciones && coverage report && coverage html
```

Django crea automáticamente una base de datos de pruebas (`test_<nombre>`); las pruebas no usan la base de producción. Con Neon, configura el host directo (sin `-pooler`) para ejecutar las pruebas.

## Pruebas de rendimiento

Las pruebas de carga y estrés usan Locust contra un servidor local conectado a una base Neon separada. Consulta [la guía de pruebas de rendimiento](pruebas_rendimiento/README.md).

## Pruebas de integración

`aplicaciones.nomina.tests.test_integracion` recorre los flujos web con sesiones, mensajes y redirecciones: creación de usuarios y novedades antes de calcular y aprobar la pre-nómina; rechazo por falta de motivo, corrección y recálculo; bloqueo de novedades una vez calculado el período; permisos por rol en reportes, novedades, cálculo y bandeja; convivencia de solicitudes de vacaciones con la pre-nómina; y validación de usuario sin guardar datos inválidos.

Ejecuta únicamente estos escenarios con:

```bash
python manage.py test aplicaciones.nomina.tests.test_integracion
```