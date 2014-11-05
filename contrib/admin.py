from django.contrib import admin
from contrib.models import *

class TriggerAdmin(admin.ModelAdmin):
    list_display = ['created', 'state', 'slug', 'title']
    raw_id_fields = ['owner']

class PledgeAdmin(admin.ModelAdmin):
    list_display = ['user_or_email', 'trigger', 'contrib_amount']
    raw_id_fields = ['user', 'trigger']
    def user_or_email(self, obj):
    	return obj.user if obj.user else obj.email
    user_or_email.short_description = 'User or Unverified Email'

admin.site.register(Trigger, TriggerAdmin)
admin.site.register(TriggerStatusUpdate)
admin.site.register(TriggerExecution)
admin.site.register(Actor)
admin.site.register(Action)
admin.site.register(Pledge, PledgeAdmin)
admin.site.register(PledgeExecution)
admin.site.register(Campaign)
admin.site.register(Contribution)
