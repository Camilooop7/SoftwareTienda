from datetime import date, time, timedelta
from decimal import Decimal
import os

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.utils import timezone

from aplicaciones.gestion_usuario.models import Usuario
from aplicaciones.nomina.excepciones import NominaError
from aplicaciones.nomina.models import ConfiguracionBonificacion
from aplicaciones.nomina.services import aceptar_prenomina, calcular_horas_extra, generar_prenomina


ROLES = ('Gerente', 'Auxiliar Administrativo', 'Vendedor')


class Command(BaseCommand):
    help = 'Crea usuarios y nóminas de prueba en una base de carga separada.'

    def add_arguments(self, parser):
        parser.add_argument('--confirmar', action='store_true')
        parser.add_argument('--empleados', type=int, default=50)

    def handle(self, *args, **options):
        nombre_bd = str(connection.settings_dict.get('NAME', ''))
        if not nombre_bd.lower().endswith('carga'):
            raise CommandError(
                'Este comando solo puede ejecutarse sobre una base de datos de carga '
                '(nombre terminado en "carga"). Base actual: {0}.'.format(nombre_bd)
            )
        if not options['confirmar']:
            raise CommandError('Agrega --confirmar para sembrar datos de carga.')
        password = os.getenv('CARGA_PASSWORD')
        if not password:
            raise CommandError('Define la variable de entorno CARGA_PASSWORD.')
        cantidad = options['empleados']
        if cantidad < 1:
            raise CommandError('--empleados debe ser mayor que cero.')

        with transaction.atomic():
            grupos = {nombre: Group.objects.get_or_create(name=nombre)[0] for nombre in ROLES}
            gerente = self._usuario('carga_gerente', password, grupos['Gerente'], 100000000001)
            auxiliar = self._usuario('carga_auxiliar', password, grupos['Auxiliar Administrativo'], 100000000002)
            empleados = []
            for indice in range(1, cantidad + 1):
                usuario = self._usuario(
                    'carga_emp_{0:03d}'.format(indice), password, grupos['Vendedor'],
                    100000000100 + indice,
                    salario=Decimal(1300000 + ((indice * 7919) % 4700001)),
                )
                empleados.append(usuario)
                if indice % 2 == 0:
                    ConfiguracionBonificacion.objects.get_or_create(
                        usuario=usuario,
                        defaults={'porcentaje': Decimal('5.00'), 'meta_mensual': Decimal('2000000.00')},
                    )
                for meses_atras in (1, 2, 3):
                    fecha = self._fecha_mes_anterior(meses_atras).replace(day=min(indice, 28))
                    if not usuario.horas_extra.filter(fecha=fecha).exists():
                        calcular_horas_extra(usuario, fecha, time(8, 0), time(18, 0), 'Prueba de carga')

            periodos = []
            for meses_atras in (3, 2, 1):
                periodo = self._fecha_mes_anterior(meses_atras).strftime('%Y-%m')
                try:
                    solicitud = generar_prenomina(periodo, gerente)
                    aceptar_prenomina(solicitud, auxiliar)
                except NominaError:
                    pass
                periodos.append(periodo)

        self.stdout.write(self.style.SUCCESS(
            'Carga lista: {0} empleados, usuarios de gerente y auxiliar, períodos {1}.'.format(
                len(empleados), ', '.join(periodos))
        ))

    def _usuario(self, username, password, grupo, identificacion, salario=None):
        numero = username.rsplit('_', 1)[-1]
        defaults = {
            'email': '{0}@carga.invalid'.format(username),
            'first_name': 'Empleado',
            'last_name': 'Carga{0}'.format(numero),
            'identificacion': identificacion,
            'fecha_ingreso': date.today() - timedelta(days=365),
            'salario_base': salario or Decimal('6000000.00'),
            'is_active': True,
        }
        usuario, creado = Usuario.objects.get_or_create(username=username, defaults=defaults)
        if creado:
            usuario.set_password(password)
            usuario.save(update_fields=['password'])
        usuario.groups.add(grupo)
        return usuario

    @staticmethod
    def _fecha_mes_anterior(meses_atras):
        hoy = timezone.localdate()
        indice = hoy.year * 12 + hoy.month - 1 - meses_atras
        return date(indice // 12, indice % 12 + 1, 1)
