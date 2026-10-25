from django.db import migrations, models
import django.db.models.deletion


def vincular_nominas_existentes(apps, schema_editor):
    Solicitud = apps.get_model('nomina', 'Solicitud')
    Nomina = apps.get_model('nomina', 'Nomina')
    estados = {
        'PENDIENTE': 'PENDIENTE',
        'ACEPTADA': 'ACEPTADA',
        'RECHAZADA': 'RECHAZADA',
    }
    for solicitud in Solicitud.objects.filter(tipo='NOMINA').iterator():
        estado_nomina = estados.get(solicitud.estado)
        if estado_nomina:
            Nomina.objects.filter(
                periodo=solicitud.periodo,
                estado=estado_nomina,
                solicitud__isnull=True,
            ).update(solicitud_id=solicitud.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('nomina', '0004_prenomina_aprobacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='nomina',
            name='solicitud',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='nominas',
                to='nomina.solicitud',
            ),
        ),
        migrations.RunPython(vincular_nominas_existentes, migrations.RunPython.noop),
    ]
