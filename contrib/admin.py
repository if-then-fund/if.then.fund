from django.contrib import admin
from contrib.models import *

class TriggerAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'status', 'slug', 'title', 'pledge_count', 'total_pledged']
    raw_id_fields = ['owner']
    readonly_fields = ['pledge_count', 'total_pledged']

class TriggerStatusUpdateAdmin(admin.ModelAdmin):
    readonly_fields = ['trigger']

class TriggerExecutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'trigger', 'pledge_count_', 'total_contributions']
    readonly_fields = ['trigger', 'pledge_count', 'pledge_count_with_contribs', 'total_contributions']
    def pledge_count_(self, obj):
        return "%d/%d" % (obj.pledge_count, obj.pledge_count_with_contribs)
    pledge_count_.short_description = "pledges (exct'd/contrib'd)"

class ActorAdmin(admin.ModelAdmin):
    list_display = ['name_long', 'party', 'govtrack_id']

class ActionAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'trigger', 'name', 'outcome_', 'total_contributions_for', 'total_contributions_against']
    readonly_fields = ['execution', 'actor', 'total_contributions_for', 'total_contributions_against']
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
    	return obj.user if obj.user else obj.email
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
    list_display = ['name', 'actor', 'challenger']
    raw_id_fields = ['actor']

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
