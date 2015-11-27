from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from contrib.models import Trigger

class Command(BaseCommand):
	args = ''
	help = ''

	def handle(self, *args, **options):
		for t in Trigger.objects.all():
			if t.extra and "max_split" in t.extra:
				m = t.extra["max_split"]
				del t.extra["max_split"]

				if not t.trigger_type.extra: t.trigger_type.extra = { }
				if "max_split" in t.trigger_type.extra and m != t.trigger_type.extra["max_split"]:
					raise ValueError(t)
				elif "max_split" not in t.trigger_type.extra:
					t.trigger_type.extra["max_split"] = m
					t.trigger_type.save()

				t.save(update_fields=['extra'])