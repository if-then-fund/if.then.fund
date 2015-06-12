# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import itfsite.models
import enum3field


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('itfsite', '0003_organization'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID', auto_created=True)),
                ('notif_type', enum3field.EnumField(itfsite.models.NotificationType, choices=[(itfsite.models.NotificationType(1), 'TriggerRecommendation')], help_text='The type of the notiication.')),
                ('source_object_id', models.PositiveIntegerField(help_text='The primary key of the object generating the notiication.')),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True)),
                ('updated', models.DateTimeField(db_index=True, auto_now=True)),
                ('dismissed_at', models.DateTimeField(help_text='Whether and when the notification was dismissed by the user by.', blank=True, null=True)),
                ('mailed_at', models.DateTimeField(help_text='Whether and when the notification was sent to the user by email.', blank=True, null=True)),
                ('clicked_at', models.DateTimeField(help_text='Whether and when the notification was clicked on by the user to see more information.', blank=True, null=True)),
                ('extra', itfsite.models.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('source_content_type', models.ForeignKey(help_text='The content type of the object generating the notiication.', to='contenttypes.ContentType')),
                ('user', models.ForeignKey(help_text='The user the notification is sent to.', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='notification',
            unique_together=set([('user', 'notif_type', 'source_content_type', 'source_object_id')]),
        ),
        migrations.AlterIndexTogether(
            name='notification',
            index_together=set([('user', 'created')]),
        ),
    ]
