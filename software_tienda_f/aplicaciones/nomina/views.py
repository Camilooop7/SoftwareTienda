from datetime import date
from decimal import Decimal
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, ListView, FormView, UpdateView, View
from ..gestion_usuario.models import Auditoria, Usuario
from ..gestion_usuario.views import (
    SoloGerenteMixin, SoloAuxiliarMixin, SoloNominaMixin, SoloGerenteOAuxiliarMixin,
)
from .models import Nomina, HoraExtra, Solicitud, ConfiguracionBonificacion, Notificacion
from .forms import HoraExtraForm, SolicitudForm, SolicitudAprobarForm, BonificacionForm, NotificacionForm, \
    SolicitudVacacionesForm
from .forms import ReporteFiltroForm
from .reportes import resumen_mensual
from .services import calcular_horas_extra, calcular_nomina
from .pdf import generar_pdf_reporte


def periodo_actual():
    return date.today().strftime('%Y-%m')


class ReporteMensualView(SoloGerenteOAuxiliarMixin, TemplateView):
    template_name = 'reporte_mensual.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = ReporteFiltroForm(self.request.GET or {'periodo': periodo_actual()})
        if form.is_valid():
            periodo = form.cleaned_data['periodo']
        else:
            periodo = periodo_actual()
            messages.error(self.request, form.errors['periodo'][0])
        context.update({
            'form': form,
            'resumen': resumen_mensual(periodo),
            'periodo': periodo,
        })
        return context


class ReporteMensualPDFView(SoloGerenteOAuxiliarMixin, View):
    def get(self, request, *args, **kwargs):
        form = ReporteFiltroForm(request.GET or {'periodo': periodo_actual()})
        if not form.is_valid():
            messages.error(request, form.errors['periodo'][0])
            return redirect('reporte_mensual')

        periodo = form.cleaned_data['periodo']
        resumen = resumen_mensual(periodo)
        pdf = generar_pdf_reporte(resumen, request.user)
        Auditoria.objects.create(
            usuario=request.user,
            accion=Auditoria.Accion.EXPORTAR,
            detalle='Exportó el reporte de nómina de {0} en PDF'.format(resumen['nombre_periodo']),
        )
        respuesta = HttpResponse(pdf, content_type='application/pdf')
        respuesta['Content-Disposition'] = 'attachment; filename="reporte_nomina_{0}.pdf"'.format(periodo)
        return respuesta


class NominaConsultarView(SoloNominaMixin, TemplateView):
    template_name = 'nomina_consultar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        periodo = self.request.GET.get('periodo', periodo_actual())
        usuario = self.request.user
        nomina = Nomina.objects.filter(usuario=usuario, periodo=periodo).first()

        context.update({
            'nomina': nomina,
            'periodo': periodo,
            'solicitudes': Solicitud.objects.filter(usuario=usuario)[:5],
            'form_solicitud': SolicitudForm(),
            'salario_base': usuario.salario_base,
        })
        return context

    def post(self, request, *args, **kwargs):
        form = SolicitudForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.usuario = request.user
            solicitud.save()
            Auditoria.objects.create(
                usuario=request.user,
                accion=Auditoria.Accion.CREAR,
                detalle='Solicitó {0}'.format(solicitud.get_tipo_display()),
            )
            messages.success(request, 'Solicitud enviada.')
        return redirect('nomina_consultar')


class NominaHistorialView(SoloNominaMixin, ListView):
    template_name = 'nomina_historial.html'
    context_object_name = 'solicitudes'
    paginate_by = 10

    def get_queryset(self):
        qs = Solicitud.objects.filter(usuario=self.request.user)
        tipo = self.request.GET.get('tipo')
        desde = self.request.GET.get('desde')
        hasta = self.request.GET.get('hasta')
        if tipo:
            qs = qs.filter(tipo=tipo)
        if desde:
            qs = qs.filter(fecha_desde__gte=desde)
        if hasta:
            qs = qs.filter(fecha_hasta__lte=hasta)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos'] = Solicitud.Tipo.choices
        context['filtros'] = self.request.GET
        return context


class HorasExtraView( SoloGerenteMixin, FormView):
    template_name = 'horas_extra.html'
    form_class = HoraExtraForm
    success_url = reverse_lazy('horas_extra')

    def form_valid(self, form):
        try:
            extra = calcular_horas_extra(
                usuario=form.cleaned_data['usuario'],
                fecha=form.cleaned_data['fecha'],
                hora_ingreso=form.cleaned_data['hora_ingreso'],
                hora_salida=form.cleaned_data['hora_salida'],
                motivo=form.cleaned_data['motivo'],
            )
            if extra:
                Auditoria.objects.create(
                    usuario=self.request.user,
                    accion=Auditoria.Accion.CREAR,
                    detalle='Registró hora extra {0} de {1}'.format(
                        extra.get_tipo_display(), extra.usuario.username),
                )
                messages.success(self.request,
                    'Registrada: {0} hora(s) {1} — ${2}'.format(
                        extra.cantidad_horas, extra.get_tipo_display(), extra.valor))
            else:
                messages.info(self.request,
                    'No superó la jornada de 8.4 horas: no se registran extras.')
        except ValueError as e:
            messages.error(self.request, str(e))
        return redirect('horas_extra')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['horas'] = HoraExtra.objects.select_related('usuario')[:20]
        return context


class BonificacionesView(SoloGerenteMixin, FormView):
    template_name = 'bonificaciones.html'
    form_class = BonificacionForm
    success_url = reverse_lazy('bonificaciones')

    def form_valid(self, form):
        usuario = form.cleaned_data['usuario']

        config, creado = ConfiguracionBonificacion.objects.update_or_create(
            usuario=usuario,
            defaults={
                'porcentaje': form.cleaned_data['porcentaje'],
                'meta_mensual': form.cleaned_data['meta_mensual'],
            },
        )
        Auditoria.objects.create(
            usuario=self.request.user,
            accion=Auditoria.Accion.ACTUALIZAR,
            detalle='Configuró bonificación de {0} al {1}% (meta ${2})'.format(
                config.usuario.username, config.porcentaje, config.meta_mensual),
        )

        if creado:
            messages.success(self.request,
                'Bonificación creada para {0}: {1}% de ${2}.'.format(
                    usuario.get_full_name() or usuario.username,
                    config.porcentaje, config.meta_mensual))
        else:
            messages.success(self.request,
                'Bonificación de {0} actualizada: {1}% de ${2}.'.format(
                    usuario.get_full_name() or usuario.username,
                    config.porcentaje, config.meta_mensual))
        return redirect('bonificaciones')

    def form_invalid(self, form):
        messages.error(self.request, 'Revisa los datos del formulario.')
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['configs'] = [
            {'config': c,
             'valor': (c.porcentaje / 100 * c.meta_mensual).quantize(Decimal('0'))}
            for c in ConfiguracionBonificacion.objects.select_related('usuario')
        ]
        return context
class CalculoNominaView( SoloGerenteMixin, TemplateView):
    template_name = 'calculo_nomina.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        periodo = self.request.GET.get('periodo', periodo_actual())
        context['periodo'] = periodo
        context['nominas'] = Nomina.objects.filter(periodo=periodo).select_related('usuario')
        return context

    def post(self, request, *args, **kwargs):
        periodo = request.POST.get('periodo', periodo_actual())
        for usuario in Usuario.objects.filter(is_active=True):
            calcular_nomina(usuario, periodo)
        Auditoria.objects.create(
            usuario=request.user,
            accion=Auditoria.Accion.CALCULAR,
            detalle='Calculó la nómina del período {0}'.format(periodo),
        )
        messages.success(request, 'Nómina del período {0} calculada.'.format(periodo))
        return redirect(reverse('calculo_nomina') + '?periodo={0}'.format(periodo))


class VacacionesView(SoloNominaMixin, FormView):
    template_name = 'vacaciones.html'
    form_class = SolicitudVacacionesForm
    success_url = reverse_lazy('vacaciones')

    def get_initial(self):
        return {'tipo': Solicitud.Tipo.VACACIONES}

    def form_valid(self, form):
        solicitud = form.save(commit=False)
        solicitud.usuario = self.request.user
        solicitud.tipo = Solicitud.Tipo.VACACIONES
        solicitud.save()
        Auditoria.objects.create(
            usuario=self.request.user,
            accion=Auditoria.Accion.CREAR,
            detalle='Solicitó vacaciones del {0} al {1}'.format(
                solicitud.fecha_desde, solicitud.fecha_hasta),
        )
        messages.success(self.request, 'Solicitud de vacaciones enviada.')
        return redirect('vacaciones')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['solicitudes'] = Solicitud.objects.filter(
            usuario=self.request.user, tipo=Solicitud.Tipo.VACACIONES)
        return context


class BandejaAprobacionView(SoloAuxiliarMixin, ListView):
    template_name = 'bandeja_aprobacion.html'
    context_object_name = 'solicitudes'

    def get_queryset(self):
        return Solicitud.objects.select_related('usuario').filter(
            estado=Solicitud.Estado.PENDIENTE)

    def post(self, request, *args, **kwargs):
        solicitud = get_object_or_404(
            Solicitud,
            pk=request.POST.get('solicitud_id'),
            estado=Solicitud.Estado.PENDIENTE,
        )

        accion = request.POST.get('accion')
        if accion == 'aprobar':
            solicitud.estado = Solicitud.Estado.ACEPTADA
            mensaje = 'Solicitud de {0} aprobada.'.format(solicitud.usuario.username)
        elif accion == 'rechazar':
            solicitud.estado = Solicitud.Estado.RECHAZADA
            solicitud.motivo_rechazo = request.POST.get('motivo_rechazo') or 'Sin motivo especificado'
            mensaje = 'Solicitud de {0} rechazada.'.format(solicitud.usuario.username)
        else:
            mensaje = 'Acción no válida.'

        solicitud.save()
        Auditoria.objects.create(
            usuario=request.user,
            accion=Auditoria.Accion.ACTUALIZAR,
            detalle='{0} la solicitud de {1} ({2})'.format(
                solicitud.get_estado_display(),
                solicitud.usuario.username,
                solicitud.get_tipo_display()),
        )
        messages.success(request, mensaje)
        return redirect('bandeja_aprobacion')
class NotificacionEditarView( SoloGerenteMixin, UpdateView):
    model = Notificacion
    form_class = NotificacionForm
    template_name = 'notificacion_editar.html'
    success_url = reverse_lazy('perfil_actual')

    def get_object(self, queryset=None):
        notif = Notificacion.objects.first()
        if not notif:
            notif = Notificacion.objects.create(
                titulo='Bienvenidos',
                contenido='',
                actualizada_por=self.request.user,
            )
        return notif

    def form_valid(self, form):
        form.instance.actualizada_por = self.request.user
        messages.success(self.request, 'Notificación actualizada para todos.')
        return super().form_valid(form)
