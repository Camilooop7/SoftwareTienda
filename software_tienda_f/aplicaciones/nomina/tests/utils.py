from django.contrib.auth.models import Group
from aplicaciones.gestion_usuario.models import Usuario


def crear_grupos():
    return {nombre: Group.objects.get_or_create(name=nombre)[0]
            for nombre in ('Gerente', 'Vendedor', 'Auxiliar Administrativo')}


def crear_usuario(username, rol=None, **campos):
    identificacion = campos.pop('identificacion', None)
    if identificacion is None:
        identificacion = 10000 + sum((i + 1) * ord(c) for i, c in enumerate(username)) % 999999
    campos.setdefault('email', '{0}@example.com'.format(username))
    campos.setdefault('password', 'Clave#2026')
    usuario = Usuario.objects.create_user(username=username, identificacion=identificacion, **campos)
    if rol:
        grupo = rol if isinstance(rol, Group) else Group.objects.get_or_create(name=rol)[0]
        usuario.groups.add(grupo)
    return usuario
