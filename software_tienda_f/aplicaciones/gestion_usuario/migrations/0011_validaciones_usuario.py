from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
from django.db.models import Q


def corregir_datos(apps, schema_editor):
    Usuario = apps.get_model('gestion_usuario', 'Usuario')
    Usuario.objects.filter(salario_base__lt=0).update(salario_base=0)
    Usuario.objects.filter(
        identificacion__isnull=False, identificacion__lt=10000,
    ).update(identificacion=None)


class Migration(migrations.Migration):
    dependencies = [('gestion_usuario', '0010_usuario_ultimo_pago')]

    operations = [
        migrations.RunPython(corregir_datos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='usuario', name='identificacion',
            field=models.PositiveBigIntegerField(
                blank=True, null=True, unique=True,
                validators=[MinValueValidator(10000), MaxValueValidator(999999999999)],
            ),
        ),
        migrations.AlterField(
            model_name='usuario', name='salario_base',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=14,
                validators=[MinValueValidator(0)],
            ),
        ),
        migrations.AddConstraint(
            model_name='usuario',
            constraint=models.CheckConstraint(
                condition=Q(salario_base__gte=0),
                name='usuario_salario_base_no_negativo',
            ),
        ),
        migrations.AddConstraint(
            model_name='usuario',
            constraint=models.CheckConstraint(
                condition=Q(identificacion__isnull=True) | Q(identificacion__gte=10000),
                name='usuario_identificacion_valida',
            ),
        ),
    ]
