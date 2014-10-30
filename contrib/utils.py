def query_json_api(base_url, params):
	import urllib.request, urllib.parse, json
	url = base_url + "?" + urllib.parse.urlencode(params)
	req = urllib.request.urlopen(url)
	return json.loads(req.read().decode("utf-8"))

