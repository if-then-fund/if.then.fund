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

    def get_urls(self):
        from django.conf.urls import patterns
        urls = super().get_urls()
        return patterns('',
            (r'^new$', self.admin_site.admin_view(self.new_form)),
        ) + urls

    def new_form(self, request):
        # Create a new Campaign.

        from django.http import HttpResponseRedirect
        from django.shortcuts import render
        from django import forms
        from votervoice_sharedquestions import sharedQuestions as votervoice_sharedquestions

        class NewForm(forms.Form):
            brand = forms.TypedChoiceField(coerce=int, choices=settings.BRAND_CHOICES, help_text="Which multi-brand site will this campaign appear on?")
            owner = forms.ModelChoiceField(required=False, queryset=Organization.objects.all(), help_text="The organization that owns this campaign.")

            slug = forms.SlugField(help_text="Forms the URL of the campaign.")
            title = forms.CharField(help_text="Displayed in the browser title, on the homepage, and other places where campaigns are listed.")
            headline = forms.CharField(help_text="Displayed as the big text on the campaign page. Usually the same as or similar to the campaign title.")
            subhead = forms.CharField(widget=forms.Textarea, help_text="Short descriptive text displayed under the title/headline. Use Markdown format.")
            body_text = forms.CharField(widget=forms.Textarea, help_text="Long text explaining the campaign. Use Markdown format.")

            pro_label = forms.CharField(label='Option 1 Label (Pro)', help_text="This is for the Aye/Yea vote, when creating a trigger. e.g. 'Pro-Environment'.")
            pro_object = forms.CharField(label='Option 1 Description', help_text="e.g. 'to defend the environment'")
            con_label = forms.CharField(label='Option 2 Label (Con)', help_text="This is for the No/Nay vote, when creating a trigger. e.g. 'Pro-Environment'")
            con_object = forms.CharField(label='Option 2 Description', help_text="e.g. 'to defend the environment'")
            trigger_type = forms.ChoiceField(required=False, label='Trigger Type', choices=(('', 'No Trigger'), ('x', 'Whichever Chamber Votes First'), ('h', 'House Vote'), ('s', 'Senate Vote')))
            trigger_bill_url = forms.URLField(required=False, label="Create Trigger Using Bill", help_text="To associate the trigger with a bill, paste a link to the GovTrack.us bill page.")
            trigger_vote_url = forms.URLField(required=False, label="Execute Using Vote URL", help_text="If the vote has already occurred, paste a link to the GovTrack.us page with roll call vote details. The trigger will be immediately executed.")
            trigger_desired_outcome = forms.TypedChoiceField(required=False, coerce=int, choices=[(None, "(None)"), (0, "Option 1 (Pro)"), (1, "Option 2 (Con)")], help_text="The desired outcome of the trigger.")

            letters = forms.BooleanField(required=False, label="Send letters?")        
            letter_topic = forms.ChoiceField(required=False, choices=[("", "-----")] + [(x,x) for x in votervoice_sharedquestions['US']['validAnswers']])
            letter_subject = forms.CharField(required=False, min_length=10, help_text="The subject line for letters.")
            letter_body = forms.CharField(widget=forms.Textarea, required=False, min_length=64, help_text="The body text of letters.")
            letters_toggles_on_a_trigger = forms.BooleanField(required=False, label="Message Changes Depending on Position of Target?")        
            pro_letter_subject = forms.CharField(label='Option 1 Subject', required=False, help_text="The subject line for letters sent to targets associated with position 1. Blank to reuse the main subject.")
            pro_letter_body = forms.CharField(label='Option 1 Body', required=False, widget=forms.Textarea, help_text="The body text of letters sent to targets associated with position 1. Blank to reuse the main body.")
            con_letter_subject = forms.CharField(label='Option 2 Subject', required=False, help_text="The subject line for letters sent to targets associated with position 2. Blank to reuse the main subject.")
            con_letter_body = forms.CharField(label='Option 2 Body', required=False, widget=forms.Textarea, help_text="The body text of letters sent to targets associated with position 2. Blank to reuse the main body.")

        if request.method == "POST":
            form = NewForm(request.POST)
            error = None
            if form.is_valid():
                from contrib.legislative import create_trigger_from_bill, create_congressional_vote_trigger, execute_trigger_from_vote
                try:
                    # If any validation fails, don't create the trigger.
                    with transaction.atomic():
                        # Create the campaign.
                        campaign = Campaign()
                        campaign.brand = form.cleaned_data['brand']
                        campaign.title = form.cleaned_data['title']
                        campaign.slug = form.cleaned_data['slug']
                        campaign.subhead = form.cleaned_data['subhead']
                        campaign.subhead_format = TextFormat.Markdown
                        campaign.owner = form.cleaned_data['owner']
                        campaign.headline = form.cleaned_data['headline']
                        campaign.body_text = form.cleaned_data['body_text']
                        campaign.body_format = TextFormat.Markdown
                        campaign.save()

                        trigger = None
                        tcust = None
                        if form.cleaned_data['trigger_type']:
                            # Create trigger.
                            if form.cleaned_data.get('trigger_bill_url'):
                                trigger = create_trigger_from_bill(form.cleaned_data['trigger_bill_url'], form.cleaned_data['trigger_type'])
                            else:
                                trigger = create_congressional_vote_trigger(form.cleaned_data['trigger_type'], form.cleaned_data['title'], "something")

                            trigger.status = TriggerStatus.Open # can't execute while draft, and might as well open it since the campaign will be in draft status anyway

                            # Set outcome strings.
                            for i, outcome in enumerate(trigger.outcomes):
                                outcome['label'] = form.cleaned_data[('pro' if i == 0 else 'con') + '_label']
                                outcome['object'] = form.cleaned_data[('pro' if i == 0 else 'con') + '_object']
                                outcome['tip'] = None
                            trigger.save()
                            campaign.contrib_triggers.add(trigger)

                            # If a vote URL is given, execute the trigger immediately.
                            if form.cleaned_data['trigger_vote_url']:
                                trigger.save()
                                execute_trigger_from_vote(trigger, form.cleaned_data['trigger_vote_url'])

                            # What does the organization want?
                            if form.cleaned_data['trigger_desired_outcome'] != '': # can be zero
                                if not campaign.owner: raise ValueError("Can't have a desired outcome if the campaign has no owner.")
                                tcust = TriggerCustomization()
                                tcust.trigger = trigger
                                tcust.owner = campaign.owner
                                tcust.outcome = form.cleaned_data['trigger_desired_outcome']
                                tcust.save()

                        letters = None
                        letters_toggle_trigger = None
                        if form.cleaned_data['letters']:
                            if not form.cleaned_data['letter_topic']: raise ValueError("letter_topic is required")
                            if not form.cleaned_data['letter_subject']: raise ValueError("letter_subject is required")
                            if not form.cleaned_data['letter_body']: raise ValueError("letter_body is required")
                            letters = LettersCampaign()
                            letters.title = campaign.title
                            letters.status = LettersCampaignStatus.Open
                            letters.owner = campaign.owner
                            letters.topic = form.cleaned_data['letter_topic']
                            letters.message_subject = form.cleaned_data['letter_subject']
                            letters.message_body = form.cleaned_data['letter_body']
                            letters.target_senators = True
                            letters.target_representatives = True
                            letters.save()
                            campaign.letters.add(letters)

                            if form.cleaned_data['letters_toggles_on_a_trigger']:
                                if trigger:
                                    letters_toggle_trigger = trigger.clone_as_announced_positions_on()
                                else:
                                    raise ValueError("Must create a trigger.")
                                letters.body_toggles_on = letters_toggle_trigger
                                letters.save()

                    # Redirect to the new campaign.
                    return HttpResponseRedirect('/admin/itfsite/campaign/%d' % campaign.id)
                except Exception as e:
                    error = str(e)

        else: # GET
            form = NewForm()
            error = None

        return render(request, "itfsite/admin/new-campaign.html", { 'form': form, 'error': error })


admin.site.register(User, UserAdmin)
admin.site.register(AnonymousUser, AnonymousUserAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Campaign, CampaignAdmin)
admin.site.register(Notification) # not really helpful outside of debugging
