# Generated by Django 2.0.13 on 2019-05-21 08:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audittrails', '0005_auto_20190520_1450'),
    ]

    operations = [
        migrations.AddField(
            model_name='audittrail',
            name='resource_weergave',
            field=models.URLField(default='', help_text='Vriendelijke identificatie van het object'),
            preserve_default=False,
        ),
    ]
