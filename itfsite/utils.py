import enum

from enum3field import django_enum
from jsonfield import JSONField as _JSONField

class JSONField(_JSONField):
	# turns on sort_keys
    def __init__(self, *args, **kwargs):
        super(_JSONField, self).__init__(*args, dump_kwargs={"sort_keys": True}, **kwargs)

@django_enum
class TextFormat(enum.Enum):
	HTML = 0
	Markdown = 1
