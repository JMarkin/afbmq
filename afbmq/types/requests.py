import typing

from pydantic.types import constr

from .attachment import Attachment
from .base import FBObject


class RecipientRequest(FBObject):
    id: typing.Optional[str] = None
    user_ref: typing.Optional[str] = None
    post_id: typing.Optional[str] = None
    comment_id: typing.Optional[str] = None


class QuickReply(FBObject):
    content_type: str  # text, user_phone_number, user_email
    title: constr(max_length=20)
    image_url: typing.Optional[str] = None
    payload: typing.Optional[str] = None


class MessageRequest(FBObject):
    text: str
    attachment: typing.Optional[Attachment] = None
    quick_replies: typing.Optional[typing.List[QuickReply]] = None
    metadata: typing.Optional[str] = None
