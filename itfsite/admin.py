from django.contrib import admin
from django import forms
from django.utils.html import escape as escape_html
from itfsite.models import *
from contrib.models import Trigger, TriggerStatus, TriggerCustomization, TextFormat
from letters.models import LettersCampaign, CampaignStatus as LettersCampaignStatus

import json

class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'id', 'is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['id', 'email']

class AnonymousUserAdmin(admin.ModelAdmin):
    list_display = ['email', 'id', 'created', 'confirmed_user']
    search_fields = ['id', 'email', 'confirmed_user__email']

class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['slug', 'orgtype', 'id', 'name', 'created']
    search_fields = ['id', 'slug', 'name']

class TriggersInline(admin.TabularInline):
    model = Campaign.contrib_triggers.through
    extra = 1
    raw_id_fields = ('trigger',)
    verbose_name = 'Trigger'
    show_change_link = True

class LettersInline(admin.TabularInline):
    model = Campaign.letters.through
    extra = 1
    raw_id_fields = ('letterscampaign',)
    verbose_name = 'Letter Campaigns'
    show_change_link = True


class CampaignExtraWidget(forms.Widget):
    # Random things are stored in the 'extra' JSON field.
    fields = [(
            "style.splash.blur",
            "Blur splash image?",
            forms.CheckboxInput(),
            lambda v : True if v else None, # only store True in db
        ),
        (
            "style.splash.invert_text",
            "Invert text color?",
            forms.CheckboxInput(),
            lambda v : True if v else None, # only store True in db
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
        for path, label, widget, infunc in CampaignExtraWidget.fields:
            ret += """<div style="clear: both; padding-top: .5em">
                <label for="id_%s">%s:</label>
            %s</div>""" % (
            escape_html(name) + "_" + path,
            escape_html(label),
            widget.render(name + "_" + path, CampaignExtraWidget.get_dict_value(value, path)),
            )
        ret += """<input type="hidden" name="%s" value="%s">""" % (
            escape_html(name) + "__base", escape_html(json.dumps(value)))
        return ret

    def value_from_datadict(self, data, files, name):
        value = json.loads(data[name + "__base"])
        for path, label, widget, infunc in CampaignExtraWidget.fields:
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
    inlines = [TriggersInline, LettersInline]
    exclude = ['brand', 'contrib_triggers', 'letters']
    prepopulated_fields = {"slug": ("title",)}

admin.site.register(User, UserAdmin)
admin.site.register(AnonymousUser, AnonymousUserAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Campaign, CampaignAdmin)
admin.site.register(Notification) # not really helpful outside of debugging
