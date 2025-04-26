from django.db import migrations, models
import django.utils.timezone

class Migration(migrations.Migration):

    dependencies = [
        ('borrow', '0011_patron_join_date'),  # Replace with your previous migration
    ]

    operations = [
        migrations.AlterField(
            model_name='patron',
            name='join_date',
            field=models.DateField(default=django.utils.timezone.now),
        ),
    ]