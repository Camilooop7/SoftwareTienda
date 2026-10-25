from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.pdfgen import canvas
from django.utils import timezone

from .templatetags.formatos import formatear_moneda


NAVY = colors.HexColor('#0F172A')
VIOLET = colors.HexColor('#8B5CF6')
PINK = colors.HexColor('#EC4899')
GRAY = colors.HexColor('#64748B')


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_page_number(self, total):
        self.setFont('Helvetica', 8)
        self.setFillColor(GRAY)
        self.drawRightString(self._pagesize[0] - 1.8 * cm, 0.9 * cm,
                             'Página {0} de {1}'.format(self._pageNumber, total))


def _nombre_usuario(usuario):
    if usuario is None:
        return 'Usuario'
    return usuario.get_full_name() or usuario.username


def generar_pdf_reporte(resumen, generado_por):
    buffer = BytesIO()
    nombre_periodo = resumen['nombre_periodo']
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=1.8 * cm, leftMargin=1.8 * cm,
        topMargin=1.8 * cm, bottomMargin=1.7 * cm,
        title='Reporte de nómina {0}'.format(nombre_periodo),
    )
    estilos = getSampleStyleSheet()
    estilo_marca = ParagraphStyle('Marca', parent=estilos['Normal'], fontName='Helvetica-Bold',
                                  fontSize=9, leading=12, textColor=VIOLET)
    estilo_titulo = ParagraphStyle('TituloReporte', parent=estilos['Title'], fontName='Helvetica-Bold',
                                   fontSize=21, leading=25, alignment=TA_LEFT,
                                   textColor=NAVY, spaceAfter=3)
    estilo_subtitulo = ParagraphStyle('SubtituloReporte', parent=estilos['Normal'],
                                      fontName='Helvetica', fontSize=12, leading=16, textColor=NAVY)
    estilo_meta = ParagraphStyle('MetaReporte', parent=estilos['Normal'],
                                 fontName='Helvetica', fontSize=8.5, leading=12, textColor=GRAY)
    estilo_nota = ParagraphStyle('NotaReporte', parent=estilos['Normal'],
                                 fontName='Helvetica-Oblique', fontSize=9, leading=13, textColor=GRAY)
    estilo_seccion = ParagraphStyle('SeccionReporte', parent=estilos['Heading2'],
                                    fontName='Helvetica-Bold', fontSize=11, leading=14,
                                    textColor=NAVY, spaceBefore=9, spaceAfter=6)
    estilo_detalle = ParagraphStyle('DetalleEmpleado', parent=estilos['Normal'],
                                    fontName='Helvetica', fontSize=7.5, leading=9,
                                    textColor=NAVY, wordWrap='CJK')
    elementos = [
        Paragraph('Sistema Tienda Femenina', estilo_marca),
        Spacer(1, 5),
        Paragraph('Reporte mensual de nómina', estilo_titulo),
        Paragraph(escape(nombre_periodo), estilo_subtitulo),
        Spacer(1, 4),
        Paragraph('Generado el {0} por {1}'.format(
            timezone.now().strftime('%d/%m/%Y %H:%M'),
            escape(_nombre_usuario(generado_por))), estilo_meta),
    ]
    divisor = Table([['']], colWidths=[doc.width], rowHeights=[1.2])
    divisor.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), PINK)]))
    elementos.extend([Spacer(1, 8), divisor, Spacer(1, 9),
                      Paragraph('Incluye únicamente nóminas aceptadas por el administrador.', estilo_nota),
                      Paragraph('RESUMEN', estilo_seccion)])

    resumen_filas = [['Concepto', 'Valor']]
    conceptos = (
        ('Empleados', str(resumen['empleados'])),
        ('Total salarios base', formatear_moneda(resumen['total_salarios'])),
        ('Total bonificaciones', formatear_moneda(resumen['total_bonificaciones'])),
        ('Total horas extra', formatear_moneda(resumen['total_horas_extra'])),
        ('Total devengado', formatear_moneda(resumen['total_devengado'])),
        ('Salud (4%)', formatear_moneda(resumen['total_salud'])),
        ('Pensión (4%)', formatear_moneda(resumen['total_pension'])),
        ('Total deducciones', formatear_moneda(resumen['total_deducciones'])),
        ('TOTAL PAGADO', formatear_moneda(resumen['total_pagado'])),
    )
    resumen_filas.extend([[nombre, valor] for nombre, valor in conceptos])
    tabla_resumen = Table(resumen_filas, colWidths=[doc.width * .69, doc.width * .31], hAlign='LEFT')
    tabla_resumen.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('LEADING', (0, 0), (-1, -1), 11),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]),
        ('GRID', (0, 0), (-1, -2), .35, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0, -1), (-1, -1), VIOLET),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
    ]))
    elementos.extend([tabla_resumen, Paragraph('DETALLE POR EMPLEADO', estilo_seccion)])

    if not resumen['empleados']:
        elementos.append(Paragraph('No hay nóminas aceptadas para {0}.'.format(
            escape(nombre_periodo)), estilos['Normal']))
    else:
        encabezados = ['Empleado', 'Salario base', 'Bonificación', 'Horas extra',
                       'Salud (4%)', 'Pensión (4%)', 'Total pagado']
        filas = [encabezados]
        for nomina in resumen['nominas']:
            usuario = nomina.usuario
            empleado = escape(usuario.get_full_name() or usuario.username)
            filas.append([
                Paragraph(empleado, estilo_detalle),
                formatear_moneda(nomina.salario_bruto),
                formatear_moneda(nomina.valor_bonificacion),
                formatear_moneda(nomina.valor_horas_extra),
                formatear_moneda(nomina.deduccion_salud),
                formatear_moneda(nomina.deduccion_pension),
                formatear_moneda(nomina.total_pagar),
            ])
        filas.append([
            'Totales', formatear_moneda(resumen['total_salarios']),
            formatear_moneda(resumen['total_bonificaciones']),
            formatear_moneda(resumen['total_horas_extra']),
            formatear_moneda(resumen['total_salud']),
            formatear_moneda(resumen['total_pension']),
            formatear_moneda(resumen['total_pagado']),
        ])
        anchos = [doc.width * .27] + [doc.width * .1216666667] * 6
        tabla_detalle = Table(filas, colWidths=anchos, repeatRows=1, hAlign='LEFT')
        tabla_detalle.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (1, 1), (-1, -1), 7),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]),
            ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F1F5F9')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (0, -1), 7),
            ('LINEABOVE', (0, -1), (-1, -1), .8, colors.HexColor('#94A3B8')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        elementos.append(tabla_detalle)

    def pie(pdf_canvas, documento):
        pdf_canvas.saveState()
        pdf_canvas.setFont('Helvetica', 8)
        pdf_canvas.setFillColor(GRAY)
        pdf_canvas.drawString(documento.leftMargin, .9 * cm,
                              'Sistema Tienda Femenina \u00b7 Reporte de n\u00f3mina {0}'.format(nombre_periodo))
        pdf_canvas.restoreState()

    doc.build(elementos, onFirstPage=pie, onLaterPages=pie, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
