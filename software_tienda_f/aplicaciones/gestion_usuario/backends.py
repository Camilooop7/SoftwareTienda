from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class CorreoOUsuarioBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        credencial = username or kwargs.get('email')
        if credencial is None or password is None:
            return None
        UserModel = get_user_model()
        campo = 'email__iexact' if '@' in credencial else 'username__iexact'
        candidatos = list(UserModel._default_manager.filter(**{campo: credencial})[:2])
        if len(candidatos) != 1:
            UserModel().set_password(password)
            return None
        usuario = candidatos[0]
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
