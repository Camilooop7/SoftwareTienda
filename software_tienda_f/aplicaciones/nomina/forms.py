from django import forms
from .models import HoraExtra, Solicitud, ConfiguracionBonificacion, Notificacion
from ..gestion_usuario.models import Usuario

class HoraExtraForm(forms.Form):
    usuario = forms.ModelChoiceField(queryset=Usuario.objects.all(), label='Trabajador')
    fecha = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='Fecha')
    hora_ingreso = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label='Hora ingreso')
    hora_salida = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label='Hora salida')
    motivo = forms.CharField(max_length=200, label='Motivo',
                             widget=forms.TextInput(attrs={'placeholder': 'Ej: Inventario'}))


class SolicitudForm(forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = ['tipo', 'motivo', 'fecha_desde', 'fecha_hasta']
        labels = {
            'tipo': 'Tipo',
            'motivo': 'Motivo',
            'fecha_desde': 'Desde',
            'fecha_hasta': 'Hasta',
        }

        widgets = {
            'fecha_desde': forms.DateInput(attrs={'type': 'date'}),
            'fecha_hasta': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo'].empty_label = None
class SolicitudVacacionesForm(SolicitudForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['tipo']

class SolicitudAprobarForm(forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = ['estado']
        labels = {'estado': 'Estado'}


class BonificacionForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionBonificacion
        fields = ['usuario', 'porcentaje', 'meta_mensual']
        labels = {
            'usuario': 'Empleado',
            'porcentaje': '% Bonificación',
            'meta_mensual': 'Meta mensual',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Select de empleado en español
        self.fields['usuario'].empty_label = '- Selecciona un empleado -'
        self.fields['usuario'].queryset = self.fields['usuario'].queryset.filter(
            is_active=True).order_by('first_name')

    def validate_unique(self):
        pass
class NotificacionForm(forms.ModelForm):
    class Meta:
        model = Notificacion
        fields = ['titulo', 'contenido', 'activa']
        labels = {'titulo': 'Título', 'contenido': 'Contenido', 'activa': 'Mostrar a todos'}