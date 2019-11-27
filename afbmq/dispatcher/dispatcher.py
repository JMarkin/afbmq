import asyncio
import functools
import logging
import typing

from afbmq import types
from afbmq.dispatcher.filters import StateFilter, Command, Text, Regexp, \
    ExceptionsFilter, IDFilter, IsReplyFilter
from afbmq.types import Entry, MessageEvent
from .filters import FiltersFactory
from .handler import Handler
from .middlewares import MiddlewareManager
from .storage import DisabledStorage, FSMContext
from ..fb import FB
from ..utils.mixins import ContextInstanceMixin, DataMixin

MODE = 'MODE'
EVENT_OBJECT = 'event_object'

logger = logging.getLogger(__name__)


class Dispatcher(DataMixin, ContextInstanceMixin):
    def __init__(self, fb, storage=None, loop=None, filters_factory=None):
        if loop is None:
            loop = fb.loop or asyncio.get_event_loop()

        if storage is None:
            storage = DisabledStorage()

        if filters_factory is None:
            filters_factory = FiltersFactory(self)

        self.storage = storage or DisabledStorage()
        self.fb: FB = fb
        self.loop = loop
        self.run_tasks_by_default = True

        self.filters_factory: FiltersFactory = filters_factory
        self.events_handler = Handler(self, middleware_key='event')
        self.message_handlers = Handler(self, middleware_key='message')
        self.errors_handlers = Handler(self, once=False, middleware_key='error')

        self.middleware = MiddlewareManager(self)
        self.events_handler.register(self.process_event)

        self._closed = True
        self._close_waiter = loop.create_future()

        self._key = None
        self._server = None
        self._ts = None

        self._setup_filters()

    def _setup_filters(self):
        filters_factory = self.filters_factory

        filters_factory.bind(StateFilter, exclude_event_handlers=[
            self.errors_handlers,
        ])
        filters_factory.bind(Command, event_handlers=[
            self.message_handlers,
        ])
        filters_factory.bind(Text, event_handlers=[
            self.message_handlers,
        ])
        filters_factory.bind(Regexp, event_handlers=[
            self.message_handlers,
        ])
        filters_factory.bind(ExceptionsFilter, event_handlers=[
            self.errors_handlers,
        ])
        filters_factory.bind(IDFilter, event_handlers=[
            self.message_handlers,
        ])
        filters_factory.bind(IsReplyFilter, event_handlers=[
            self.message_handlers,
        ])

    async def process_entries(self, entries: typing.List[Entry]):
        """
        Process list of updates

        :param entries:
        :return:
        """
        tasks = []
        for entry in entries:
            event = entry.messaging[0]
            if isinstance(event, MessageEvent):
                tasks.append(self.events_handler.notify(event))
        return await asyncio.gather(*tasks)

    async def process_event(self, event):
        """
        Process single event object

        :param event:
        :return:
        """
        if isinstance(event, MessageEvent):
            types.Recipient.set_current(event.recipient)
            types.Sender.set_current(event.sender)
            return await self.message_handlers.notify(event, event.message)

    def register_message_handler(self, callback, *, commands=None, regexp=None, content_types=None, func=None,
                                 state=None, custom_filters=None, run_task=None, **kwargs):
        filters_set = self.filters_factory.resolve(self.message_handlers,
                                                   *custom_filters,
                                                   commands=commands,
                                                   regexp=regexp,
                                                   content_types=content_types,
                                                   state=state,
                                                   **kwargs)
        self.message_handlers.register(self._wrap_async_task(callback, run_task), filters_set)

    def message_handler(self, *custom_filters, commands=None, regexp=None, content_types=None, func=None, state=None,
                        run_task=None, **kwargs):

        def decorator(callback):
            self.register_message_handler(callback,
                                          commands=commands, regexp=regexp, content_types=content_types,
                                          func=func, state=state, custom_filters=custom_filters, run_task=run_task,
                                          **kwargs)
            return callback

        return decorator

    async def wait_closed(self):
        """
        Wait for the long-polling to close

        :return:
        """
        await asyncio.shield(self._close_waiter, loop=self.loop)

    def async_task(self, func):
        """
        Execute handler as task and return None.


        :param func:
        :return:
        """

        def process_response(task):
            try:
                task.result()

            except Exception as e:
                self.loop.create_task(
                    self.errors_handlers.notify(self, task.context.get(EVENT_OBJECT, None), e))

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            task = self.loop.create_task(func(*args, **kwargs))
            task.add_done_callback(process_response)

        return wrapper

    def _wrap_async_task(self, callback, run_task=None) -> callable:
        if run_task is None:
            run_task = self.run_tasks_by_default

        if run_task:
            return self.async_task(callback)
        return callback

    def current_state(self, *,
                      chat: typing.Union[str, int, None] = None,
                      user: typing.Union[str, int, None] = None) -> FSMContext:
        """
        Get current state for user in chat as context

        .. code-block:: python3

            with dp.current_state(chat=message.chat.id, user=message.user.id) as state:
                pass

            state = dp.current_state()
            state.set_state('my_state')

        :param chat:
        :param user:
        :return:
        """
        if chat is None:
            chat_obj = types.Recipient.get_current()
            chat = chat_obj.id if chat_obj else None
        if user is None:
            user_obj = types.Sender.get_current()
            user = user_obj.id if user_obj else None

        return FSMContext(storage=self.storage, chat=chat, user=user)
