from .base import FBObject


class MessageResponse(FBObject):
    recipient_id: str
    message_id: str
