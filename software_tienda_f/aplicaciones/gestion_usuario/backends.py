from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q


class CorreoOUsuarioBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        credencial = username or kwargs.get('email')
        if credencial is None or password is None:
            return None
        UserModel = get_user_model()
        usuario = UserModel._default_manager.filter(
            Q(username__iexact=credencial) | Q(email__iexact=credencial)
        ).first()
        if usuario and usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
