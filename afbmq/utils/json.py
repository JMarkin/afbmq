import importlib
import os

JSON = 'json'
RAPIDJSON = 'rapidjson'
UJSON = 'ujson'
ORJSON = 'orjson'

# Detect mode
mode = JSON
for json_lib in (RAPIDJSON, ORJSON, UJSON):
    if 'DISABLE_' + json_lib.upper() in os.environ:
        continue

    try:
        json = importlib.import_module(json_lib)
    except ImportError:
        continue
    else:
        mode = json_lib
        break

if mode == RAPIDJSON:
    def dumps(data):
        return json.dumps(data, ensure_ascii=False, number_mode=json.NM_NATIVE,
                          datetime_mode=json.DM_ISO8601 | json.DM_NAIVE_IS_UTC)


    def loads(data):
        return json.loads(data, number_mode=json.NM_NATIVE,
                          datetime_mode=json.DM_ISO8601 | json.DM_NAIVE_IS_UTC)

elif mode == ORJSON:
    def dumps(data):
        return json.dumps(data).decode('utf-8')


    def loads(data):
        return json.loads(data)

elif mode == UJSON:
    def loads(data):
        return json.loads(data)


    def dumps(data):
        return json.dumps(data, ensure_ascii=False)

else:
    import json


    def dumps(data):
        return json.dumps(data, ensure_ascii=False)


    def loads(data):
        return json.loads(data)
