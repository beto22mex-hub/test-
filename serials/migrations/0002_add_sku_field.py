# Generated migration for adding SKU field to AuthorizedPart

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('serials', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='authorizedpart',
            name='sku',
            field=models.CharField(default='', help_text='SKU del componente para exportación CSV', max_length=50),
            preserve_default=False,
        ),
    ]
