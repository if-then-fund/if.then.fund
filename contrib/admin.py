from django.contrib import admin
from django.db import transaction
from contrib.models import *

class TriggerAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'status', 'slug', 'title', 'pledge_count', 'total_pledged']
    raw_id_fields = ['owner']
    readonly_fields = ['pledge_count', 'total_pledged']
    search_fields = ['title', 'description']

    def get_urls(self):
        from django.conf.urls import patterns
        urls = super(TriggerAdmin, self).get_urls()
        return patterns('',
            (r'^new-from-bill/$', self.admin_site.admin_view((self.new_from_bill)))
        ) + urls

    def new_from_bill(self, request):
        # Create a new Trigger from a bill ID and a vote chamber.

        from django.shortcuts import render, redirect
        from django import forms

        class NewFromBillForm(forms.Form):
            congress = forms.ChoiceField(label='Congress', choices=((114, '114th Congress'),))
            bill_type = forms.ChoiceField(label='Bill Type', choices=(('hr', 'H.R.'),('s', 'S.')))
            bill_number = forms.IntegerField(label='Bill Number', min_value=1, max_value=9999)
            vote_chamber = forms.ChoiceField(label='Vote in chamber', choices=(('x', 'Whichever Votes First'), ('h', 'House'), ('s', 'Senate')))
            pro_tip = forms.CharField(label='Pro Tip', help_text="e.g. 'Pro-Environment'")
            con_tip = forms.CharField(label='Con Tip', help_text="e.g. 'Pro-Environment'")
            vote_url = forms.URLField(required=False, label="Vote URL", help_text="Optional. If the vote has already occurred, paste a link to the GovTrack.us page with roll call vote details.")
        
        if request.method == "POST":
            form = NewFromBillForm(request.POST)
            error = None
            if form.is_valid():
                from contrib.legislative import create_trigger_from_bill, execute_trigger_from_vote
                from django.http import HttpResponseRedirect
                try:
                    # If any validation fails, don't create the trigger.
                    with transaction.atomic():
                        # Create trigger.
                        bill_id = form.cleaned_data['bill_type'] + str(form.cleaned_data['bill_number']) + "-" + str(form.cleaned_data['congress'])
                        t = create_trigger_from_bill(bill_id, form.cleaned_data['vote_chamber'])

                        # Set tips.
                        for outcome in t.outcomes:
                            if outcome['vote_key'] == "+": outcome['tip'] = form.cleaned_data['pro_tip']
                            if outcome['vote_key'] == "-": outcome['tip'] = form.cleaned_data['con_tip']
                        t.save()

                        # If a vote URL is given, execute it immediately.
                        if form.cleaned_data['vote_url']:
                            t.status = TriggerStatus.Open # can't execute while draft
                            t.save()
                            execute_trigger_from_vote(t, form.cleaned_data['vote_url'])

                    # Redirect to admin.
                    return HttpResponseRedirect('/admin/contrib/trigger/%d' % t.id)
                except Exception as e:
                    error = str(e)

        else: # GET
            form = NewFromBillForm()
            error = None

        return render(request, "contrib/admin/new-trigger-from-bill.html", { 'form': form, 'error': error })

class TriggerStatusUpdateAdmin(admin.ModelAdmin):
    readonly_fields = ['trigger']

class TriggerExecutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'trigger', 'pledge_count_', 'total_contributions']
    readonly_fields = ['trigger', 'pledge_count', 'pledge_count_with_contribs', 'num_contributions', 'total_contributions']
    def pledge_count_(self, obj):
        return "%d/%d" % (obj.pledge_count, obj.pledge_count_with_contribs)
    pledge_count_.short_description = "pledges (exct'd/contrib'd)"

class ActorAdmin(admin.ModelAdmin):
    list_display = ['name_long', 'party', 'govtrack_id', 'challenger']
    raw_id_fields = ['challenger']
    search_fields = ['name_long', 'govtrack_id']

class ActionAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'trigger', 'name', 'outcome_', 'total_contributions_for', 'total_contributions_against']
    readonly_fields = ['execution', 'actor', 'challenger', 'total_contributions_for', 'total_contributions_against']
    def created(self, obj):
        return obj.execution.created
    def trigger(self, obj):
        return obj.execution.trigger
    def name(self, obj):
        return obj.name_long
    def outcome_(self, obj):
        return obj.outcome_label()
    outcome_.short_description = "Outcome"

class PledgeAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'trigger', 'user_or_email', 'amount', 'created']
    readonly_fields = ['user', 'trigger', 'amount', 'algorithm'] # amount is read-only because a total is cached in the Trigger
    def user_or_email(self, obj):
        return obj.user if obj.user else (obj.email + " (?)")
    user_or_email.short_description = 'User or Unverified Email'

class CancelledPledgeAdmin(admin.ModelAdmin):
    list_display = ['created', 'user_or_email', 'trigger']
    readonly_fields = ['user', 'trigger']
    def user_or_email(self, obj):
        return obj.user if obj.user else obj.email
    user_or_email.short_description = 'User or Unverified Email'

class PledgeExecutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'trigger', 'user_or_email', 'charged']
    readonly_fields = ['pledge', 'charged', 'fees']
    def user_or_email(self, obj):
        p = obj.pledge
        return p.user if p.user else p.email
    user_or_email.short_description = 'User/Email'
    def trigger(self, obj):
        return obj.pledge.trigger

class RecipientAdmin(admin.ModelAdmin):
    list_display = ['name', 'de_id', 'actor', 'office_sought', 'party']
    raw_id_fields = ['actor']
    def name(self, obj):
        return str(obj)

class ContributionAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'amount', 'recipient', 'user_or_email', 'trigger']
    readonly_fields = ['pledge_execution', 'action', 'recipient', 'amount'] # amount it readonly because a total is cached in the Action
    exclude = ['refunded_time']
    def created(self, obj):
        return obj.pledge_execution.created
    def user_or_email(self, obj):
        p = obj.pledge_execution.pledge
        return p.user if p.user else p.email
    user_or_email.short_description = 'User/Email'
    def trigger(self, obj):
        return obj.pledge_execution.pledge.trigger

admin.site.register(Trigger, TriggerAdmin)
admin.site.register(TriggerStatusUpdate, TriggerStatusUpdateAdmin)
admin.site.register(TriggerExecution, TriggerExecutionAdmin)
admin.site.register(Actor, ActorAdmin)
admin.site.register(Action, ActionAdmin)
admin.site.register(Pledge, PledgeAdmin)
admin.site.register(CancelledPledge, CancelledPledgeAdmin)
admin.site.register(PledgeExecution, PledgeExecutionAdmin)
admin.site.register(Recipient, RecipientAdmin)
admin.site.register(Contribution, ContributionAdmin)
