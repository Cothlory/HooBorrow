# Generated by Django 5.1.5 on 2025-04-14 03:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('borrow', '0004_alter_collections_allowed_users'),
    ]

    operations = [
        migrations.AddField(
            model_name='collections',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
