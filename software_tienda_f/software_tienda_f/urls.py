"""
URL configuration for software_tienda_f project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from aplicaciones.gestion_usuario.views import *
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', UsuarioListaView.as_view(), name='usuario_usuarios'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('perfil/', PerfilActualView.as_view(), name='perfil_actual'),
    path('gestion_usuario/crear/', UsuarioCrearView.as_view(), name='usuario_crear'),
    path('gestion_usuario/<int:pk>/', UsuarioPerfilView.as_view(), name='usuario_perfil'),
    path('gestion_usuario/<int:pk>/actualizar/', UsuarioActualizarView.as_view(), name='usuario_actualizar'),
    path('gestion_usuario/<int:pk>/eliminar/', UsuarioEliminarView.as_view(), name='usuario_eliminar'),
    path('auditoria/', AuditoriaListView.as_view(), name='auditoria'),
    path('roles/', RolListView.as_view(), name='roles'),
    path('roles/<int:pk>/editar/', RolEditarView.as_view(), name='rol_editar'),


]
