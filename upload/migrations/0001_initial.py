from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='UploadLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=255)),
                ('file_type', models.CharField(
                    choices=[('csv', 'CSV'), ('excel', 'Excel'), ('auto', 'Automated Import')],
                    default='csv',
                    max_length=10,
                )),
                ('rows_loaded', models.IntegerField(default=0)),
                ('status', models.CharField(
                    choices=[('success', 'Success'), ('error', 'Error'), ('partial', 'Partial')],
                    default='success',
                    max_length=10,
                )),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'upload_logs',
                'ordering': ['-uploaded_at'],
                'managed': True,
            },
        ),
    ]
