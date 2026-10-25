import calendar
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from aplicaciones.gestion_usuario.models import Auditoria, Usuario
from aplicaciones.nomina.excepciones import NominaError
from aplicaciones.nomina.models import ConfiguracionBonificacion, HoraExtra, Nomina, Solicitud
from aplicaciones.nomina.services import (
    aceptar_prenomina,
    calcular_horas_extra,
    generar_prenomina,
    rechazar_prenomina,
)


ROLES = ('Gerente', 'Auxiliar Administrativo', 'Vendedor')
MOTIVOS_HORAS = (
    'Inventario de fin de mes', 'Temporada de descuentos', 'Cierre de caja',
    'Recepción de mercancía', 'Organización de vitrinas',
)
MOTIVOS_CERTIFICADO = (
    'Trámite bancario', 'Solicitud de crédito de vivienda', 'Proceso de arriendo',
    'Inscripción universitaria', 'Trámite de visa',
)


class Command(BaseCommand):
    help = 'Puebla la aplicación con datos de demostración del último año.'

    def add_arguments(self, parser):
        parser.add_argument('--confirmar', action='store_true')
        parser.add_argument('--password')
        parser.add_argument('--meses', type=int, default=11)

    def handle(self, *args, **options):
        if not options['confirmar']:
            raise CommandError('Agrega --confirmar para poblar los datos de demostración.')
        if not options['password']:
            raise CommandError('Indica la contraseña común con --password.')
        if not 1 <= options['meses'] <= 11:
            raise CommandError('--meses debe estar entre 1 y 11.')

        self.rng = random.Random(2026)
        hoy = timezone.localdate()
        periodos = self._periodos(hoy, options['meses'])
        with transaction.atomic():
            grupos = {nombre: Group.objects.get_or_create(name=nombre)[0] for nombre in ROLES}
            usuarios = self._usuarios(hoy, grupos, options['password'])
            self._bonificaciones(usuarios)
            self._solicitudes_empleados(usuarios, hoy)
            self._auditoria_basica(usuarios, periodos)

        gerente = usuarios[0]
        auxiliar = usuarios[1]
        vendedores = usuarios[3:]
        for indice, periodo in enumerate(periodos):
            anio, mes = map(int, periodo.split('-'))
            inicio = date(anio, mes, 1)
            dia_solicitud = self._aware_datetime(date(anio, mes, 28), time(10))
            revision = self._aware_datetime(self._siguiente_mes(inicio).replace(day=2), time(15))
            with transaction.atomic():
                self._horas_mes(vendedores, inicio)
                antes = Auditoria.objects.order_by('-id').values_list('id', flat=True).first() or 0
                try:
                    solicitud = generar_prenomina(periodo, gerente)
                    if indice == min(4, len(periodos) - 1):
                        rechazar_prenomina(
                            solicitud, auxiliar,
                            'Falta incluir la bonificación de una vendedora',
                        )
                        self._ajustar_bonificacion(vendedores[0])
                        solicitud = generar_prenomina(periodo, gerente)
                    aceptar_prenomina(solicitud, auxiliar)
                    Solicitud.objects.filter(pk=solicitud.pk).update(
                        fecha_solicitud=dia_solicitud, fecha_respuesta=revision,
                        respondida_por=auxiliar)
                    Nomina.objects.filter(solicitud=solicitud).update(
                        fecha_revision=revision)
                except NominaError:
                    pass
                ids = Auditoria.objects.filter(id__gt=antes).values_list('id', flat=True)
                self._fechar_auditoria(ids, revision.date(), revision.time())

        self._resumen()

    @staticmethod
    def _periodos(hoy, cantidad):
        indice = hoy.year * 12 + hoy.month - 1 - 11
        salida = []
        for _ in range(cantidad):
            salida.append('{0:04d}-{1:02d}'.format(indice // 12, indice % 12 + 1))
            indice += 1
        return salida

    @staticmethod
    def _siguiente_mes(fecha):
        indice = fecha.year * 12 + fecha.month
        return date(indice // 12, indice % 12 + 1, 1)

    @staticmethod
    def _aware_datetime(fecha, hora):
        return timezone.make_aware(datetime.combine(fecha, hora), timezone.get_current_timezone())

    def _usuarios(self, hoy, grupos, password):
        especificaciones = [
            ('mgomez', 'Marcela', 'Gómez', 'Gerente', date(2020, 3, 2)),
            ('acastro', 'Andrés', 'Castro', 'Auxiliar Administrativo', date(2021, 6, 14)),
            ('lrojas', 'Lucía', 'Rojas', 'Vendedor', hoy - timedelta(days=420)),
            ('cortiz', 'Camila', 'Ortiz', 'Vendedor', hoy - timedelta(days=400)),
            ('dtorres', 'Daniela', 'Torres', 'Vendedor', hoy - timedelta(days=380)),
            ('emora', 'Elena', 'Mora', 'Vendedor', hoy - timedelta(days=360)),
            ('farias', 'Fernanda', 'Arias', 'Vendedor', hoy - timedelta(days=340)),
            ('gpena', 'Gabriela', 'Peña', 'Vendedor', hoy - timedelta(days=320)),
            ('hruiz', 'Helena', 'Ruiz', 'Vendedor', hoy - timedelta(days=300)),
            ('isoto', 'Isabel', 'Soto', 'Vendedor', hoy - timedelta(days=182)),
            ('jvega', 'Juliana', 'Vega', 'Vendedor', hoy - timedelta(days=91)),
        ]
        demo_preexistente = Usuario.objects.filter(username='mgomez').exists()
        resultado = []
        for i, (username, nombre, apellido, rol, ingreso) in enumerate(especificaciones):
            usuario = Usuario.objects.filter(username=username).first()
            if usuario is None and demo_preexistente:
                continue
            if usuario is None:
                usuario = Usuario.objects.create_user(
                    username=username,
                    email='{0}@tiendafemenina.co'.format(username),
                    first_name=nombre,
                    last_name=apellido,
                    identificacion=12345678 + i * 73129,
                    salario_base=Decimal(self.rng.randrange(1423500, 5500001)),
                    fecha_ingreso=ingreso,
                    estado=Usuario.Estado.ACTIVO,
                    is_active=True,
                    password=None,
                )
                ingreso_local = self._aware_datetime(ingreso, time(0))
                Usuario.objects.filter(pk=usuario.pk).update(date_joined=ingreso_local)
            usuario.groups.set([grupos[rol]])
            if i % 5 == 0:
                usuario.metodo_pago = Usuario.MetodoPago.EFECTIVO
                usuario.banco = ''
                usuario.numero_cuenta = ''
            else:
                usuario.metodo_pago = Usuario.MetodoPago.TRANSFERENCIA
                usuario.banco = ('Banco Andino', 'Banco Nacional', 'Banco Central')[i % 3]
                usuario.numero_cuenta = str(100000000000 + i * 73129)
            usuario.frecuencia_pago = Usuario.FrecuenciaPago.MENSUAL
            usuario.save(update_fields=['metodo_pago', 'banco', 'numero_cuenta', 'frecuencia_pago'])
            resultado.append(usuario)
        if len(resultado) != 11:
            resultado = list(Usuario.objects.filter(username__in=[
                'mgomez', 'acastro', 'lrojas', 'cortiz', 'dtorres', 'emora',
                'farias', 'gpena', 'hruiz', 'isoto', 'jvega',
            ]).order_by('id'))
        for usuario in Usuario.objects.all().iterator():
            usuario.set_password(password)
            usuario.save(update_fields=['password'])
        return resultado

    def _bonificaciones(self, usuarios):
        for usuario in usuarios[1:]:
            ConfiguracionBonificacion.objects.get_or_create(
                usuario=usuario,
                defaults={
                    'porcentaje': Decimal(self.rng.randrange(300, 1501)) / 100,
                    'meta_mensual': Decimal(self.rng.randrange(2000, 15001) * 1000),
                },
            )

    @staticmethod
    def _ajustar_bonificacion(usuario):
        config = ConfiguracionBonificacion.objects.filter(usuario=usuario).first()
        if config:
            config.porcentaje = min(config.porcentaje + Decimal('0.25'), Decimal('15.00'))
            config.save(update_fields=['porcentaje'])

    def _horas_mes(self, vendedores, inicio):
        anio, mes = inicio.year, inicio.month
        limite = calendar.monthrange(anio, mes)[1]
        candidatos = [u for u in vendedores if not u.fecha_ingreso or u.fecha_ingreso <= date(anio, mes, limite)]
        if not candidatos:
            return
        existentes = set(HoraExtra.objects.filter(periodo=inicio.strftime('%Y-%m')).values_list('usuario_id', 'fecha'))
        for i in range(min(self.rng.choice((2, 3)), len(candidatos))):
            usuario = candidatos[(i + (mes % len(candidatos))) % len(candidatos)]
            dias_laborales = [
                dia for dia in range(1, min(25, limite) + 1)
                if date(anio, mes, dia).weekday() < 5
                and (usuario.pk, date(anio, mes, dia)) not in existentes
            ]
            if not dias_laborales:
                continue
            fecha = date(anio, mes, self.rng.choice(dias_laborales))
            existentes.add((usuario.pk, fecha))
            antes = Auditoria.objects.order_by('-id').values_list('id', flat=True).first() or 0
            calcular_horas_extra(
                usuario, fecha, time(self.rng.choice((7, 8)), 0),
                time(self.rng.choice((17, 18, 19, 20)), 30),
                self.rng.choice(MOTIVOS_HORAS),
            )
            ids = Auditoria.objects.filter(id__gt=antes).values_list('id', flat=True)
            self._fechar_auditoria(ids, fecha, time(18))

    @staticmethod
    def _fechar_auditoria(ids, fecha, hora):
        Auditoria.objects.filter(id__in=list(ids)).update(fecha=fecha, hora=hora)

    def _solicitudes_empleados(self, usuarios, hoy):
        fechas = [hoy - timedelta(days=d) for d in (300, 260, 220, 180, 140, 100, 60)]
        for i, usuario in enumerate(usuarios[2:9]):
            inicio = fechas[i]
            fecha = self._aware_datetime(inicio - timedelta(days=8), time(9))
            self._crear_solicitud(usuario, Solicitud.Tipo.VACACIONES,
                                  inicio, inicio + timedelta(days=3 + i),
                                  'Descanso familiar', Solicitud.Estado.ACEPTADA, '', fecha, usuarios[1])
        for i, usuario in enumerate(usuarios[3:10]):
            inicio = hoy + timedelta(days=10 + i * 5) if i >= 4 else fechas[i]
            pendiente = i >= 4
            estado = Solicitud.Estado.PENDIENTE if pendiente else (
                Solicitud.Estado.RECHAZADA if i in (1, 3) else Solicitud.Estado.ACEPTADA)
            rechazo = 'Falta soporte del trámite' if estado == Solicitud.Estado.RECHAZADA else ''
            fecha = self._aware_datetime(inicio - timedelta(days=3), time(11))
            self._crear_solicitud(
                usuario, Solicitud.Tipo.CERTIFICADO, inicio, inicio,
                self.rng.choice(MOTIVOS_CERTIFICADO), estado, rechazo, fecha, usuarios[1],
            )

    @staticmethod
    def _crear_solicitud(usuario, tipo, desde, hasta, motivo, estado, rechazo, fecha, respondida_por):
        existente = Solicitud.objects.filter(
            usuario=usuario, tipo=tipo, fecha_desde=desde, fecha_hasta=hasta,
        ).first()
        if existente:
            if existente.estado != Solicitud.Estado.PENDIENTE:
                Solicitud.objects.filter(pk=existente.pk).update(
                    fecha_solicitud=fecha,
                    fecha_respuesta=fecha + timedelta(days=1),
                    respondida_por=respondida_por,
                )
            return
        solicitud = Solicitud.objects.create(
            usuario=usuario, tipo=tipo, fecha_desde=desde, fecha_hasta=hasta,
            motivo=motivo, estado=estado, motivo_rechazo=rechazo,
            fecha_respuesta=fecha + timedelta(days=1) if estado != Solicitud.Estado.PENDIENTE else None,
            respondida_por=respondida_por if estado != Solicitud.Estado.PENDIENTE else None,
        )
        Solicitud.objects.filter(pk=solicitud.pk).update(fecha_solicitud=fecha)

    def _auditoria_basica(self, usuarios, periodos):
        for i in range(20):
            usuario = usuarios[i % len(usuarios)]
            indice = i % len(periodos)
            anio, mes = map(int, periodos[indice].split('-'))
            fecha = date(anio, mes, min(4 + i, 25))
            registro, creado = Auditoria.objects.get_or_create(
                usuario=usuario,
                accion=Auditoria.Accion.INGRESAR if i % 2 == 0 else Auditoria.Accion.SALIR,
                detalle='Acceso de demostración {0}'.format(i + 1),
            )
            if creado:
                Auditoria.objects.filter(pk=registro.pk).update(
                    fecha=fecha, hora=time(8 + i % 10, 15))

    def _resumen(self):
        conteo_tipo = ', '.join('{0}: {1}'.format(tipo, Solicitud.objects.filter(tipo=tipo).count())
                                for tipo, _ in Solicitud.Tipo.choices)
        conteo_nomina = ', '.join('{0}: {1}'.format(estado, Nomina.objects.filter(estado=estado).count())
                                  for estado, _ in Nomina.Estado.choices)
        self.stdout.write(self.style.SUCCESS(
            'Demo lista — usuarios: {0}; grupos: {1}; bonificaciones: {2}; '
            'horas extra: {3}; solicitudes ({4}); nóminas ({5}); auditoría: {6}.'.format(
                Usuario.objects.count(), Group.objects.count(),
                ConfiguracionBonificacion.objects.count(), HoraExtra.objects.count(),
                conteo_tipo, conteo_nomina, Auditoria.objects.count(),
            )
        ))
