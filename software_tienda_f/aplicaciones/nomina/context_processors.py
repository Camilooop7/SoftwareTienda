from .models import Notificacion

def notificacion_global(request):
    return {'notificacion_global': Notificacion.objects.filter(activa=True).first()}