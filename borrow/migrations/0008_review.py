# Generated by Django 5.1.5 on 2025-04-14 15:52

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('borrow', '0007_merge_20250414_0402'),
    ]

    operations = [
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.IntegerField(choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')])),
                ('comment', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='borrow.item')),
                ('reviewer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='borrow.patron')),
            ],
            options={
                'unique_together': {('item', 'reviewer')},
            },
        ),
    ]
