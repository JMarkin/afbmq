import datetime

from babel.support import LazyProxy
from pydantic import BaseModel

from . import json

DEFAULT_FILTER = ['self', 'cls']


def generate_payload(exclude=None, **kwargs):
    """
    Generate payload

    Usage: payload = generate_payload(**locals(), exclude=['foo'])

    :param exclude:
    :param kwargs:
    :return: dict
    """
    _d = {}
    if exclude is None:
        exclude = set(DEFAULT_FILTER)
    elif isinstance(exclude, list):
        exclude = set(exclude + DEFAULT_FILTER)
    for key, value in kwargs.items():
        if value is None or key in exclude or key.startswith('_'):
            continue
        if isinstance(value, BaseModel):
            _d[key] = generate_payload(exclude=exclude, **value.dict())
        else:
            _d[key] = value

    return _d


def _normalize(obj):
    """
    Normalize dicts and lists

    :param obj:
    :return: normalized object
    """
    if isinstance(obj, list):
        return [_normalize(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items() if v is not None}
    elif hasattr(obj, 'to_python'):
        return obj.to_python()
    return obj


def prepare_arg(value):
    """
    Stringify dicts/lists and convert datetime/timedelta to unix-time

    :param value:
    :return:
    """
    if value is None:
        return value
    if isinstance(value, (list, dict)) or hasattr(value, 'to_python'):
        return json.dumps(_normalize(value))
    if isinstance(value, datetime.timedelta):
        now = datetime.datetime.now()
        return int((now + value).timestamp())
    if isinstance(value, datetime.datetime):
        return round(value.timestamp())
    if isinstance(value, LazyProxy):
        return str(value)
    return value
