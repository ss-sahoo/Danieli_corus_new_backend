from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0005_add_scrap_inventory'),
    ]

    operations = [
        migrations.AddField(
            model_name='optimizationhistory',
            name='label',
            field=models.CharField(blank=True, default='', max_length=100, help_text='Custom label for this optimization'),
        ),
        migrations.AddField(
            model_name='optimizationhistory',
            name='label_color',
            field=models.CharField(blank=True, default='green', max_length=20, help_text='Label color'),
        ),
    ]
