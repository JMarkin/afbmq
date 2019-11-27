import typing

from afbmq import types
from afbmq.utils.payload import generate_payload
from .attachment import Attachment, AttachmentFallback
from .base import FBObject
from .exceptions import FBException
from .requests import RecipientRequest, MessageRequest
from .responses import MessageResponse


class QuickReply(FBObject):
    payload: str


class ReplyTo(FBObject):
    mid: str


AttachType = typing.TypeVar('AttachType', Attachment, AttachmentFallback)


class Message(FBObject):
    mid: str
    text: str
    attachments: typing.Optional[typing.List[AttachType]]
    quick_reply: typing.Optional[QuickReply]
    reply_to: typing.Optional[ReplyTo]

    async def send_message(self, recipient: RecipientRequest, message: MessageRequest = None,
                           sender_action: str = None,
                           notification_type: str = None,
                           tag: str = None,
                           messaging_type: str = 'RESPONSE') -> MessageResponse:

        if message is not None and sender_action is not None:
            raise FBException('sender_action cannot be sent with message. Must be sent as a separate request.')

        if sender_action is not None and [key for key in locals().keys() if key is not None] != ['sender_action',
                                                                                                 'recipient']:
            raise FBException(
                'When using sender_action, recipient should be the only other property set in the request.')

        payload = generate_payload(**locals())

        result = await self.fb.api_request('/me/messages', payload)
        return types.MessageResponse(**result)
