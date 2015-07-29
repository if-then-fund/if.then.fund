from django.contrib import admin
from itfsite.models import *

class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'id', 'is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['id', 'email']

class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['slug', 'orgtype', 'id', 'name', 'created']
    search_fields = ['id', 'slug', 'name']

admin.site.register(User, UserAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Notification) # not really helpful outside of debugging
