import enum, json, datetime

from django.http import HttpResponse

from jsonfield import JSONField as _JSONField
from enumfields import EnumIntegerField as EnumField

from .templatetags.itfsite_utils import render_text

class JSONField(_JSONField):
	# turns on sort_keys
    def __init__(self, *args, **kwargs):
        super(_JSONField, self).__init__(*args, dump_kwargs={"sort_keys": True}, **kwargs)

class TextFormat(enum.Enum):
	HTML = 0
	Markdown = 1

def json_response(response):
	# If the data is an HttpResponse already, just
	# return it unchanged.
	if isinstance(response, HttpResponse):
		return response

	# JSONify and return.
	payload = json.dumps(response, indent='  ', sort_keys=True)
	resp = HttpResponse(payload, content_type="application/json")
	resp["Content-Length"] = len(payload)
	return resp

def serialize_value(val, text_format):
	# Makes a value serializable, given that it's of a type
	# pulled by serialize_obj.
	if isinstance(val, enum.Enum): return val.name
	if isinstance(val, (datetime.datetime, datetime.date)): return val.isoformat()
	if isinstance(val, str) and text_format: return render_text(val, text_format)
	return val

def serialize_obj(obj, keys=None, render_text_map={}):
	# Makes a Python object JSON-serializable by turning its fields into dict attributes.
	return { k: serialize_value(v, getattr(obj, render_text_map.get(k, "--"), None)) for k, v in obj.__dict__.items() if
		    isinstance(k, str)
		and (not keys or k in keys)
		and isinstance(v, (int, float, str, enum.Enum, datetime.datetime, datetime.date))}

def mergedicts(*args):
	# Merges all of the dics.
	ret = { }
	for d in args: ret.update(d)
	return ret
