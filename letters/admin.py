from django.contrib import admin
from .models import LettersCampaign

class CampaignAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'id', 'created']
    search_fields = ['title', 'owner__name', 'owner__slug']
    raw_id_fields = ['owner']

admin.site.register(LettersCampaign, CampaignAdmin)
