from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_usuario', '0009_alter_auditoria_accion'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='ultimo_periodo_pagado',
            field=models.CharField(blank=True, max_length=7),
        ),
        migrations.AddField(
            model_name='usuario',
            name='ultimo_total_pagado',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
    ]
