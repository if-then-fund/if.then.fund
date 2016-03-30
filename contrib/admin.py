from django.contrib import admin
from django.db import transaction
from django.conf import settings
from django import forms
from django.utils.html import escape as escape_html

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

class TriggerOutcomesWidget(forms.Widget):
    # We store outcomes as JSON, as an array of dicts. We want to
    # make editing this less error-prone by not giving the end-user
    # the raw JSON to edit.

    def render(self, name, value, attrs=None):
        try:
            # Create separate form fields per outcome & attribute.
            vote_key_str = { "+": "Aye/Yea Vote", "-": "Nay/No Vote" }
            ret = """<div style="clear: both">"""
            for i, outcome in enumerate(json.loads(value)):
                n = escape_html(name) + "_" + str(i)
                ret += """<div style="padding: 1em 0">"""
                ret += """<div style="font-weight: bold; margin-bottom: .5em">Outcome #%d - %s</div>""" % (
                    i+1,
                    outcome.get("_default", {}).get("label") or 
                        vote_key_str.get(outcome.get("vote_key"), "")
                    )
                for key, label, help_text in (
                    ("label", "Label", "Primary text on the button to take action."),
                    ("tip", "Tip", "Optional small text displayed below the label."),
                    ("object", "Objective", "Finishes the sentence \"blah blah voted....\" ")):
                    ret += """<div>
                        <label for="id_%s">%s:</label>
                        <input class="vTextField" id="id_%s" maxlength="256" name="%s" type="text" value="%s" placeholder="%s" style="width: 30em; margin-bottom: 0">
                        <p class="help">%s</p>
                        </div>""" % (
                            n + "_" + key,
                            escape_html(label),
                            n + "_" + key,
                            n + "_" + key,
                            escape_html(outcome.get(key, "") or ""), # None => empty string
                            escape_html(outcome.get("_default", {}).get(key, "")),
                            escape_html(help_text),
                        )
                # round-trip any keys that aren't submitted in form fields
                other_keys = { key: value for key, value in outcome.items()
                    if key not in ("label", "tip", "object", "_default") }
                ret += """<input type="hidden" name="%s" value="%s">""" % (
                    n + "_otherkeys", escape_html(json.dumps(other_keys)))
                ret += """<div>"""
            #ret += """<pre>""" + escape_html(value) + """</pre>"""
            ret += """<div>"""
            return ret
        except Exception:
            # fallback
            return admin.widgets.AdminTextareaWidget().render(name, value, attrs=attrs)

    def value_from_datadict(self, data, files, name):
        if name in data:
            # fallback if we didn't replace the widget
            return admin.widgets.AdminTextareaWidget().value_from_datadict(data, files, name)

        outcomes = []
        i = 0
        while True:
            n = escape_html(name) + "_" + str(i)
            if n + "_label" not in data: break # no more outcomes
            outcome = json.loads(data[n + "_otherkeys"]) # default data
            for key in ("label", "tip", "object"):
                # set if string is truthy - don't create key if value is empty
                value = data[n + "_" + key].strip()
                if value:
                    outcome[key] = value
            outcomes.append(outcome)
            i += 1

        return json.dumps(outcomes)

class TriggerAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['outcomes'].widget = TriggerOutcomesWidget()
    def clean_outcomes(self):
        outcomes = self.cleaned_data['outcomes']
        if not isinstance(outcomes, list) or len(outcomes) != 2: raise forms.ValidationError('Invalid data.')
        for i, outcome in enumerate(outcomes):
            if not outcome.get("label", "").strip():
                raise forms.ValidationError("Outcome #%d's label cannot be empty." % (i+1))
            if not outcome.get("object", "").strip():
                raise forms.ValidationError("Outcome #%d's objective cannot be empty." % (i+1))
        return outcomes

class TriggerAdmin(admin.ModelAdmin):
    form = TriggerAdminForm
    list_display = ['title', 'status', 'id', 'pledge_count', 'total_pledged', 'created']
    raw_id_fields = ['owner']
    readonly_fields = ['status', 'pledge_count', 'total_pledged']
    search_fields = ['id', 'title', 'description']
    exclude = ['key', 'owner', 'extra']

    actions = ['clone_for_announced_positions_on_this', 'execute_empty', 'draft_to_open', 'open_to_draft']
    def clone_for_announced_positions_on_this(modeladmin, request, queryset):
        for t in queryset.filter():
            t.clone_as_announced_positions_on()
    def execute_empty(modeladmin, request, queryset):
        for t in queryset.filter():
            t.execute_empty()
    def draft_to_open(modeladmin, request, queryset):
        queryset.filter(status__in=(TriggerStatus.Draft, TriggerStatus.Paused)).update(status=TriggerStatus.Open)
    draft_to_open.short_description = "Draft/Paused => Open"
    def open_to_draft(modeladmin, request, queryset):
        queryset.filter(status=TriggerStatus.Open).update(status=TriggerStatus.Draft)
    open_to_draft.short_description = "Open => Draft"

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


class TriggerCustomizationExtraWidget(forms.Widget):
    # We store overridden outcome strings within the JSON extra field.
    # Render this nicer in the admin.

    def __init__(self, trigger_outcomes):
        super().__init__()
        self.trigger_outcomes = trigger_outcomes

    def render(self, name, value, attrs=None):
        # Get the current value. If empty, initialize to empty data.
        outcome_strings = (json.loads(value) or {}).get('outcome_strings')
        if not outcome_strings:
            outcome_strings = [{} for outcome in self.trigger_outcomes]

        # Copy in the main label so it can be displayed.
        for i, outcome in enumerate(self.trigger_outcomes):
            outcome_strings[i]['_default'] = outcome

        return TriggerOutcomesWidget().render(
            name + "_outcome_strings",
            json.dumps(outcome_strings))
       
    def value_from_datadict(self, data, files, name):
        # Get value.
        outcome_strings = json.loads(TriggerOutcomesWidget().value_from_datadict(data, files, name + "_outcome_strings"))

        # If all fields are empty, clear the whole thing.
        for outcome in outcome_strings:
            if outcome.get("label") or outcome.get("tip") or outcome.get("object"):
                break
        else:
            # No truthy values.
            outcome_strings = None

        return json.dumps({
            "outcome_strings": outcome_strings
        })
        
        

class TriggerCustomizationAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'instance' not in kwargs or kwargs['instance'] is None: return # add form doesn't have an instance
        self.fields['outcome'].widget = forms.Select(
            choices=
            [('', "---------")] +
            [(i, outcome['label']) for i, outcome in enumerate(kwargs['instance'].trigger.outcomes)])
        self.fields['incumb_challgr'].widget = forms.Select(
            choices=[
                (None, "---------"),
                (1.0, "Incumbents Only"),
                (-1.0, "Challengers Only"),
                (0.0, "Both Incumbents and Challengers"),
            ])
        self.fields['extra'].widget = TriggerCustomizationExtraWidget(kwargs['instance'].trigger.outcomes)

class TriggerCustomizationAdmin(admin.ModelAdmin):
    form = TriggerCustomizationAdminForm
    list_display = ['id', 'owner', 'trigger', 'created']
    raw_id_fields = ['trigger', 'owner']
    search_fields = ['id', 'owner__id', 'owner__name', 'title'] + ['trigger__'+f for f in TriggerAdmin.search_fields]
    exclude = ['filter_competitive'] # not used yet

class TriggerExecutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'trigger', 'pledge_count_', 'total_contributions', 'created']
    readonly_fields = ['trigger', 'pledge_count', 'pledge_count_with_contribs', 'num_contributions', 'total_contributions']
    search_fields = ['id'] + ['trigger__'+f for f in TriggerAdmin.search_fields]

    def pledge_count_(self, obj):
        return "%d/%d" % (obj.pledge_count, obj.pledge_count_with_contribs)
    pledge_count_.short_description = "pledges (exct'd/contrib'd)"

    def get_urls(self):
        from django.conf.urls import patterns
        urls = super(TriggerExecutionAdmin, self).get_urls()
        return patterns('',
            (r'^([0-9]+)/actions$', self.admin_site.admin_view(self.edit_actions)),
        ) + urls

    def edit_actions(self, request, trigger_execution_id):
        from django.shortcuts import render, get_object_or_404

        trigger_execution = get_object_or_404(TriggerExecution, id=trigger_execution_id)
        trigger = trigger_execution.trigger

        # Validity checks.
        if trigger.pledge_count > 0:
            return render(request, "contrib/admin/edit-actions.html", {
                "trigger": trigger,
                "error": "Can't edit this trigger. There are pledges on it."
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
                        for actor_outcome in ao:
                            if actor_outcome['actor'].office and isinstance(outcome, int):
                                # Include only actors known to currently be in office
                                # and those that had an aye/no vote.
                                actor_outcomes[actor_outcome['actor']] = actor_outcome['outcome']
                            else:
                                # Clear out the positions of any actor mentioned in the
                                # vote that does not have a current office or that voted
                                # present/not-voting.
                                actor_outcomes[actor_outcome['actor']] = "null"

                    elif k.startswith("actor_"):
                        actor = Actor.objects.get(id=k[6:])
                        actor_outcomes[actor] = (v if v in ("null", "rno") else int(v))

                for actor, outcome in actor_outcomes.items():
                    axn = Action.objects.filter(execution=trigger_execution, actor=actor)
                    if outcome == "null":
                        # Delete action if exists.
                        axn.delete()
                    elif axn.first() and outcome != "rno" and axn.first().outcome == outcome:
                        # Exists with correct outcome value.
                        pass
                    elif axn.first() and outcome == "rno" and axn.first().outcome == None:
                        # Exists with correct outcome & a reason_for_no_outcome is set.
                        pass
                    else:
                        # Doesn't exist, or exists with wrong outcome value.
                        axn.delete()
                        if outcome == "rno":
                            return render(request, "contrib/admin/edit-actions.html", {
                                "trigger": trigger,
                                "error": "Can't set %s to having a reason for no outcome." % str(actor),
                            })
                        Action.create(trigger_execution, actor, outcome)

        else: # GET
            pass

        # Get existing positions.
        data = { }
        if True:
            # Fetch.
            data.update({
                action[0]: {
                    "actor": action[0],
                    "position": action[1],
                    "reason_for_no_outcome": action[2],
                }
                for action
                  in trigger_execution.actions.values_list('actor__id', 'outcome', 'reason_for_no_outcome')
            })

            # Convert Actor IDs to objects.
            actors = Actor.objects.in_bulk({ entry["actor"] for entry in data.values() })
            for entry in data.values():
                entry["actor"] = actors[entry["actor"]]

        # Which other actors can have a position on this? Ones currently holding
        # office.
        for actor in Actor.objects.exclude(office=None):
            if actor.id not in data:
                data[actor.id] = {
                    "actor": actor,
                }

        # Sort and display.
        data = sorted(data.values(), key = lambda entry : (not ('position' in entry or 'reason_for_no_outcome' in entry), entry['actor'].name_sort))
        return render(request, "contrib/admin/edit-actions.html", {
            "trigger": trigger,
            "data": data,
        })

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
    list_display = ['id', 'status', 'action', 'user_or_email', 'amount', 'referrer', 'created']
    readonly_fields = ['user', 'anon_user', 'trigger', 'via_campaign', 'profile', 'amount', 'algorithm'] # amount is read-only because a total is cached in the Trigger
    search_fields = ['id', 'user__email', 'anon_user__email'] \
      + ['trigger__'+f for f in TriggerAdmin.search_fields] \
      + ['profile__'+f for f in ContributorInfoAdmin.search_fields]
    def action(self, obj):
        return str(obj.via_campaign) + (("/" + str(obj.trigger)) if not obj.via_campaign.is_sole_trigger(obj.trigger) else "")
    def user_or_email(self, obj):
        return obj.user if obj.user else (obj.anon_user.email + " (?)")
    user_or_email.short_description = 'User or Unverified Email'
    def referrer(self, obj):
        return obj.ref_code

@no_delete_action
class CancelledPledgeAdmin(admin.ModelAdmin):
    list_display = ['created', 'user_or_email', 'trigger']
    readonly_fields = ['user', 'trigger']
    search_fields = ['user__email', 'anon_user__email'] + ['trigger__'+f for f in TriggerAdmin.search_fields]
    def user_or_email(self, obj):
        return obj.user if obj.user else ((obj.anon_user.email or "[None]") + " (?)")
    user_or_email.short_description = 'User or Unverified Email'

@no_delete_action
class PledgeExecutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'pledge_', 'user_or_email', 'charged', 'created', 'action']
    readonly_fields = ['pledge', 'charged', 'fees']
    search_fields = ['id'] + ['pledge__'+f for f in PledgeAdmin.search_fields]
    def pledge_(self, obj):
        return obj.pledge_id
    pledge_.short_description = "Pledge ID"
    def user_or_email(self, obj):
        p = obj.pledge
        return p.user if p.user else (p.anon_user.email + " (?)")
    user_or_email.short_description = 'User/Email'
    def action(self, obj):
        return str(obj.pledge.via_campaign) + (("/" + str(obj.pledge.trigger)) if not obj.pledge.via_campaign.is_sole_trigger(obj.pledge.trigger) else "")

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
