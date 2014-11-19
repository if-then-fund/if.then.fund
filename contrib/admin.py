from django.contrib import admin
from contrib.models import *

class TriggerAdmin(admin.ModelAdmin):
    list_display = ['created', 'state', 'slug', 'title']
    raw_id_fields = ['owner']

class ActorAdmin(admin.ModelAdmin):
    list_display = ['name_long', 'party', 'govtrack_id']

class PledgeAdmin(admin.ModelAdmin):
    list_display = ['user_or_email', 'trigger', 'amount', 'created']
    raw_id_fields = ['user', 'trigger']
    def user_or_email(self, obj):
    	return obj.user if obj.user else obj.email
    user_or_email.short_description = 'User or Unverified Email'

class CancelledPledgeAdmin(admin.ModelAdmin):
    list_display = ['created', 'user_or_email', 'trigger']
    raw_id_fields = ['user', 'trigger']
    def user_or_email(self, obj):
        return obj.user if obj.user else obj.email
    user_or_email.short_description = 'User or Unverified Email'

class RecipientAdmin(admin.ModelAdmin):
    list_display = ['name', 'actor', 'challenger']
    raw_id_fields = ['actor']

admin.site.register(Trigger, TriggerAdmin)
admin.site.register(TriggerStatusUpdate)
admin.site.register(TriggerExecution)
admin.site.register(Actor, ActorAdmin)
admin.site.register(Action)
admin.site.register(Pledge, PledgeAdmin)
admin.site.register(CancelledPledge, CancelledPledgeAdmin)
admin.site.register(PledgeExecution)
admin.site.register(Recipient, RecipientAdmin)
admin.site.register(Contribution)
