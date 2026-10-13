from django import forms
from django.core.validators import MinValueValidator
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario
from django.contrib.auth.models import Group, Permission
from django.contrib.admin.widgets import FilteredSelectMultiple


class UsuarioCrearForm(UserCreationForm):
    identificacion = forms.IntegerField(
        label='Identificación',
        required=True,
        validators=[
            MinValueValidator(1, message='La identificación no puede ser negativa ni cero.'),
        ],
        widget=forms.NumberInput(attrs={
            'min': 1,
            'inputmode': 'numeric',
            'placeholder': 'Solo números',
        }),
    )

    fecha_ingreso = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True,
        label='Fecha de ingreso',
    )

    class Meta:
        model = Usuario
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'identificacion',
            'fecha_ingreso',
            'estado',
            'groups'
        ]

        labels = {
            'username': 'Nombre de usuario',
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'estado': 'Estado',
            'groups': 'Rol',
        }

        help_texts = {
            'username': ' ',
            'password1': '',
            'groups': '',
        }

        error_messages = {
            'password_mismatch': 'Las dos contraseñas no coinciden.',
        }

        widgets = {
            'estado': forms.Select(choices=Usuario.Estado.choices),
            'groups': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['password1'].label = 'Contraseña'

        self.fields['password2'].label = 'Confirmar contraseña'

        self.fields['password1'].help_text = (
            'Mínimo 8 caracteres, un número y un caracter especial. '
        )

        self.fields['password2'].help_text = (
            'Escribe la misma contraseña para verificar.'
        )

        self.fields['groups'].required = True


class UsuarioActualizarForm(forms.ModelForm):
    identificacion = forms.IntegerField(
        label='Identificación',
        required=True,
        validators=[
            MinValueValidator(1, message='La identificación no puede ser negativa ni cero.'),
        ],
        widget=forms.NumberInput(attrs={
            'min': 1,
            'inputmode': 'numeric',
            'placeholder': 'Solo números'
        }),
    )

    fecha_ingreso = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True,
        label='Fecha de ingreso',
    )

    class Meta:
        model = Usuario
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'identificacion',
            'fecha_ingreso',
            'estado',
            'groups'
        ]

        labels = {
            'username': 'Nombre de usuario',
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'estado': 'Estado',
            'groups': 'Rol',
        }

        help_texts = {
            'username': ' ',
            'password1': '',
            'groups': '',
        }

        widgets = {
            'estado': forms.Select(choices=Usuario.Estado.choices),
            'groups': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['groups'].required = False


class RolForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        label='Permisos',
        widget=FilteredSelectMultiple('permisos', is_stacked=False),
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']

        labels = {
            'name': 'Nombre del rol',
        }