from pydantic import BaseModel

from afbmq import FB
from afbmq.utils.mixins import ContextInstanceMixin


class FBObject(BaseModel, ContextInstanceMixin):
    @property
    def fb(self) -> FB:
        from ..fb import FB

        fb = FB.get_current()
        if fb is None:
            raise RuntimeError("Can't get fb instance from context. "
                               "You can fix it with setting current instance: "
                               "'fb.set_current(bot_instance)'")
        return fb
