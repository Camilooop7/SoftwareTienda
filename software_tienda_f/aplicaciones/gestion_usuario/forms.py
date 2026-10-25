from datetime import date

from django import forms
from django.contrib.auth.forms import (
    UserCreationForm, AuthenticationForm, PasswordChangeForm,
)
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils import timezone

from aplicaciones.validaciones import (
    normalizar_espacios, validar_fecha_no_futura, validar_solo_digitos,
    validar_solo_letras, validar_usuario,
)
from .models import Usuario, Auditoria
from aplicaciones.validaciones import validar_texto_seguro


class UsuarioValidacionMixin(forms.Form):
    frecuencia_pago = forms.ChoiceField(choices=Usuario.FrecuenciaPago.choices, label='Frecuencia de pago', initial=Usuario.FrecuenciaPago.MENSUAL)
    metodo_pago = forms.ChoiceField(choices=Usuario.MetodoPago.choices, label='Método de pago', initial=Usuario.MetodoPago.TRANSFERENCIA)
    banco = forms.CharField(required=False, max_length=60, label='Banco', widget=forms.TextInput(attrs={'data-solo': 'letras', 'maxlength': '60'}))
    numero_cuenta = forms.CharField(required=False, max_length=20, label='Número de cuenta', widget=forms.TextInput(attrs={'data-solo': 'numeros', 'maxlength': '20', 'inputmode': 'numeric'}))
    email = forms.EmailField(
        required=True,
        error_messages={
            'required': 'Escribe el correo electrónico.',
            'invalid': 'Escribe un correo electrónico válido, por ejemplo '
                       'nombre@dominio.com.',
        },
    )
    identificacion = forms.CharField(
        required=True, max_length=12,
        error_messages={'required': 'Escribe la identificación.',
                        'invalid': 'Escribe una identificación válida.'},
        widget=forms.TextInput(attrs={
            'inputmode': 'numeric', 'data-solo': 'numeros', 'maxlength': '12',
        }),
    )
    fecha_ingreso = forms.DateField(
        required=True, error_messages={
            'required': 'Selecciona la fecha de ingreso.',
            'invalid': 'Escribe una fecha válida.',
        }, widget=forms.DateInput(attrs={'type': 'date'}),
    )
    salario_base = forms.DecimalField(
        required=True, max_digits=14, decimal_places=2, localize=True,
        error_messages={
            'required': 'Escribe el salario base.',
            'invalid': 'Escribe un valor numérico válido.',
            'max_decimal_places': 'El salario base admite máximo 2 decimales.',
        }, widget=forms.TextInput(attrs={
            'min': 0, 'inputmode': 'decimal', 'data-solo': 'decimal',
            'maxlength': '15', 'placeholder': 'Salario base en pesos',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].required = True
        self.fields['username'].error_messages.update({
            'required': 'Escribe el nombre de usuario.',
            'invalid': 'Escribe un nombre de usuario válido.',
        })
        self.fields['first_name'].required = True
        self.fields['first_name'].error_messages['required'] = 'Escribe los nombres.'
        self.fields['last_name'].required = True
        self.fields['last_name'].error_messages['required'] = 'Escribe los apellidos.'
        self.fields['groups'].required = True
        self.fields['groups'].error_messages['required'] = 'Selecciona al menos un rol para el usuario.'
        self.fields['fecha_ingreso'].widget.attrs.update({
            'min': '1950-01-01', 'max': timezone.localdate().isoformat(),
        })

    def clean_username(self):
        valor = normalizar_espacios(self.cleaned_data['username'])
        validar_usuario(valor)
        if not 4 <= len(valor) <= 150:
            raise ValidationError(
                'El nombre de usuario debe tener entre 4 y 150 caracteres.')
        query = Usuario.objects.filter(username__iexact=valor)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise ValidationError('Ya existe un usuario con ese nombre de usuario.')
        return valor

    def _clean_nombre(self, key, campo):
        valor = normalizar_espacios(self.cleaned_data[key])
        validar_solo_letras(valor, campo)
        if not 2 <= len(valor) <= 150:
            titulo = 'Los nombres' if key == 'first_name' else 'Los apellidos'
            raise ValidationError(
                f'{titulo} deben tener entre 2 y 150 caracteres.')
        return valor

    def clean_first_name(self):
        return self._clean_nombre('first_name', 'El campo nombres')

    def clean_last_name(self):
        return self._clean_nombre('last_name', 'El campo apellidos')

    def clean_email(self):
        valor = self.cleaned_data['email'].strip().lower()
        try:
            EmailValidator(message='Escribe un correo electrónico válido, por ejemplo '
                                    'nombre@dominio.com.')(valor)
        except ValidationError:
            raise ValidationError('Escribe un correo electrónico válido, por ejemplo '
                                  'nombre@dominio.com.')
        query = Usuario.objects.filter(email__iexact=valor)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise ValidationError('Ya existe un usuario con ese correo electrónico.')
        return valor

    def clean_identificacion(self):
        valor = self.cleaned_data['identificacion'].strip()
        validar_solo_digitos(valor, 'La identificación')
        if not 5 <= len(valor) <= 12:
            raise ValidationError('La identificación debe tener entre 5 y 12 dígitos.')
        if valor.startswith('0'):
            raise ValidationError('La identificación no puede empezar con cero.')
        query = Usuario.objects.filter(identificacion=int(valor))
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise ValidationError('Ya existe un usuario con esa identificación.')
        return int(valor)

    def clean_fecha_ingreso(self):
        valor = self.cleaned_data['fecha_ingreso']
        validar_fecha_no_futura(valor, 'La fecha de ingreso')
        if valor < date(1950, 1, 1):
            raise ValidationError('La fecha de ingreso no puede ser anterior a 1950.')
        return valor

    def clean_salario_base(self):
        valor = self.cleaned_data['salario_base']
        if valor <= 0:
            raise ValidationError('El salario base debe ser mayor que cero.')
        if valor > 999999999:
            raise ValidationError('El salario base no puede superar $999.999.999.')
        return valor

    def clean_groups(self):
        grupos = self.cleaned_data.get('groups')
        if not grupos:
            raise ValidationError('Selecciona al menos un rol para el usuario.')
        return grupos

    def clean(self):
        cleaned = super().clean()
        metodo = cleaned.get('metodo_pago')
        banco = cleaned.get('banco', '')
        cuenta = cleaned.get('numero_cuenta', '')
        if metodo == Usuario.MetodoPago.TRANSFERENCIA:
            if not banco:
                self.add_error('banco', 'Indica el banco para pagos por transferencia.')
            else:
                banco = normalizar_espacios(banco)
                try:
                    validar_solo_letras(banco, 'El banco')
                    if not 3 <= len(banco) <= 60:
                        raise ValidationError('El banco debe tener entre 3 y 60 caracteres.')
                    cleaned['banco'] = banco
                except ValidationError as error:
                    self.add_error('banco', error)
            if not cuenta:
                self.add_error('numero_cuenta', 'Indica el número de cuenta para pagos por transferencia.')
            else:
                try:
                    validar_solo_digitos(cuenta, 'El número de cuenta')
                    if not 6 <= len(cuenta) <= 20:
                        raise ValidationError('El número de cuenta debe tener entre 6 y 20 dígitos.')
                except ValidationError as error:
                    self.add_error('numero_cuenta', error)
        else:
            cleaned['banco'] = ''
            cleaned['numero_cuenta'] = ''
        return cleaned


class UsuarioCrearForm(UsuarioValidacionMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'identificacion',
                  'fecha_ingreso', 'salario_base', 'frecuencia_pago', 'metodo_pago', 'banco', 'numero_cuenta', 'estado', 'groups']
        labels = {
            'username': 'Nombre de usuario', 'first_name': 'Nombres',
            'last_name': 'Apellidos', 'email': 'Correo electrónico',
            'salario_base': 'Salario base', 'estado': 'Estado', 'groups': 'Rol',
        }
        help_texts = {'username': ' ', 'password1': '', 'groups': ''}
        widgets = {
            'username': forms.TextInput(attrs={'data-solo': 'usuario', 'maxlength': '150'}),
            'first_name': forms.TextInput(attrs={'data-solo': 'letras', 'maxlength': '150'}),
            'last_name': forms.TextInput(attrs={'data-solo': 'letras', 'maxlength': '150'}),
            'estado': forms.Select(choices=Usuario.Estado.choices),
            'groups': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = 'Contraseña'
        self.fields['password2'].label = 'Confirmar contraseña'
        self.fields['password1'].help_text = (
            'Mínimo 8 caracteres con mayúsculas, minúsculas y números.')
        self.fields['password2'].help_text = 'Escribe la misma contraseña para verificar.'


class UsuarioActualizarForm(UsuarioValidacionMixin, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'identificacion',
                  'fecha_ingreso', 'salario_base', 'frecuencia_pago', 'metodo_pago', 'banco', 'numero_cuenta', 'estado', 'groups']
        labels = UsuarioCrearForm.Meta.labels
        help_texts = {'username': ' ', 'groups': ''}
        widgets = UsuarioCrearForm.Meta.widgets


class RolForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all().order_by('content_type__app_label', 'codename'),
        label='Permisos', widget=forms.CheckboxSelectMultiple, required=False,
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']
        widgets = {'name': forms.TextInput(attrs={'data-solo': 'letras', 'maxlength': '150'})}
        labels = {'name': 'Nombre del rol'}
        error_messages = {'name': {'required': 'Escribe el nombre del rol.'}}

    def clean_name(self):
        valor = normalizar_espacios(self.cleaned_data['name'])
        validar_solo_letras(valor, 'El nombre del rol')
        if not 3 <= len(valor) <= 150:
            raise ValidationError('El nombre del rol debe tener entre 3 y 150 caracteres.')
        existentes = Group.objects.filter(name__iexact=valor)
        if self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise ValidationError('Ya existe un rol con ese nombre.')
        return valor


class PerfilForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email']
        labels = {'first_name': 'Nombres', 'last_name': 'Apellidos',
                  'email': 'Correo electrónico'}
        widgets = {
            'first_name': forms.TextInput(attrs={'data-solo': 'letras', 'maxlength': '150'}),
            'last_name': forms.TextInput(attrs={'data-solo': 'letras', 'maxlength': '150'}),
        }

    def clean_first_name(self):
        return UsuarioValidacionMixin._clean_nombre(self, 'first_name', 'El campo nombres')

    def clean_last_name(self):
        return UsuarioValidacionMixin._clean_nombre(self, 'last_name', 'El campo apellidos')

    def clean_email(self):
        valor = self.cleaned_data['email'].strip().lower()
        try:
            EmailValidator()(valor)
        except ValidationError:
            raise ValidationError('Escribe un correo electrónico válido, por ejemplo nombre@dominio.com.')
        if Usuario.objects.filter(email__iexact=valor).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Ya existe un usuario con ese correo electrónico.')
        return valor


class LoginForm(AuthenticationForm):
    error_messages = {'invalid_login': 'Correo/usuario o contraseña incorrectos.'}


class CambiarContrasenaForm(PasswordChangeForm):
    error_messages = {
        **PasswordChangeForm.error_messages,
        'password_incorrect': 'Tu contrase\u00f1a actual es incorrecta.',
        'password_mismatch': 'Las dos contrase\u00f1as nuevas no coinciden.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Contrase\u00f1a actual'
        self.fields['new_password1'].label = 'Nueva contrase\u00f1a'
        self.fields['new_password2'].label = 'Confirmar nueva contrase\u00f1a'


class UsuarioFiltroForm(forms.Form):
    rol = forms.ModelChoiceField(queryset=Group.objects.all().order_by('name'), required=False)
    estado = forms.ChoiceField(choices=[('', 'Todos')] + list(Usuario.Estado.choices), required=False)
    nombre = forms.CharField(required=False)

    def clean_nombre(self):
        valor = normalizar_espacios(self.cleaned_data.get('nombre', ''))
        if valor:
            validar_texto_seguro(valor, 'El filtro de nombre')
        return valor


class AuditoriaFiltroForm(forms.Form):
    fecha = forms.DateField(
        required=False,
        error_messages={'invalid': 'Escribe una fecha v\u00e1lida en el filtro.'},
    )
    accion = forms.ChoiceField(
        required=False,
        error_messages={'invalid_choice': 'Selecciona una acci\u00f3n v\u00e1lida.'},
    )
    usuario = forms.ModelChoiceField(queryset=Usuario.objects.all(), required=False,
        error_messages={'invalid_choice': 'Selecciona un usuario válido.'})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['accion'].choices = [('', 'Todas')] + list(Auditoria.Accion.choices)

    def clean_fecha(self):
        fecha = self.cleaned_data.get('fecha')
        if fecha:
            try:
                validar_fecha_no_futura(fecha, 'La fecha del filtro')
            except ValidationError:
                raise forms.ValidationError('La fecha del filtro no puede ser posterior a hoy.')
        return fecha
