from django.conf import settings
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView,
)
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.signals import (
    user_logged_in, user_logged_out, )
from django.contrib.auth.models import Group
from django.dispatch import receiver
from .models import Usuario, Auditoria
from .forms import UsuarioCrearForm, UsuarioActualizarForm, RolForm


class SoloGerenteMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if not request.user.groups.filter(name='Gerente').exists():
            raise PermissionDenied('No tienes permisos para esta acción.')
        return super().dispatch(request, *args, **kwargs)


class SoloAuxiliarMixin(LoginRequiredMixin):
    """Auxiliar Administrativo: bandeja de aprobación y nómina."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.groups.filter(name='Auxiliar Administrativo').exists():
            raise PermissionDenied('Solo el Auxiliar Administrativo puede acceder.')
        return super().dispatch(request, *args, **kwargs)


class SoloGerenteOAuxiliarMixin(LoginRequiredMixin):
    """Permite el acceso a reportes al Gerente o al Auxiliar Administrativo."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.groups.filter(
                name__in=['Gerente', 'Auxiliar Administrativo']).exists():
            raise PermissionDenied(
                'Solo el Gerente o el Auxiliar Administrativo pueden ver los reportes.')
        return super().dispatch(request, *args, **kwargs)


class SoloNominaMixin(LoginRequiredMixin):
    """Los tres roles entran a consultar su nómina propia."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.groups.exists():
            raise PermissionDenied('Necesitas un rol asignado para consultar la nómina.')
        return super().dispatch(request, *args, **kwargs)


class LoginView(auth_views.LoginView):
    template_name = 'loggin.html'
    redirect_authenticated_user = True
    next_page = 'perfil_actual'


class LogoutView(auth_views.LogoutView):
    next_page = 'login'


class PerfilActualView(LoginRequiredMixin, TemplateView):
    template_name = 'usuario_perfil.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario'] = self.request.user
        return context


class UsuarioListaView(LoginRequiredMixin, SoloGerenteMixin, ListView):
    model = Usuario
    template_name = 'usuario_usuarios.html'
    context_object_name = 'usuarios'


class UsuarioPerfilView(LoginRequiredMixin, DetailView):
    model = Usuario
    template_name = 'usuario_perfil.html'
    context_object_name = 'usuario'


class UsuarioCrearView(LoginRequiredMixin, SoloGerenteMixin, CreateView):
    model = Usuario
    form_class = UsuarioCrearForm
    template_name = 'usuario_actualizar.html'
    success_url = reverse_lazy('usuario_usuarios')

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        Auditoria.objects.create(
            usuario=self.request.user,
            accion=Auditoria.Accion.CREAR,
            detalle='Creó el usuario {0} (#{1})'.format(
                self.object.get_full_name() or self.object.username, self.object.pk),
        )
        messages.success(self.request, 'Usuario {0} creado correctamente.'.format(self.object.username))
        return respuesta


class UsuarioActualizarView(LoginRequiredMixin, SoloGerenteMixin, UpdateView):
    model = Usuario
    form_class = UsuarioActualizarForm
    template_name = 'usuario_actualizar.html'
    success_url = reverse_lazy('usuario_usuarios')

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        Auditoria.objects.create(
            usuario=self.request.user,
            accion=Auditoria.Accion.ACTUALIZAR,
            detalle='Editó datos de {0}'.format(self.object.username),
        )
        messages.success(self.request, 'Usuario {0} actualizado correctamente.'.format(self.object.username))
        return respuesta


class UsuarioEliminarView(LoginRequiredMixin, SoloGerenteMixin, DeleteView):
    model = Usuario
    template_name = 'usuario_eliminar.html'
    success_url = reverse_lazy('usuario_usuarios')

    def form_valid(self, form):
        nombre = self.object.username
        respuesta = super().form_valid(form)
        Auditoria.objects.create(
            usuario=self.request.user,
            accion=Auditoria.Accion.ELIMINAR,
            detalle='Eliminó a {0}'.format(nombre),
        )
        messages.success(self.request, 'Usuario {0} eliminado correctamente.'.format(nombre))
        return respuesta


@receiver(user_logged_in)
def auditoria_login(sender, request, user, **kwargs):
    Auditoria.objects.create(
        usuario=user,
        accion=Auditoria.Accion.INGRESAR,
        detalle='Inició sesión',
    )


@receiver(user_logged_out)
def auditoria_logout(sender, request, user, **kwargs):
    Auditoria.objects.create(
        usuario=user,
        accion=Auditoria.Accion.SALIR,
        detalle='Cerró sesión',
    )


class AuditoriaListView(LoginRequiredMixin, SoloGerenteMixin, ListView):
    model = Auditoria
    template_name = 'auditoria.html'
    context_object_name = 'registros'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related('usuario')

        fecha = self.request.GET.get('fecha')
        accion = self.request.GET.get('accion')
        usuario_id = self.request.GET.get('usuario')

        if fecha:
            queryset = queryset.filter(fecha=fecha)
        if accion:
            queryset = queryset.filter(accion=accion)
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['acciones'] = Auditoria.Accion.choices
        context['usuarios'] = Usuario.objects.filter(is_active=True).order_by('first_name')
        context['filtros'] = {
            'fecha': self.request.GET.get('fecha', ''),
            'accion': self.request.GET.get('accion', ''),
            'usuario': self.request.GET.get('usuario', ''),
        }
        return context


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


class RolListView(LoginRequiredMixin, SoloGerenteMixin, ListView):
    model = Group
    template_name = 'roles.html'
    context_object_name = 'roles'

    def get_queryset(self):
        return Group.objects.prefetch_related('permissions')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = [
            {'grupo': grupo, 'descripcion': descripcion_rol(grupo)}
            for grupo in self.object_list
        ]
        context['total_usuarios'] = Usuario.objects.filter(groups__isnull=False).distinct().count()
        return context


class RolEditarView(LoginRequiredMixin, SoloGerenteMixin, UpdateView):
    model = Group
    form_class = RolForm
    template_name = 'rol_editar.html'
    success_url = reverse_lazy('roles')

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        Auditoria.objects.create(
            usuario=self.request.user,
            accion=Auditoria.Accion.ACTUALIZAR,
            detalle='Editó el rol {0} (ahora con {1} permisos)'.format(
                self.object.name,
                self.object.permissions.count()),
        )
        messages.success(self.request,
            'Rol "{0}" actualizado correctamente.'.format(self.object.name))
        return respuesta
