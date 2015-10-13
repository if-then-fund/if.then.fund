from django.contrib import admin
from django.db import transaction
from django.conf import settings

from contrib.models import *

def json_response(data):
    from django.http import HttpResponse
    import rtyaml
    response = HttpResponse(content_type="application/json")
    rtyaml.dump(data, response)
    return response

def no_delete_action(admin):
    class MyClass(admin):
        def get_actions(self, request):
            actions = super(admin, self).get_actions(request)
            if 'delete_selected' in actions:
                del actions['delete_selected']
            return actions
    return MyClass

class TriggerAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'id', 'pledge_count', 'total_pledged', 'created']
    raw_id_fields = ['owner']
    readonly_fields = ['pledge_count', 'total_pledged']
    search_fields = ['id', 'title', 'description']

    actions = ['clone_for_announced_positions_on_this', 'execute_empty']
    def clone_for_announced_positions_on_this(modeladmin, request, queryset):
        for t in queryset.filter():
            t.clone_as_announced_positions_on()
    def execute_empty(modeladmin, request, queryset):
        for t in queryset.filter():
            t.execute_empty()

    def get_urls(self):
        from django.conf.urls import patterns
        urls = super(TriggerAdmin, self).get_urls()
        return patterns('',
            (r'^new-from-bill/$', self.admin_site.admin_view(self.new_from_bill)),
            (r'^([0-9]+)/edit-actions$', self.admin_site.admin_view(self.edit_actions)),
        ) + urls

    def new_from_bill(self, request):
        # Create a new Trigger from a bill ID and a vote chamber.

        from django.shortcuts import render, redirect
        from django import forms

        class NewFromBillForm(forms.Form):
            congress = forms.ChoiceField(label='Congress', choices=((114, '114th Congress'),))
            bill_type = forms.ChoiceField(label='Bill Type', choices=(('hr', 'H.R.'),('s', 'S.'),('hjres', 'H.J.Res.')))
            bill_number = forms.IntegerField(label='Bill Number', min_value=1, max_value=9999)
            vote_chamber = forms.ChoiceField(label='Vote in chamber', choices=(('x', 'Whichever Votes First'), ('h', 'House'), ('s', 'Senate')))
            pro_label = forms.CharField(label='Pro Label', help_text="e.g. 'Pro-Environment'")
            pro_object = forms.CharField(label='Pro Description', help_text="e.g. 'to defend the environment'")
            con_label = forms.CharField(label='Con Label', help_text="e.g. 'Pro-Environment'")
            con_object = forms.CharField(label='Con Description', help_text="e.g. 'to defend the environment'")
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
                            # move our default label to the tip
                            outcome['tip'] = outcome['label']

                            # bring in user values
                            outcome['label'] = form.cleaned_data[('pro' if outcome['vote_key'] == "+" else 'con') + '_label']
                            outcome['object'] = form.cleaned_data[('pro' if outcome['vote_key'] == "+" else 'con') + '_object']
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

    def edit_actions(self, request, trigger_id):
        from django.shortcuts import render, get_object_or_404

        trigger = get_object_or_404(Trigger, id=trigger_id)

        # Validity checks.
        if trigger.pledge_count > 0:
            return render(request, "contrib/admin/edit-actions.html", {
                "trigger": trigger,
                "error": "Can't edit this trigger. There are pledges on it."
            })
        elif trigger.status != TriggerStatus.Executed:
            return render(request, "contrib/admin/edit-actions.html", {
                "trigger": trigger,
                "error": "Can't edit a trigger with status %s." % trigger.status.name,
            })

        if request.method == "POST":
            with transaction.atomic():
                # Update positions.
                actor_outcomes = { }
                for k, v in request.POST.items():
                    if k == "from-vote-url":
                        # Load the vote from GovTrack.
                        try:
                            from .legislative import load_govtrack_vote, load_govtrack_sponsors
                            if "/votes" in v:
                                (vote, when, ao) = load_govtrack_vote(trigger, v, flip=request.POST.get('from-vote-flip'))
                            else:
                                (bill, ao) = load_govtrack_sponsors(trigger, v, flip=request.POST.get('from-vote-flip'))
                        except Exception as e:
                            return render(request, "contrib/admin/edit-actions.html", {
                                "trigger": trigger,
                                "error": str(e),
                            })
                        for actor, outcome in ao.items():
                            if actor.office and isinstance(outcome, int):
                                # Include only actors known to currently be in office
                                # and those that had an aye/no vote.
                                actor_outcomes[actor] = outcome
                            else:
                                # Clear out the positions of any actor mentioned in the
                                # vote that does not have a current office or that voted
                                # present/not-voting.
                                actor_outcomes[actor] = "null"

                    elif k.startswith("actor_"):
                        actor = Actor.objects.get(id=k[6:])
                        actor_outcomes[actor] = (v if v == "null" else int(v))

                for actor, outcome in actor_outcomes.items():
                    axn = Action.objects.filter(execution__trigger=trigger, actor=actor)
                    if outcome == "null":
                        # Delete action if exists.
                        axn.delete()
                    elif axn.first() and axn.first().outcome == outcome:
                        # Exists with correct outcome value.
                        pass
                    else:
                        # Doesn't exist, or exists with wrong outcome value.
                        axn.delete()
                        Action.create(trigger.execution, actor, outcome)

        else: # GET
            pass

        # Which actors can have a position on this? Ones currently holding
        # office.
        actors = Actor.objects.exclude(office=None)

        # Get existing positions.
        existing_positions = { }
        if trigger.status == TriggerStatus.Executed:
            existing_positions = dict(trigger.execution.actions.values_list('actor__id', 'outcome'))

        data = { }
        for actor in actors:
            data[actor] = {
                "actor": actor,
                "position": existing_positions.get(actor.id),
            }

        data = sorted(data.values(), key = lambda entry : (entry['position'] is None, entry['actor'].name_sort))
        return render(request, "contrib/admin/edit-actions.html", {
            "trigger": trigger,
            "data": data,
        })

class TriggerStatusUpdateAdmin(admin.ModelAdmin):
    readonly_fields = ['trigger']
    search_fields = ['id', 'trigger__id']

class TriggerRecommendationAdmin(admin.ModelAdmin):
    raw_id_fields = ['trigger1', 'trigger2']
    readonly_fields = ['notifications_created']
    list_display = ['id', 'trigger1', 'trigger2', 'symmetric', 'notifications_created']
    actions = ['create_initial_notifications']
    search_fields = ['id', 'trigger1__id', 'trigger2__id']
    def create_initial_notifications(modeladmin, request, queryset):
        for tr in queryset.filter(notifications_created=False):
            tr.create_initial_notifications()

class TriggerCustomizationAdmin(admin.ModelAdmin):
    list_display = ['id', 'owner', 'trigger', 'created']
    raw_id_fields = ['trigger', 'owner']
    search_fields = ['id', 'owner__id', 'owner__name', 'title'] + ['trigger__'+f for f in TriggerAdmin.search_fields]

class TriggerExecutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'trigger', 'pledge_count_', 'total_contributions', 'created']
    readonly_fields = ['trigger', 'pledge_count', 'pledge_count_with_contribs', 'num_contributions', 'total_contributions']
    search_fields = ['id'] + ['trigger__'+f for f in TriggerAdmin.search_fields]
    def pledge_count_(self, obj):
        return "%d/%d" % (obj.pledge_count, obj.pledge_count_with_contribs)
    pledge_count_.short_description = "pledges (exct'd/contrib'd)"

class ActorAdmin(admin.ModelAdmin):
    list_display = ['name_long', 'party', 'govtrack_id', 'office', 'challenger', 'id']
    raw_id_fields = ['challenger']
    search_fields = ['id', 'name_long', 'govtrack_id', 'challenger__id', 'challenger__office_sought']

class ActionAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'trigger', 'name', 'outcome_', 'total_contributions_for', 'total_contributions_against']
    readonly_fields = ['execution', 'actor', 'challenger', 'total_contributions_for', 'total_contributions_against']
    search_fields = ['id'] + ['execution__trigger__'+f for f in TriggerAdmin.search_fields] + ['actor__'+f for f in ActorAdmin.search_fields]
    def created(self, obj):
        return obj.execution.created
    def trigger(self, obj):
        return obj.execution.trigger
    def name(self, obj):
        return obj.name_long
    def outcome_(self, obj):
        return obj.outcome_label()
    outcome_.short_description = "Outcome"

class ContributorInfoAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'cclastfour', 'pledge_count', 'id', 'created']
    readonly_fields = ['cclastfour', 'extra_']
    fields = readonly_fields
    search_fields = ['id', 'extra', 'cclastfour']
    def pledge_count(self, obj):
        return obj.pledges.count()
    def extra_(self, obj):
        import json
        from django.utils.safestring import mark_safe, mark_for_escaping
        return mark_safe("<pre style='font-family: sans-serif;'>" + mark_for_escaping(json.dumps(obj.extra, sort_keys=True, indent=True)) + "</pre>")
    extra_.name = "Extra"

class PledgeAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'trigger', 'user_or_email', 'amount', 'campaign', 'created']
    readonly_fields = ['user', 'anon_user', 'trigger', 'via_campaign', 'profile', 'amount', 'algorithm'] # amount is read-only because a total is cached in the Trigger
    search_fields = ['id', 'user__email', 'anon_user__email'] \
      + ['trigger__'+f for f in TriggerAdmin.search_fields] \
      + ['profile__'+f for f in ContributorInfoAdmin.search_fields]
    def user_or_email(self, obj):
        return obj.user if obj.user else (obj.anon_user.email + " (?)")
    user_or_email.short_description = 'User or Unverified Email'
    def campaign(self, obj):
        return "/".join(str(x) for x in [obj.via_campaign, obj.ref_code] if x)

@no_delete_action
class CancelledPledgeAdmin(admin.ModelAdmin):
    list_display = ['created', 'user_or_email', 'trigger']
    readonly_fields = ['user', 'trigger']
    search_fields = ['user__email', 'anon_user__email'] + ['trigger__'+f for f in TriggerAdmin.search_fields]
    def user_or_email(self, obj):
        return obj.user if obj.user else obj.anon_user.email
    user_or_email.short_description = 'User or Unverified Email'

@no_delete_action
class PledgeExecutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'trigger', 'user_or_email', 'charged', 'created']
    readonly_fields = ['pledge', 'charged', 'fees']
    search_fields = ['id'] + ['pledge__'+f for f in PledgeAdmin.search_fields]
    def user_or_email(self, obj):
        p = obj.pledge
        return p.user if p.user else (p.anon_user.email + " (?)")
    user_or_email.short_description = 'User/Email'
    def trigger(self, obj):
        return obj.pledge.trigger

    # remove the Delete action
    actions = ['void'] + (['expunge_record'] if settings.DEBUG else [])
    def void(modeladmin, request, queryset):
        # Void selected pledge executions. Collect return
        # values and exceptions.
        voids = []
        for pe in queryset:
            try:
                voids.append([pe.id, str(pe), pe.void()])
            except Exception as e:
                voids.append([pe.id, str(pe), e])
        return json_response(voids)
    def expunge_record(modeladmin, request, queryset):
        # For debugging only, actually delete records.
        for pe in queryset:
            pe.delete(really=True, with_void=False)

class RecipientAdmin(admin.ModelAdmin):
    list_display = ['name', 'de_id', 'actor', 'office_sought', 'party']
    raw_id_fields = ['actor']
    search_fields = ['id', 'de_id', 'office_sought'] \
        + ['actor__'+f for f in ActorAdmin.search_fields]
    def name(self, obj):
        return str(obj)

@no_delete_action
class ContributionAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'amount', 'recipient', 'user_or_email', 'trigger']
    readonly_fields = ['pledge_execution', 'action', 'recipient', 'amount'] # amount it readonly because a total is cached in the Action
    exclude = ['refunded_time']
    search_fields = ['id'] \
        + ['pledge_execution__'+f for f in PledgeExecutionAdmin.search_fields] \
        + ['recipient__'+f for f in RecipientAdmin.search_fields]
    def created(self, obj):
        return obj.pledge_execution.created
    def user_or_email(self, obj):
        p = obj.pledge_execution.pledge
        return p.user if p.user else p.anon_user.email
    user_or_email.short_description = 'User/Email'
    def trigger(self, obj):
        return obj.pledge_execution.pledge.trigger

admin.site.register(TriggerType)
admin.site.register(Trigger, TriggerAdmin)
admin.site.register(TriggerStatusUpdate, TriggerStatusUpdateAdmin)
admin.site.register(TriggerRecommendation, TriggerRecommendationAdmin)
admin.site.register(TriggerCustomization, TriggerCustomizationAdmin)
admin.site.register(TriggerExecution, TriggerExecutionAdmin)
admin.site.register(Actor, ActorAdmin)
admin.site.register(Action, ActionAdmin)
admin.site.register(ContributorInfo, ContributorInfoAdmin)
admin.site.register(Pledge, PledgeAdmin)
admin.site.register(CancelledPledge, CancelledPledgeAdmin)
admin.site.register(PledgeExecution, PledgeExecutionAdmin)
admin.site.register(Recipient, RecipientAdmin)
admin.site.register(Contribution, ContributionAdmin)
