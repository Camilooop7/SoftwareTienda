from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('gestion_usuario', '0011_validaciones_usuario')]
    operations = [
        migrations.AddField('usuario', 'frecuencia_pago', models.CharField(choices=[('MENSUAL', 'Mensual')], default='MENSUAL', max_length=10)),
        migrations.AddField('usuario', 'metodo_pago', models.CharField(choices=[('TRANSFERENCIA', 'Transferencia bancaria'), ('EFECTIVO', 'Efectivo'), ('CHEQUE', 'Cheque')], default='TRANSFERENCIA', max_length=15)),
        migrations.AddField('usuario', 'banco', models.CharField(blank=True, max_length=60)),
        migrations.AddField('usuario', 'numero_cuenta', models.CharField(blank=True, max_length=20)),
    ]
