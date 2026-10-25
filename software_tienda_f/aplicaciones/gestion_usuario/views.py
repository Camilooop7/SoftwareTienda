from django.conf import settings
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView,
)
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.signals import (
    user_logged_in, user_logged_out, user_login_failed, )
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.models import Group
from django.dispatch import receiver
from .models import Usuario, Auditoria
from .forms import (
    AuditoriaFiltroForm, UsuarioCrearForm, UsuarioActualizarForm, RolForm,
    PerfilForm, LoginForm, UsuarioFiltroForm, CambiarContrasenaForm,
)


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
    authentication_form = LoginForm


class LogoutView(auth_views.LogoutView):
    next_page = 'login'


class PerfilActualView(LoginRequiredMixin, TemplateView):
    template_name = 'usuario_perfil.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario'] = self.request.user
        return context


class PerfilEditarView(LoginRequiredMixin, UpdateView):
    model = Usuario
    form_class = PerfilForm
    template_name = 'perfil_editar.html'
    success_url = reverse_lazy('perfil_actual')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        Auditoria.objects.create(usuario=self.request.user, accion=Auditoria.Accion.ACTUALIZAR,
                                 detalle='Actualizó su perfil')
        messages.success(self.request, 'Tus datos se actualizaron correctamente.')
        return response


class CambiarContrasenaView(LoginRequiredMixin, PasswordChangeView):
    form_class = CambiarContrasenaForm
    template_name = 'cambiar_contrasena.html'
    success_url = reverse_lazy('perfil_actual')

    def form_valid(self, form):
        response = super().form_valid(form)
        update_session_auth_hash(self.request, self.request.user)
        Auditoria.objects.create(usuario=self.request.user, accion=Auditoria.Accion.ACTUALIZAR,
                                 detalle='Cambió su contraseña')
        messages.success(self.request, 'Tu contraseña se actualizó correctamente.')
        return response


class UsuarioListaView(LoginRequiredMixin, SoloGerenteMixin, ListView):
    model = Usuario
    template_name = 'usuario_usuarios.html'
    context_object_name = 'usuarios'

    def get_queryset(self):
        queryset = Usuario.objects.prefetch_related('groups').order_by('last_name', 'first_name')
        self.filtro_form = UsuarioFiltroForm(self.request.GET if self.request.GET else None)
        if self.filtro_form.is_valid():
            datos = self.filtro_form.cleaned_data
            if datos['rol']:
                queryset = queryset.filter(groups=datos['rol'])
            if datos['estado']:
                queryset = queryset.filter(estado=datos['estado'])
            if datos['nombre']:
                from django.db.models import Q
                nombre = datos['nombre']
                queryset = queryset.filter(Q(first_name__icontains=nombre) | Q(last_name__icontains=nombre) | Q(username__icontains=nombre) | Q(email__icontains=nombre))
        elif self.filtro_form.errors:
            messages.error(self.request, next(iter(self.filtro_form.errors.values()))[0])
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtro_form'] = self.filtro_form
        return context


class UsuarioPerfilView(LoginRequiredMixin, DetailView):
    model = Usuario
    template_name = 'usuario_perfil.html'
    context_object_name = 'usuario'


class UsuarioCrearView(LoginRequiredMixin, SoloGerenteMixin, CreateView):
    model = Usuario
    form_class = UsuarioCrearForm
    template_name = 'usuario_actualizar.html'
    success_url = reverse_lazy('usuario_usuarios')

    def form_invalid(self, form):
        messages.error(self.request, 'Revisa los campos marcados en rojo.')
        return super().form_invalid(form)

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

    def form_invalid(self, form):
        messages.error(self.request, 'Revisa los campos marcados en rojo.')
        return super().form_invalid(form)

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
        form = AuditoriaFiltroForm(self.request.GET)
        self.filtro_form = form
        if form.is_valid():
            datos = form.cleaned_data
            if datos['fecha']:
                queryset = queryset.filter(fecha=datos['fecha'])
            if datos['accion']:
                queryset = queryset.filter(accion=datos['accion'])
            if datos['usuario']:
                queryset = queryset.filter(usuario=datos['usuario'])
        else:
            messages.error(self.request, next(iter(form.errors.values()))[0])
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

    def form_invalid(self, form):
        messages.error(self.request, 'Revisa los campos marcados en rojo.')
        return super().form_invalid(form)

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


class RolCrearView(LoginRequiredMixin, SoloGerenteMixin, CreateView):
    model = Group
    form_class = RolForm
    template_name = 'rol_editar.html'
    success_url = reverse_lazy('roles')

    def form_valid(self, form):
        response = super().form_valid(form)
        Auditoria.objects.create(usuario=self.request.user, accion=Auditoria.Accion.CREAR,
                                 detalle='Creó el rol {0}'.format(self.object.name))
        messages.success(self.request, 'Rol "{0}" creado correctamente.'.format(self.object.name))
        return response


class RolEliminarView(LoginRequiredMixin, SoloGerenteMixin, DeleteView):
    model = Group
    template_name = 'rol_eliminar.html'
    success_url = reverse_lazy('roles')
    roles_base = {'Gerente', 'Auxiliar Administrativo', 'Vendedor'}

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        nombre = self.object.name
        cantidad = self.object.user_set.count()
        if nombre in self.roles_base:
            messages.error(request, 'No se puede eliminar el rol {0} porque es un rol base del sistema.'.format(nombre))
            return redirect('roles')
        if cantidad:
            messages.error(request, 'No se puede eliminar el rol {0} porque tiene {1} usuario(s) asignado(s).'.format(nombre, cantidad))
            return redirect('roles')
        response = super().post(request, *args, **kwargs)
        Auditoria.objects.create(usuario=request.user, accion=Auditoria.Accion.ELIMINAR,
                                 detalle='Eliminó el rol {0}'.format(nombre))
        messages.success(request, 'Rol "{0}" eliminado correctamente.'.format(nombre))
        return response


@receiver(user_login_failed)
def auditoria_login_fallido(sender, credentials, request, **kwargs):
    credencial = credentials.get('username') or credentials.get('email') or ''
    Auditoria.objects.create(usuario=None, accion=Auditoria.Accion.ERROR_ACCESO,
                             detalle='Intento fallido de acceso con {0}'.format(credencial)[:255])
