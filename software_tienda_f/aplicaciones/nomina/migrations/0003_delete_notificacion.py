from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nomina', '0002_nomina_estado_salud_pension'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Notificacion',
        ),
    ]
