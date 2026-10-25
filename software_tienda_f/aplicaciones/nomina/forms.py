import re
from datetime import date, timedelta

from django import forms
from django.utils import timezone

from ..gestion_usuario.models import Usuario
from ..validaciones import (
    normalizar_espacios, validar_fecha_no_futura, validar_texto_seguro,
)
from .models import (
    ConfiguracionBonificacion, HoraExtra, Nomina, Solicitud,
)
from .reportes import nombre_periodo


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
    usuario = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(is_active=True).order_by('first_name'),
        empty_label='- Selecciona un trabajador -', label='Trabajador',
        error_messages={
            'required': 'Selecciona el trabajador.',
            'invalid_choice': 'Selecciona un trabajador válido.'},
    )
    fecha = forms.DateField(
        required=True, widget=forms.DateInput(attrs={'type': 'date'}), label='Fecha',
        error_messages={'required': 'Selecciona la fecha de las horas extra.'})
    hora_ingreso = forms.TimeField(
        required=True, widget=forms.TimeInput(attrs={'type': 'time'}), label='Hora ingreso',
        error_messages={'required': 'Indica la hora de ingreso.'})
    hora_salida = forms.TimeField(
        required=True, widget=forms.TimeInput(attrs={'type': 'time'}), label='Hora salida',
        error_messages={'required': 'Indica la hora de salida.'})
    motivo = forms.CharField(required=True, max_length=200, label='Motivo',
        widget=forms.TextInput(attrs={
            'placeholder': 'Ej: Inventario', 'data-solo': 'texto', 'maxlength': '200',
        }),
        error_messages={'required': 'Escribe el motivo de las horas extra.'})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoy = date.today()
        self.fields['fecha'].widget.attrs.update({
            'max': hoy.isoformat(),
            'min': (hoy - timedelta(days=60)).isoformat(),
        })

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        validar_fecha_no_futura(fecha, 'La fecha de las horas extra')
        if (date.today() - fecha).days > 60:
            raise forms.ValidationError('Solo se pueden registrar horas extra de los últimos 60 días.')
        return fecha

    def clean_motivo(self):
        motivo = normalizar_espacios(self.cleaned_data['motivo'])
        validar_texto_seguro(motivo, 'El motivo')
        if not 5 <= len(motivo) <= 200:
            raise forms.ValidationError('El motivo debe tener entre 5 y 200 caracteres.')
        return motivo

    def clean(self):
        cleaned = super().clean()
        inicio, salida = cleaned.get('hora_ingreso'), cleaned.get('hora_salida')
        if inicio and salida and salida <= inicio:
            self.add_error('hora_salida', 'La hora de salida debe ser posterior a la hora de ingreso.')
        usuario, fecha = cleaned.get('usuario'), cleaned.get('fecha')
        if usuario and fecha:
            if HoraExtra.objects.filter(usuario=usuario, fecha=fecha).exists():
                nombre = usuario.get_full_name() or usuario.username
                mensaje = 'Ya hay horas extra registradas para {0} el {1}.'.format(
                    nombre, fecha.strftime('%d/%m/%Y'))
                self.add_error(None, mensaje)
            nomina = Nomina.objects.filter(
                usuario=usuario, periodo=fecha.strftime('%Y-%m'),
                estado__in=[Nomina.Estado.PENDIENTE, Nomina.Estado.ACEPTADA]).exists()
            if nomina:
                periodo_nombre = nombre_periodo(fecha.strftime('%Y-%m'))
                self.add_error(None, (
                    'La n\u00f3mina de {0} ya fue calculada; no se pueden ' 
                    'registrar m\u00e1s horas extra de ese mes.'
                ).format(periodo_nombre)
                )
        return cleaned


class SolicitudCertificadoForm(forms.ModelForm):
    motivo = forms.CharField(required=True, max_length=200,
        widget=forms.TextInput(attrs={'data-solo': 'texto', 'maxlength': '200'}),
        error_messages={'required': 'Escribe para qu\u00e9 necesitas el certificado.'})

    class Meta:
        model = Solicitud
        fields = ['motivo']

    def clean_motivo(self):
        motivo = normalizar_espacios(self.cleaned_data['motivo'])
        validar_texto_seguro(motivo, 'El motivo')
        if not 5 <= len(motivo) <= 200:
            raise forms.ValidationError('El motivo debe tener entre 5 y 200 caracteres.')
        return motivo


class SolicitudVacacionesForm(forms.ModelForm):
    fecha_desde = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}),
        error_messages={'required': 'Selecciona la fecha de inicio de las vacaciones.'})
    fecha_hasta = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}),
        error_messages={'required': 'Selecciona la fecha de fin de las vacaciones.'})
    motivo = forms.CharField(required=False, max_length=200,
        widget=forms.TextInput(attrs={'data-solo': 'texto', 'maxlength': '200'}))

    class Meta:
        model = Solicitud
        fields = ['motivo', 'fecha_desde', 'fecha_hasta']

    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)
        self.fields['fecha_desde'].widget.attrs['min'] = date.today().isoformat()
        self.fields['fecha_hasta'].widget.attrs['min'] = date.today().isoformat()

    def clean_motivo(self):
        motivo = normalizar_espacios(self.cleaned_data.get('motivo', ''))
        if motivo:
            validar_texto_seguro(motivo, 'El motivo')
            if len(motivo) > 200:
                raise forms.ValidationError('El motivo no puede superar 200 caracteres.')
        return motivo

    def clean(self):
        cleaned = super().clean()
        desde, hasta = cleaned.get('fecha_desde'), cleaned.get('fecha_hasta')
        if desde and desde < timezone.localdate():
            self.add_error('fecha_desde', 'La fecha de inicio no puede ser anterior a hoy.')
        if desde and hasta:
            if hasta < desde:
                self.add_error('fecha_hasta', 'La fecha de fin no puede ser anterior a la fecha de inicio.')
            elif (hasta - desde).days + 1 > 30:
                self.add_error('fecha_hasta', 'Las vacaciones no pueden superar 30 días calendario.')
            elif self.usuario and Solicitud.objects.filter(
                usuario=self.usuario, tipo=Solicitud.Tipo.VACACIONES,
                estado__in=[Solicitud.Estado.PENDIENTE, Solicitud.Estado.ACEPTADA],
                fecha_desde__lte=hasta, fecha_hasta__gte=desde,
            ).exists():
                raise forms.ValidationError(
                    'Ya tienes vacaciones solicitadas o aprobadas que se cruzan ' 
                    'con esas fechas.')
        return cleaned


class SolicitudAprobarForm(forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = ['estado']
        labels = {'estado': 'Estado'}


class BonificacionForm(forms.ModelForm):
    porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, localize=True,
        error_messages={'required': 'Escribe el porcentaje de bonificación.',
            'invalid': 'Escribe un porcentaje válido, por ejemplo 15 o 12,5.',
            'max_decimal_places': 'El porcentaje admite máximo 2 decimales.',
        },
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'data-solo': 'decimal', 'maxlength': '6'}))
    meta_mensual = forms.DecimalField(max_digits=14, decimal_places=2, localize=True,
        error_messages={'required': 'Escribe la meta mensual.',
            'invalid': 'Escribe una meta válida, solo números.',
            'max_decimal_places': 'La meta mensual admite máximo 2 decimales.',
        },
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'data-solo': 'decimal', 'maxlength': '15'}))

    class Meta:
        model = ConfiguracionBonificacion
        fields = ['usuario', 'porcentaje', 'meta_mensual']
        labels = {'usuario': 'Empleado', 'porcentaje': '% Bonificaci\u00f3n', 'meta_mensual': 'Meta mensual'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['usuario'].required = True
        self.fields['usuario'].error_messages['required'] = 'Selecciona el empleado.'
        self.fields['usuario'].empty_label = '- Selecciona un empleado -'
        self.fields['usuario'].queryset = (
            self.fields['usuario'].queryset.filter(is_active=True).order_by('first_name')
        )

    def clean_porcentaje(self):
        valor = self.cleaned_data['porcentaje']
        if valor <= 0 or valor > 100:
            raise forms.ValidationError('El porcentaje debe ser mayor que 0 y máximo 100.')
        return valor

    def clean_meta_mensual(self):
        valor = self.cleaned_data['meta_mensual']
        if valor <= 0:
            raise forms.ValidationError('La meta mensual debe ser mayor que cero.')
        if valor > 999999999:
            raise forms.ValidationError('La meta mensual no puede superar $999.999.999.')
        return valor

    def validate_unique(self):
        pass


class HistorialFiltroForm(forms.Form):
    tipo = forms.ChoiceField(required=False, choices=[('', 'Todos')] + list(Solicitud.Tipo.choices),
        error_messages={'invalid_choice': 'Selecciona un tipo válido.'})
    desde = forms.DateField(required=False, error_messages={'invalid': 'Escribe una fecha válida.'})
    hasta = forms.DateField(required=False, error_messages={'invalid': 'Escribe una fecha válida.'})

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('desde') and cleaned.get('hasta') and cleaned['desde'] > cleaned['hasta']:
            raise forms.ValidationError('La fecha "desde" no puede ser posterior a la fecha "hasta".')
        return cleaned
