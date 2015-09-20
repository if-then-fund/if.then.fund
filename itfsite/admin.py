from django.contrib import admin
from itfsite.models import *
from contrib.models import Trigger, TriggerStatus, TriggerCustomization, TextFormat
from letters.models import LettersCampaign, CampaignStatus as LettersCampaignStatus

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

class CampaignAdmin(admin.ModelAdmin):
    list_display = ['slug', 'owner', 'id', 'title', 'created']
    search_fields = ['id', 'slug', 'title', 'owner__name', 'owner__slug']
    raw_id_fields = ['owner']
    inlines = [TriggersInline, LettersInline]
    exclude = ['contrib_triggers', 'letters']

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
            trigger_type = forms.ChoiceField(label='Trigger Type', choices=(('', 'No Trigger'), ('x', 'Whichever Chamber Votes First'), ('h', 'House Vote'), ('s', 'Senate Vote')))
            trigger_bill_url = forms.URLField(required=False, label="Create Trigger Using Bill", help_text="To associate the trigger with a bill, paste a link to the GovTrack.us bill page.")
            trigger_vote_url = forms.URLField(required=False, label="Execute Using Vote URL", help_text="If the vote has already occurred, paste a link to the GovTrack.us page with roll call vote details. The trigger will be immediately executed.")
            trigger_desired_outcome = forms.TypedChoiceField(required=False, coerce=int, choices=[(None, "(None)"), (0, "Option 1 (Pro)"), (1, "Option 2 (Con)")], help_text="The desired outcome of the trigger.")

            letters = forms.BooleanField(required=False, label="Send letters?")        
            letter_subject = forms.CharField(required=False, help_text="The subject line for letters.")
            letter_body = forms.CharField(widget=forms.Textarea, required=False, help_text="The body text of letters.")
            letters_toggles_on_a_trigger = forms.BooleanField(required=False, label="Message Changes Depending on Position of Target?")        
            pro_letter_subject = forms.CharField(label='Option 1 Subject', required=False, help_text="The subject line for letters sent to targets associated with position 1. Blank to reuse the main subject.")
            pro_letter_body = forms.CharField(label='Option 1 Body', required=False, widget=forms.Textarea, help_text="The body text of letters sent to targets associated with position 1. Blank to reuse the main body.")
            con_letter_subject = forms.CharField(label='Option 2 Subject', required=False, help_text="The subject line for letters sent to targets associated with position 2. Blank to reuse the main subject.")
            con_letter_body = forms.CharField(label='Option 2 Body', required=False, widget=forms.Textarea, help_text="The body text of letters sent to targets associated with position 2. Blank to reuse the main body.")

        if request.method == "POST":
            form = NewForm(request.POST)
            error = None
            if form.is_valid():
                from contrib.legislative import create_trigger_from_bill, execute_trigger_from_vote
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
                            trigger = create_trigger_from_bill(form.cleaned_data['trigger_bill_url'], form.cleaned_data['trigger_type'])
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
                            letters = LettersCampaign()
                            letters.title = campaign.title
                            letters.status = LettersCampaignStatus.Open
                            letters.owner = campaign.owner
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
