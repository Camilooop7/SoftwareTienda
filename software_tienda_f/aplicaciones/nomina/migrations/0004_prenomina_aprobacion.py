from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_usuario', '0009_alter_auditoria_accion'),
        ('nomina', '0003_delete_notificacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitud',
            name='periodo',
            field=models.CharField(blank=True, max_length=7),
        ),
        migrations.AlterField(
            model_name='solicitud',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('VACACIONES', 'Vacaciones'),
                    ('CERTIFICADO', 'Certificado'),
                    ('NOMINA', 'Pre-nómina'),
                ],
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name='nomina',
            name='revisada_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='nominas_revisadas',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='nomina',
            name='fecha_revision',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nomina',
            name='motivo_rechazo',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
