from django.contrib import admin

from .models import LettersCampaign, ConstituentInfo, UserLetter

class CampaignAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'id', 'created']
    search_fields = ['title', 'owner__name', 'owner__slug']
    raw_id_fields = ['owner', 'body_toggles_on']

class ConstituentInfoAdmin(admin.ModelAdmin):
	search_fields = ['id', 'extra']

class UserLetterAdmin(admin.ModelAdmin):
    list_display = ['id', 'letterscampaign', 'user_or_email', 'campaign', 'submitted', 'created']
    readonly_fields = ['user', 'anon_user', 'letterscampaign', 'profile', 'via_campaign']
    search_fields = ['id', 'user__email', 'anon_user__email'] \
      + ['letterscampaign__'+f for f in CampaignAdmin.search_fields] \
      + ['profile__'+f for f in ConstituentInfoAdmin.search_fields]
    actions = ['submit_for_delivery']

    def user_or_email(self, obj):
        return obj.user if obj.user else (obj.anon_user.email + " (?)")
    user_or_email.short_description = 'User or Unverified Email'
    def campaign(self, obj):
        return "/".join(str(x) for x in [obj.via_campaign, obj.ref_code] if x)
    def submitted(self, obj):
        return "%d/%d" % (obj.delivered, obj.delivered+obj.pending)

    def submit_for_delivery(modeladmin, request, queryset):
        for obj in queryset:
            obj.submit_for_delivery()

admin.site.register(LettersCampaign, CampaignAdmin)
admin.site.register(ConstituentInfo, ConstituentInfoAdmin)
admin.site.register(UserLetter, UserLetterAdmin)
