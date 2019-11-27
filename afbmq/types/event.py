import typing
from datetime import datetime

from afbmq.types import Message
from .base import FBObject


class Sender(FBObject):
    id: str


class Recipient(FBObject):
    id: str


class Event(FBObject):
    sender: Sender
    recipient: Recipient
    timestamp: datetime


class MessageEvent(Event):
    message: Message


class Entry(FBObject):
    id: str
    time: datetime
    messaging: typing.List[typing.Union[None, MessageEvent]]


class WebhookEvent(FBObject):
    object: str
    entry: typing.List[Entry]
