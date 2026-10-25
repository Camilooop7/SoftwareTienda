import re
from datetime import date

from django import forms
from .models import HoraExtra, Solicitud, ConfiguracionBonificacion
from ..gestion_usuario.models import Usuario


class ReporteFiltroForm(forms.Form):
    periodo = forms.CharField(
        widget=forms.TextInput(attrs={'type': 'month', 'min': '2020-01'}),
        label='Período',
        error_messages={'required': 'Selecciona un período para generar el reporte.'},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['periodo'].widget.attrs['max'] = date.today().strftime('%Y-%m')

    def clean_periodo(self):
        periodo = self.cleaned_data.get('periodo', '')
        if not periodo:
            raise forms.ValidationError('Selecciona un período para generar el reporte.')
        if not re.fullmatch(r'\d{4}-\d{2}', periodo):
            raise forms.ValidationError('El período debe tener el formato AAAA-MM (ej: 2026-09).')
        ano, mes = (int(parte) for parte in periodo.split('-'))
        if not 1 <= mes <= 12:
            raise forms.ValidationError('El mes debe estar entre 01 y 12.')
        if ano < 2020:
            raise forms.ValidationError('No hay reportes anteriores a enero de 2020.')
        if (ano, mes) > (date.today().year, date.today().month):
            raise forms.ValidationError('No se puede generar el reporte de un mes futuro.')
        return '{0:04d}-{1:02d}'.format(ano, mes)

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
