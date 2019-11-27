import typing

from pydantic import AnyUrl

from .base import FBObject


class MediaPayload(FBObject):
    url: AnyUrl


class Coors(FBObject):
    lat: float
    long: float


class LocationPayload(FBObject):
    coordinates: Coors


class AttachmentFallback(FBObject):
    title: str
    url: AnyUrl
    payload: typing.Any = None
    type: str = 'fallback'


class Attachment(FBObject):
    type: str  # template, audio, fallback, file, image, location or video
    payload: typing.Union[MediaPayload, Coors, None]
