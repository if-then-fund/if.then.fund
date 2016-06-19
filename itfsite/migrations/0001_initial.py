# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import itfsite.models
import enum3field
import django.utils.timezone
import itfsite.utils
import django.db.models.deletion
import itfsite.accounts


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0006_require_contenttypes_0002'),
        ('contrib', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('password', models.CharField(verbose_name='password', max_length=128)),
                ('last_login', models.DateTimeField(verbose_name='last login', blank=True, null=True)),
                ('is_superuser', models.BooleanField(verbose_name='superuser status', default=False, help_text='Designates that this user has all permissions without explicitly assigning them.')),
                ('email', models.EmailField(unique=True, max_length=254)),
                ('is_staff', models.BooleanField(default=False, help_text='Whether the user can log into this admin.')),
                ('is_active', models.BooleanField(default=True, help_text='Unselect this instead of deleting accounts.')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now)),
                ('notifs_freq', enum3field.EnumField(itfsite.accounts.NotificationsFrequency, default=itfsite.accounts.NotificationsFrequency(1), help_text='Now often the user wants to get non-obligatory notifications.', choices=[(itfsite.accounts.NotificationsFrequency(0), 'NoNotifications'), (itfsite.accounts.NotificationsFrequency(1), 'DailyNotifications'), (itfsite.accounts.NotificationsFrequency(2), 'WeeklyNotifications')])),
                ('groups', models.ManyToManyField(related_query_name='user', to='auth.Group', related_name='user_set', verbose_name='groups', help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', blank=True)),
                ('user_permissions', models.ManyToManyField(related_query_name='user', to='auth.Permission', related_name='user_set', verbose_name='user permissions', help_text='Specific permissions for this user.', blank=True)),
            ],
            options={
                'permissions': (('see_user_emails', 'Can see the email addresses of our users'),),
            },
        ),
        migrations.CreateModel(
            name='AnonymousUser',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, db_index=True, blank=True, null=True)),
                ('sentConfirmationEmail', models.BooleanField(default=False, help_text='Have we sent this user an email to confirm their address and activate their account/actions?')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('confirmed_user', models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, help_text='The user that this record became confirmed as.', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Campaign',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('brand', models.IntegerField(default=1, help_text='Which multi-brand site does this campaign appear on.', choices=[(1, 'if.then.fund'), (2, 'progressive.fund'), (99, '279forchange.us')])),
                ('title', models.CharField(help_text='The title for the campaign.', max_length=200)),
                ('slug', models.SlugField(max_length=200, help_text='The URL slug for this campaign.')),
                ('subhead', models.TextField(help_text='Short sub-heading text for use in list pages and the meta description tag, in the format given by subhead_format.')),
                ('subhead_format', enum3field.EnumField(itfsite.utils.TextFormat, default=itfsite.utils.TextFormat(1), help_text='The format of the subhead and image_credit text.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')])),
                ('status', enum3field.EnumField(itfsite.models.CampaignStatus, default=itfsite.models.CampaignStatus(0), help_text='The current status of the campaign.', choices=[(itfsite.models.CampaignStatus(0), 'Draft'), (itfsite.models.CampaignStatus(1), 'Open'), (itfsite.models.CampaignStatus(2), 'Paused'), (itfsite.models.CampaignStatus(3), 'Closed')])),
                ('headline', models.CharField(help_text='Headline text for the page.', max_length=256)),
                ('og_image', models.ImageField(blank=True, help_text="The og:image (for Facebook and Twitter posts) for the campaign. At least 120px x 120px and must be square. If not set and the campaign has an owner, then the owner's og:image is used.", null=True, upload_to='campaign-media')),
                ('splash_image', models.ImageField(blank=True, help_text='The big image to display behind the main call to action. Should be about 1300px wide and at least 500px tall, but the image will be resized and cropped as necessary.', null=True, upload_to='campaign-media')),
                ('image_credit', models.TextField(blank=True, help_text='Image credit, in the same format as the subhead.', null=True)),
                ('body_text', models.TextField(help_text='Body text, in the format given by body_format.')),
                ('body_format', enum3field.EnumField(itfsite.utils.TextFormat, default=itfsite.utils.TextFormat(1), help_text='The format of the body_text field.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')])),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('contrib_triggers', models.ManyToManyField(related_name='campaigns', help_text='Triggers to offer the user to take action on (or to show past actions).', blank=True, to='contrib.Trigger')),
            ],
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('notif_type', enum3field.EnumField(itfsite.models.NotificationType, help_text='The type of the notiication.', choices=[(itfsite.models.NotificationType(1), 'TriggerRecommendation')])),
                ('source_object_id', models.PositiveIntegerField(help_text='The primary key of the object generating the notiication.')),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('dismissed_at', models.DateTimeField(blank=True, help_text='Whether and when the notification was dismissed by the user by.', null=True)),
                ('mailed_at', models.DateTimeField(blank=True, help_text='Whether and when the notification was sent to the user by email.', null=True)),
                ('clicked_at', models.DateTimeField(blank=True, help_text='Whether and when the notification was clicked on by the user to see more information.', null=True)),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
                ('source_content_type', models.ForeignKey(help_text='The content type of the object generating the notiication.', to='contenttypes.ContentType')),
                ('user', models.ForeignKey(help_text='The user the notification is sent to.', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('name', models.CharField(help_text='The name of the Organization.', max_length=200)),
                ('slug', models.SlugField(max_length=200, help_text='The unique URL slug for this Organization.')),
                ('orgtype', enum3field.EnumField(itfsite.models.OrganizationType, help_text='The type of the organization.', choices=[(itfsite.models.OrganizationType(1), 'User'), (itfsite.models.OrganizationType(2), 'C4'), (itfsite.models.OrganizationType(3), 'Company'), (itfsite.models.OrganizationType(4), 'ItfBrand')])),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True, db_index=True)),
                ('description', models.TextField(help_text='Description text in the format given by description_format.')),
                ('description_format', enum3field.EnumField(itfsite.utils.TextFormat, default=itfsite.utils.TextFormat(1), help_text='The format of the description text.', choices=[(itfsite.utils.TextFormat(0), 'HTML'), (itfsite.utils.TextFormat(1), 'Markdown')])),
                ('profile_image', models.ImageField(blank=True, help_text="The logo or headshot to display as the profile picture on the organization's page, and the default og:image (for Facebook and Twitter posts) if og_image is not provided. At least 120px x 120px and must be square.", null=True, upload_to='campaign-media')),
                ('og_image', models.ImageField(blank=True, help_text="The og:image (for Facebook and Twitter posts) for the organization's profile page and the default og:image for the organization's campaigns. At least 120px x 120px and must be square.", null=True, upload_to='campaign-media')),
                ('banner_image', models.ImageField(blank=True, help_text="This organization's banner image. Should be about 1300px wide and at least 500px tall, but the image will be resized and cropped as necessary.", null=True, upload_to='org-banner-image')),
                ('website_url', models.URLField(max_length=256, blank=True, help_text="The URL to this organization's website.", null=True)),
                ('facebook_url', models.URLField(max_length=256, blank=True, help_text="The URL to this organization's Facebook Page.", null=True)),
                ('twitter_handle', models.CharField(max_length=64, blank=True, help_text="The organization's Twitter handle (omit the @-sign).", null=True)),
                ('de_recip_id', models.CharField(max_length=64, blank=True, help_text='The recipient ID on Democracy Engine for taking tips.', null=True)),
                ('extra', itfsite.utils.JSONField(help_text='Additional information stored with this object.', blank=True)),
            ],
        ),
        migrations.AddField(
            model_name='campaign',
            name='owner',
            field=models.ForeignKey(null=True, to='itfsite.Organization', related_name='campaigns', help_text='The user/organization which owns the campaign. Null if the campaign is created by us.', blank=True, on_delete=django.db.models.deletion.PROTECT),
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
