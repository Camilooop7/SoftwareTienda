from django.db import models
from django.conf import settings


class ConfiguracionBonificacion(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bonificacion_config',
    )
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    meta_mensual = models.DecimalField(max_digits=14, decimal_places=2, default=0)

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


class Solicitud(models.Model):
    class Tipo(models.TextChoices):
        VACACIONES = 'VACACIONES', 'Vacaciones'
        CERTIFICADO = 'CERTIFICADO', 'Certificado'

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
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    motivo_rechazo = models.CharField(max_length=200, blank=True)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_solicitud']


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
    periodo = models.CharField(max_length=7)  # '2026-09'
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


