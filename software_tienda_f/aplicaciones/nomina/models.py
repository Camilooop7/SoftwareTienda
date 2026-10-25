from django.db import models
from django.conf import settings
from django.db.models import Q, F
from django.core.validators import MinValueValidator, MaxValueValidator


class ConfiguracionBonificacion(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bonificacion_config',
    )
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0.01, 'bonificacion_porcentaje_valido'), MaxValueValidator(100, 'bonificacion_porcentaje_valido')])
    meta_mensual = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0.01, 'bonificacion_meta_positiva')])

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(porcentaje__gt=0) & Q(porcentaje__lte=100),
                name='bonificacion_porcentaje_valido',
            ),
            models.CheckConstraint(
                condition=Q(meta_mensual__gt=0),
                name='bonificacion_meta_positiva',
            ),
        ]

    def __str__(self):
        return '{0} - {1}%'.format(self.usuario.username, self.porcentaje)


class HoraExtra(models.Model):
    class Tipo(models.TextChoices):
        DIURNA = 'DIURNA', 'Diurna'
        NOCTURNA = 'NOCTURNA', 'Nocturna'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='horas_extra',
    )
    fecha = models.DateField()
    hora_ingreso = models.TimeField()
    hora_salida = models.TimeField()
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    cantidad_horas = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    valor = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    motivo = models.CharField(max_length=200)
    periodo = models.CharField(max_length=7)  # '2026-09'

    class Meta:
        ordering = ['-fecha']
        constraints = [
            models.CheckConstraint(condition=Q(cantidad_horas__gt=0), name='horaextra_cantidad_positiva'),
            models.CheckConstraint(condition=Q(valor__gte=0), name='horaextra_valor_no_negativo'),
            models.CheckConstraint(condition=Q(hora_salida__gt=F('hora_ingreso')), name='horaextra_salida_posterior'),
        ]


class Solicitud(models.Model):
    class Tipo(models.TextChoices):
        VACACIONES = 'VACACIONES', 'Vacaciones'
        CERTIFICADO = 'CERTIFICADO', 'Certificado'
        NOMINA = 'NOMINA', 'Pre-nómina'

    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        ACEPTADA = 'ACEPTADA', 'Aceptada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='solicitudes',
    )
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    motivo = models.CharField(max_length=200, blank=True)
    fecha_desde = models.DateField(null=True, blank=True)
    fecha_hasta = models.DateField(null=True, blank=True)
    periodo = models.CharField(max_length=7, blank=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    motivo_rechazo = models.CharField(max_length=200, blank=True)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    respondida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_respondidas')

    class Meta:
        ordering = ['-fecha_solicitud']
        constraints = [models.CheckConstraint(
            condition=Q(fecha_desde__isnull=True) | Q(fecha_hasta__isnull=True) | Q(fecha_hasta__gte=F('fecha_desde')),
            name='solicitud_fechas_ordenadas')]


class Nomina(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        ACEPTADA = 'ACEPTADA', 'Aceptada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='nominas',
    )
    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nominas',
    )
    periodo = models.CharField(max_length=7)  # '2026-09'
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nominas_revisadas',
    )
    fecha_revision = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.CharField(max_length=200, blank=True)
    salario_bruto = models.DecimalField(max_digits=14, decimal_places=2)
    valor_bonificacion = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    valor_horas_extra = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deducciones = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    deduccion_salud = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deduccion_pension = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_pagar = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        unique_together = ('usuario', 'periodo')
        ordering = ['-periodo']
        constraints = [
            models.CheckConstraint(condition=Q(salario_bruto__gte=0), name='nomina_salario_no_negativo'),
            models.CheckConstraint(condition=Q(deducciones__gte=0), name='nomina_deducciones_no_negativas'),
            models.CheckConstraint(condition=Q(total_pagar__gte=0), name='nomina_total_no_negativo'),
        ]


