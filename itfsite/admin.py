from django.contrib import admin
from itfsite.models import *
from contrib.models import TriggerCustomization

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

admin.site.register(User, UserAdmin)
admin.site.register(AnonymousUser, AnonymousUserAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Campaign, CampaignAdmin)
admin.site.register(Notification) # not really helpful outside of debugging
