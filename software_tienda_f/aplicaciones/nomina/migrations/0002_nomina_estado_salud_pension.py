from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nomina', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='nomina',
            name='estado',
            field=models.CharField(
                choices=[('PENDIENTE', 'Pendiente'), ('ACEPTADA', 'Aceptada'), ('RECHAZADA', 'Rechazada')],
                default='PENDIENTE',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='nomina',
            name='deduccion_salud',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name='nomina',
            name='deduccion_pension',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
    ]
