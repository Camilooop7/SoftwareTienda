from django.db import models
from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):

    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'

    email = models.EmailField(max_length=120,unique=True)
    identificacion = models.PositiveIntegerField(max_length=25, unique=True, null=True, blank=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    fecha_ingreso = models.DateField(null=True, blank=True)
    salario_base = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    def __str__(self):
        return "{0} (ID: {1} - Identificacion: {2} - Estado: {3})".format(self.get_full_name() or self.username,
                                                                          self.pk, self.identificacion, self.estado)

    def obtener_rol(self):
        grupos = self.groups.all()
        return grupos[0].name if grupos else None

    def es_gerente(self):
        return self.groups.filter(name='Gerente').exists()

    def es_auxiliar(self):
        return self.groups.filter(name='Auxiliar Administrativo').exists()

    def es_vendedor(self):
        return self.groups.filter(name='Vendedor').exists()

class Auditoria(models.Model):
    class Accion(models.TextChoices):
        INGRESAR = 'INGRESAR', 'Ingresar'
        CREAR = 'CREAR', 'Crear'
        ACTUALIZAR = 'ACTUALIZAR', 'Actualizar'
        ELIMINAR = 'ELIMINAR', 'Eliminar'
        SALIR = 'SALIR', 'Salir'
        ERROR_ACCESO = 'ERROR_ACCESO', 'Intento fallido de acceso'
        CALCULAR = 'CALCULAR', 'Cálculo de nómina'
        EXPORTAR = 'EXPORTAR', 'Exportar reporte'

    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL,null=True,related_name='auditorias')
    accion = models.CharField(max_length=20, choices=Accion.choices)
    detalle = models.CharField(max_length=255)
    fecha = models.DateField(auto_now_add=True)
    hora = models.TimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Auditoría'
        verbose_name_plural = 'Auditorías'
        ordering = ['-fecha', '-hora']

    def __str__(self):
        return '{0} - {1} ({2})'.format(
            self.usuario, self.get_accion_display(), self.detalle
        )



def descripcion_rol(grupo):
    permisos = grupo.permissions.all()
    codigos = {p.codename for p in permisos}

    if not codigos:
        return 'Sin permisos asignados'
    if 'view_auditoria' in codigos and len(codigos) >= 10:
        return 'Acceso total a todos los módulos'
    if 'add_usuario' in codigos:
        return 'Gestión de usuarios del sistema'
    if 'view_usuario' in codigos:
        return 'Perfil y consulta de información'
    return '{0} permisos asignados'.format(len(codigos))