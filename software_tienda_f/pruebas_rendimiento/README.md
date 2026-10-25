# Pruebas de rendimiento

## Objetivo

Medir carga sostenida y estrés de Django con Locust. Las pruebas autenticadas se ejecutan únicamente en un servidor local de producción conectado a una base Neon separada cuyo nombre termina en `carga`. Contra Vercel se permite solo el humo anónimo.

## Crear y preparar la base

Crea la base en Neon con el shell Django:

```bash
python manage.py dbshell
CREATE DATABASE carga_neondb;
```

Configura `DATABASE_URL` con la URL directa (sin `-pooler`) de `carga_neondb`. Verifica que su nombre termina en `carga`. Define `CARGA_PASSWORD` y ejecuta:

```bash
python manage.py migrate
python manage.py sembrar_datos_carga --confirmar --empleados 50
```

El sembrado se niega a trabajar con bases cuyo nombre no termine en `carga`.

## Servidor local

Recopila estáticos y levanta Waitress con cookies HTTP habilitadas solo para esta corrida local:

```bash
python manage.py collectstatic --noinput
DEBUG=False COOKIES_SEGURAS=False waitress-serve --listen=127.0.0.1:8000 --threads=8 software_tienda_f.wsgi:application
```

En PowerShell, define `$env:DEBUG='False'` y `$env:COOKIES_SEGURAS='False'` antes de invocar `waitress-serve`.

## Carga y estrés

Desde `software_tienda_f`, instala Locust si hace falta y ejecuta:

```bash
mkdir -p pruebas_rendimiento/resultados
FORMA_CARGA=carga CARGA_PASSWORD='...' CARGA_EMPLEADOS=50 locust -f pruebas_rendimiento/locustfile.py --host http://127.0.0.1:8000 --headless --csv pruebas_rendimiento/resultados/carga --html pruebas_rendimiento/resultados/carga.html
FORMA_CARGA=estres CARGA_PASSWORD='...' CARGA_EMPLEADOS=50 locust -f pruebas_rendimiento/locustfile.py --host http://127.0.0.1:8000 --headless --csv pruebas_rendimiento/resultados/estres --html pruebas_rendimiento/resultados/estres.html
```

Sin `FORMA_CARGA`, Locust usa `-u` y `-r`. `carga` sube a 30 usuarios en 30 segundos y termina a los 3 minutos. `estres` aumenta 20 usuarios cada 45 segundos hasta 200.

Humo anónimo breve contra Vercel:

```bash
locust -f pruebas_rendimiento/humo_vercel.py --host https://TU-APP.vercel.app --headless -u 5 -r 1 -t 1m
```

## Criterios propuestos

- Carga: 0 % de errores y p95 menor de 2000 ms en páginas y 4000 ms en PDF.
- Estrés: identificar concurrencia donde los errores superan 1 % o p95 supera 5 s.

Al terminar, elimina la base de carga desde otra conexión administrativa:

```sql
DROP DATABASE carga_neondb WITH (FORCE);
```

## Hallazgos y optimizaciones

Antes, Django abría una conexión SSL nueva a Neon en cada petición. Después, se usan conexiones persistentes con `CONN_MAX_AGE=60` y health checks. Los resultados comparativos están en `resultados/carga_base_*` y `resultados/carga_optimizada_*`.
