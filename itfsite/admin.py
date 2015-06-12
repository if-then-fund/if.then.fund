from django.contrib import admin
from itfsite.models import *

admin.site.register(User)
admin.site.register(Organization)
admin.site.register(Notification) # not really helpful outside of debugging
