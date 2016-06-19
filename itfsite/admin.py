from django.contrib import admin
from django import forms
from django.http import HttpResponse
from django.utils.html import escape as escape_html
from itfsite.models import *
from contrib.models import Trigger, TriggerStatus, TriggerCustomization, TextFormat

import json

class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'id', 'is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['id', 'email']

    def get_urls(self):
        # Add a view at /admin/itfsite/user/all-emails.
        from django.conf.urls import  url
        urls = super(UserAdmin, self).get_urls()
        return [
            url(r'^all-emails$', self.admin_site.admin_view(self.dump_user_emails)),
        ] + urls

    def dump_user_emails(self, request):
        # Handle /admin/itfsite/user/all-emails --- dump the email address
        # of each user who has not turned off getting emails from us.
        if not request.user.has_perm('itfsite.see_user_emails'): return HttpResponse("not authorized")
        from itfsite.models import User, NotificationsFrequency
        from contrib.models import ContributorInfo
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["userid", "date_joined", "email", "firstname", "lastname"])
        for user in User.objects\
            .exclude(notifs_freq=NotificationsFrequency.NoNotifications)\
            .order_by('-date_joined'):
            profile = ContributorInfo.objects.filter(pledges__user=user).order_by('-created').first()
            w.writerow([
                user.id,
                user.date_joined,
                user.email,
                profile.extra["contributor"]["contribNameFirst"] if profile else None,
                profile.extra["contributor"]["contribNameLast"] if profile else None
                ])
        return HttpResponse(buf.getvalue(), content_type="text/plain")

class AnonymousUserAdmin(admin.ModelAdmin):
    list_display = ['email', 'id', 'created', 'confirmed_user']
    search_fields = ['id', 'email', 'confirmed_user__email']

class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['slug', 'orgtype', 'id', 'name', 'created']
    search_fields = ['id', 'slug', 'name']
    prepopulated_fields = {"slug": ("name",)}

class TriggersInline(admin.TabularInline):
    model = Campaign.contrib_triggers.through
    extra = 1
    raw_id_fields = ('trigger',)
    verbose_name = 'Trigger'
    show_change_link = True

class CampaignExtraWidget(forms.Widget):
    # Random things are stored in the 'extra' JSON field.
    fields = [
	(
            "style.splash.blur",
            "Blur splash image?",
            forms.CheckboxInput(),
            lambda v : True if v else None, # only store True in db
            None,
        ),
	(
            "style.splash.brightness",
            "Image brightness",
            forms.NumberInput(),
            lambda v : float(v) if (v.strip() != "" and float(v) != 1.0) else None, # only store != 1.0 in db
            "0 is black, 1 is keep unchanged, greater than 1 is lighter",
        ),
        (
            "style.splash.invert_text",
            "Invert text color?",
            forms.CheckboxInput(),
            lambda v : True if v else None, # only store True in db
            None,
        )]

    @staticmethod
    def get_dict_value(value, path):
        for p in path.split("."):
            value = value.get(p) or {}
        return value or None # empty dict, empty string => None

    @staticmethod
    def set_dict_value(value, path, item):
        pp = path.split(".")
        while len(pp) > 1:
            p = pp.pop(0)
            if p not in value or not isinstance(value[p], dict):
                value[p] = { }
            value = value[p]
        value[pp.pop(0)] = item

    def render(self, name, value, attrs=None):
        value = json.loads(value or "{}") or {}
        ret = ""
        for path, label, widget, infunc, help_text in CampaignExtraWidget.fields:
            ret += """<div style="clear: both; padding-top: .5em">
                <label for="id_%s">%s:</label>
            %s
            <div class="help">%s</div></div>""" % (
            escape_html(name) + "_" + path,
            escape_html(label),
            widget.render(name + "_" + path, CampaignExtraWidget.get_dict_value(value, path)),
            escape_html(help_text or ""),
            )
        ret += """<input type="hidden" name="%s" value="%s">""" % (
            escape_html(name) + "__base", escape_html(json.dumps(value)))
        return ret

    def value_from_datadict(self, data, files, name):
        value = json.loads(data[name + "__base"])
        for path, label, widget, infunc, help_text in CampaignExtraWidget.fields:
            CampaignExtraWidget.set_dict_value(value, path, infunc(data.get(name + "_" + path)))
        return json.dumps(value)

class CampaignAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subhead'].widget = forms.Textarea(attrs={ "rows": 3 })
        self.fields['image_credit'].widget = forms.Textarea(attrs={ "rows": 3 })
        self.fields['extra'].widget = CampaignExtraWidget()

class CampaignAdmin(admin.ModelAdmin):
    form = CampaignAdminForm
    list_display = ['slug', 'owner', 'id', 'title', 'created']
    search_fields = ['id', 'slug', 'title', 'owner__name', 'owner__slug']
    raw_id_fields = ['owner']
    inlines = [TriggersInline]
    exclude = ['contrib_triggers']
    prepopulated_fields = {"slug": ("title",)}

admin.site.register(User, UserAdmin)
admin.site.register(AnonymousUser, AnonymousUserAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Campaign, CampaignAdmin)
admin.site.register(Notification) # not really helpful outside of debugging
