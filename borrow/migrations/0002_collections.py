# Generated by Django 5.1.5 on 2025-03-27 16:40

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('borrow', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Collections',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.CharField(max_length=500)),
                ('is_collection_private', models.BooleanField(default=False)),
                ('allowed_users', models.ManyToManyField(blank=True, help_text='For private collections, only these users (plus librarians) can see and borrow items.', to='borrow.patron')),
                ('creator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='creator', to='borrow.patron')),
                ('items_list', models.ManyToManyField(blank=True, to='borrow.item')),
            ],
        ),
    ]
