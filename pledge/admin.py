from django.contrib import admin
from pledge.models import *

class TriggerAdmin(admin.ModelAdmin):
    list_display = ['created', 'state', 'slug', 'title']

admin.site.register(Trigger, TriggerAdmin)
admin.site.register(TriggerStatusUpdate)
admin.site.register(TriggerExecution)
admin.site.register(Actor)
admin.site.register(Action)
admin.site.register(Pledge)
admin.site.register(PledgeExecution)
admin.site.register(Campaign)
admin.site.register(Contribution)
