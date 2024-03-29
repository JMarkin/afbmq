import inspect
import re
import typing
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Union

from babel.support import LazyProxy

from afbmq import types
from afbmq.dispatcher.filters.filters import BoundFilter, Filter
from afbmq.types import MessageEvent, Event


class Command(Filter):
    """
    You can handle commands by using this filter.

    If filter is successful processed the :obj:`Command.CommandObj` will be passed to the handler arguments.

    By default this filter is registered for messages and edited messages handlers.
    """

    def __init__(self, commands: Union[Iterable, str],
                 prefixes: Union[Iterable, str] = '/',
                 ignore_case: bool = True,
                 ignore_mention: bool = False):
        """
        Filter can be initialized from filters factory or by simply creating instance of this class.

        Examples:

        .. code-block:: python

            @dp.message_handler(commands=['myCommand'])
            @dp.message_handler(Command(['myCommand']))
            @dp.message_handler(commands=['myCommand'], commands_prefix='!/')

        :param commands: Command or list of commands always without leading slashes (prefix)
        :param prefixes: Allowed commands prefix. By default is slash.
            If you change the default behavior pass the list of prefixes to this argument.
        :param ignore_case: Ignore case of the command
        :param ignore_mention: Ignore mention in command
            (By default this filter pass only the commands addressed to current fb)
        """
        if isinstance(commands, str):
            commands = (commands,)

        self.commands = list(map(str.lower, commands)) if ignore_case else commands
        self.prefixes = prefixes
        self.ignore_case = ignore_case
        self.ignore_mention = ignore_mention

    @classmethod
    def validate(cls, full_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validator for filters factory

        From filters factory this filter can be registered with arguments:

         - ``command``
         - ``commands_prefix`` (will be passed as ``prefixes``)
         - ``commands_ignore_mention`` (will be passed as ``ignore_mention``

        :param full_config:
        :return: config or empty dict
        """
        config = {}
        if 'commands' in full_config:
            config['commands'] = full_config.pop('commands')
        if config and 'commands_prefix' in full_config:
            config['prefixes'] = full_config.pop('commands_prefix')
        if config and 'commands_ignore_mention' in full_config:
            config['ignore_mention'] = full_config.pop('commands_ignore_mention')
        return config

    async def check(self, event: types.MessageEvent, message: types.Message):
        return await self.check_command(message, self.commands, self.prefixes, self.ignore_case, self.ignore_mention)

    @staticmethod
    async def check_command(message: types.Message, commands, prefixes, ignore_case=True, ignore_mention=False):
        if not message.text:  # Prevent to use with non-text content types
            return False

        full_command = message.text.split()[0]
        prefix, (command, _, mention) = full_command[0], full_command[1:].partition('@')

        if not ignore_mention and mention and (await message.fb.me).username.lower() != mention.lower():
            return False
        if prefix not in prefixes:
            return False
        if (command.lower() if ignore_case else command) not in commands:
            return False

        return {'command': Command.CommandObj(command=command, prefix=prefix, mention=mention)}

    @dataclass
    class CommandObj:
        """
        Instance of this object is always has command and it prefix.

        Can be passed as keyword argument ``command`` to the handler
        """

        """Command prefix"""
        prefix: str = '/'
        """Command without prefix and mention"""
        command: str = ''
        """Mention (if available)"""
        mention: str = None
        """Command argument"""
        args: str = field(repr=False, default=None)

        @property
        def mentioned(self) -> bool:
            """
            This command has mention?

            :return:
            """
            return bool(self.mention)

        @property
        def text(self) -> str:
            """
            Generate original text from object

            :return:
            """
            line = self.prefix + self.command
            if self.mentioned:
                line += '@' + self.mention
            if self.args:
                line += ' ' + self.args
            return line


class CommandStart(Command):
    """
    This filter based on :obj:`Command` filter but can handle only ``/start`` command.
    """

    def __init__(self, deep_link: typing.Optional[typing.Union[str, re.Pattern]] = None):
        """
        Also this filter can handle `deep-linking <https://core.telegram.org/bots#deep-linking>`_ arguments.

        Example:

        .. code-block:: python

            @dp.message_handler(CommandStart(re.compile(r'ref-([\\d]+)')))

        :param deep_link: string or compiled regular expression (by ``re.compile(...)``).
        """
        super().__init__(['start'])
        self.deep_link = deep_link

    async def check(self, event: types.MessageEvent, message: types.Message):
        """
        If deep-linking is passed to the filter result of the matching will be passed as ``deep_link`` to the handler

        :param event:
        :param message:
        :return:
        """
        check = await super().check(event, message)

        if check and self.deep_link is not None:
            if not isinstance(self.deep_link, re.Pattern):
                return message.get_args() == self.deep_link

            match = self.deep_link.match(message.get_args())
            if match:
                return {'deep_link': match}
            return False

        return check


class CommandHelp(Command):
    """
    This filter based on :obj:`Command` filter but can handle only ``/help`` command.
    """

    def __init__(self):
        super().__init__(['help'])


class CommandSettings(Command):
    """
    This filter based on :obj:`Command` filter but can handle only ``/settings`` command.
    """

    def __init__(self):
        super().__init__(['settings'])


class CommandPrivacy(Command):
    """
    This filter based on :obj:`Command` filter but can handle only ``/privacy`` command.
    """

    def __init__(self):
        super().__init__(['privacy'])


class Text(Filter):
    """
    Simple text filter
    """

    _default_params = (
        ('text', 'equals'),
        ('text_contains', 'contains'),
        ('text_startswith', 'startswith'),
        ('text_endswith', 'endswith'),
    )

    def __init__(self,
                 equals: Optional[Union[str, LazyProxy, Iterable[Union[str, LazyProxy]]]] = None,
                 contains: Optional[Union[str, LazyProxy, Iterable[Union[str, LazyProxy]]]] = None,
                 startswith: Optional[Union[str, LazyProxy, Iterable[Union[str, LazyProxy]]]] = None,
                 endswith: Optional[Union[str, LazyProxy, Iterable[Union[str, LazyProxy]]]] = None,
                 ignore_case=False):
        """
        Check text for one of pattern. Only one mode can be used in one filter.
        In every pattern, a single string is treated as a list with 1 element.

        :param equals: True if object's text in the list
        :param contains: True if object's text contains all strings from the list
        :param startswith: True if object's text starts with any of strings from the list
        :param endswith: True if object's text ends with any of strings from the list
        :param ignore_case: case insensitive
        """
        # Only one mode can be used. check it.
        check = sum(map(lambda s: s is not None, (equals, contains, startswith, endswith)))
        if check > 1:
            args = "' and '".join([arg[0] for arg in [('equals', equals),
                                                      ('contains', contains),
                                                      ('startswith', startswith),
                                                      ('endswith', endswith)
                                                      ] if arg[1] is not None])
            raise ValueError(f"Arguments '{args}' cannot be used together.")
        elif check == 0:
            raise ValueError(f"No one mode is specified!")

        equals, contains, endswith, startswith = map(lambda e: [e] if isinstance(e, str) or isinstance(e, LazyProxy)
        else e,
                                                     (equals, contains, endswith, startswith))
        self.equals = equals
        self.contains = contains
        self.endswith = endswith
        self.startswith = startswith
        self.ignore_case = ignore_case

    @classmethod
    def validate(cls, full_config: Dict[str, Any]):
        for param, key in cls._default_params:
            if param in full_config:
                return {key: full_config.pop(param)}

    async def check(self, event: Union[types.MessageEvent], obj: Union[types.Message]):
        if isinstance(event, MessageEvent):
            text = obj.text
        else:
            return False
        if self.ignore_case:
            text = text.lower()
            _pre_process_func = lambda s: str(s).lower()
        else:
            _pre_process_func = str

        # now check
        if self.equals is not None:
            equals = list(map(_pre_process_func, self.equals))
            return text in equals

        if self.contains is not None:
            contains = list(map(_pre_process_func, self.contains))
            return all(map(text.__contains__, contains))

        if self.startswith is not None:
            startswith = list(map(_pre_process_func, self.startswith))
            return any(map(text.startswith, startswith))

        if self.endswith is not None:
            endswith = list(map(_pre_process_func, self.endswith))
            return any(map(text.endswith, endswith))

        return False


class Regexp(Filter):
    """
    Regexp filter for messages and callback query
    """

    def __init__(self, regexp):
        if not isinstance(regexp, re.Pattern):
            regexp = re.compile(regexp, flags=re.IGNORECASE | re.MULTILINE)
        self.regexp = regexp

    @classmethod
    def validate(cls, full_config: Dict[str, Any]):
        if 'regexp' in full_config:
            return {'regexp': full_config.pop('regexp')}

    async def check(self, event: Union[MessageEvent], obj: Union[types.Message]):
        if isinstance(event, MessageEvent):
            content = obj.text
        else:
            return False

        match = self.regexp.search(content)

        if match:
            return {'regexp': match}
        return False


class StateFilter(BoundFilter):
    """
    Check user state
    """
    key = 'state'
    required = True

    ctx_state = ContextVar('user_state')

    def __init__(self, dispatcher, state):
        from afbmq.dispatcher.filters.state import State, StatesGroup

        self.dispatcher = dispatcher
        states = []
        if not isinstance(state, (list, set, tuple, frozenset)) or state is None:
            state = [state, ]
        for item in state:
            if isinstance(item, State):
                states.append(item.state)
            elif inspect.isclass(item) and issubclass(item, StatesGroup):
                states.extend(item.all_states_names)
            else:
                states.append(item)
        self.states = states

    def get_target(self, obj):
        return getattr(getattr(obj, 'recipient', None), 'id', None), getattr(getattr(obj, 'sender', None), 'id', None)

    async def check(self, event: Event, obj):
        if '*' in self.states:
            return {'state': self.dispatcher.current_state()}

        try:
            state = self.ctx_state.get()
        except LookupError:
            chat, user = self.get_target(event)
            if chat or user:
                state = await self.dispatcher.storage.get_state(chat=chat, user=user)
                self.ctx_state.set(state)
                if state in self.states:
                    return {'state': self.dispatcher.current_state(), 'raw_state': state}

        else:
            if state in self.states:
                return {'state': self.dispatcher.current_state(), 'raw_state': state}

        return False


class ExceptionsFilter(BoundFilter):
    """
    Filter for exceptions
    """

    key = 'exception'

    def __init__(self, exception):
        self.exception = exception

    async def check(self, update, exception):
        try:
            raise exception
        except self.exception:
            return True
        except:
            return False


class IDFilter(Filter):

    def __init__(self,
                 user_id: Optional[Union[Iterable[Union[int, str]], str, int]] = None,
                 chat_id: Optional[Union[Iterable[Union[int, str]], str, int]] = None,
                 ):
        """
        :param user_id:
        :param chat_id:
        """
        if user_id is None and chat_id is None:
            raise ValueError("Both user_id and chat_id can't be None")

        self.user_id = None
        self.chat_id = None
        if user_id:
            if isinstance(user_id, Iterable):
                self.user_id = list(map(int, user_id))
            else:
                self.user_id = [int(user_id), ]
        if chat_id:
            if isinstance(chat_id, Iterable):
                self.chat_id = list(map(int, chat_id))
            else:
                self.chat_id = [int(chat_id), ]

    @classmethod
    def validate(cls, full_config: typing.Dict[str, typing.Any]) -> typing.Optional[typing.Dict[str, typing.Any]]:
        result = {}
        if 'user_id' in full_config:
            result['user_id'] = full_config.pop('user_id')

        if 'chat_id' in full_config:
            result['chat_id'] = full_config.pop('chat_id')

        return result

    async def check(self, event: Union[Event], obj: Union[types.Message]):
        if isinstance(event, Event):
            user_id = event.sender.id
            chat_id = event.recipient.id
        else:
            return False

        if self.user_id and self.chat_id:
            return user_id in self.user_id and chat_id in self.chat_id
        if self.user_id:
            return user_id in self.user_id
        if self.chat_id:
            return chat_id in self.chat_id

        return False


class IsReplyFilter(BoundFilter):
    """
    Check if message is replied and send reply message to handler
    """
    key = 'is_reply'

    def __init__(self, is_reply):
        self.is_reply = is_reply

    async def check(self, event: Union[types.MessageEvent], msg: Union[types.Message]):
        if msg.reply_to and self.is_reply:
            return {'reply': msg.reply_to}
        elif not msg.reply_to and not self.is_reply:
            return True
