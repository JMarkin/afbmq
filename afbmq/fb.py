from __future__ import annotations

import asyncio
import contextlib
import logging
import ssl
import typing
from contextvars import ContextVar

import aiohttp
import certifi
from aiohttp import ClientSession
from aiohttp.helpers import sentinel

from .utils import json
from .utils.mixins import DataMixin, ContextInstanceMixin

logger = logging.getLogger(__name__)

API_URL = 'https://graph.facebook.com'


class FB(DataMixin, ContextInstanceMixin):
    _ctx_timeout = ContextVar('FBRequestTimeout')

    def __init__(self, confirmation_code=None, access_token=None, loop=None):
        """
        :type confirmation_code: str
        """
        self.confirmation_code = confirmation_code
        self.access_token = access_token
        self.api_version = '5.0'

        # asyncio loop instance
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.connector = aiohttp.TCPConnector(ssl_context=ssl_context, loop=self.loop)
        self._session = ClientSession(loop=self.loop, json_serialize=json.dumps, connector=self.connector)

        # methods
        _data = {'access_token': access_token, 'session': self._session, 'api_version': self.api_version}

    @property
    def session(self):
        if not self._session:
            self._session = ClientSession(loop=self.loop, json_serialize=json.dumps, connector=self.connector)
        return self._session

    async def api_request(self, method_name, parameters):

        link = f'{API_URL}/v{self.api_version}/{method_name}?access_token={self.access_token}'
        async with self.session.post(link, json=parameters) as resp:
            status = resp.status
            text = await resp.text()
            logger.info(f'Response: {status}, {text}')
        try:
            result_json = json.loads(text)
        except ValueError:
            result_json = {}
        return result_json

    async def close(self):
        if isinstance(self._session, ClientSession) and not self._session.closed:
            await self._session.close()

    @staticmethod
    def _prepare_timeout(
        value: typing.Optional[typing.Union[int, float, aiohttp.ClientTimeout]]
    ) -> typing.Optional[aiohttp.ClientTimeout]:
        if value is None or isinstance(value, aiohttp.ClientTimeout):
            return value
        return aiohttp.ClientTimeout(total=value)

    @property
    def timeout(self):
        timeout = self._ctx_timeout.get(self._timeout)
        if timeout is None:
            return sentinel
        return timeout

    @timeout.setter
    def timeout(self, value):
        self._timeout = self._prepare_timeout(value)

    @timeout.deleter
    def timeout(self):
        self.timeout = None

    @contextlib.contextmanager
    def request_timeout(self, timeout: typing.Union[int, float, aiohttp.ClientTimeout]):
        """
        Context manager implements opportunity to change request timeout in current context

        :param timeout: Request timeout
        :type timeout: :obj:`typing.Optional[typing.Union[base.Integer, base.Float, aiohttp.ClientTimeout]]`
        :return:
        """
        timeout = self._prepare_timeout(timeout)
        token = self._ctx_timeout.set(timeout)
        try:
            yield
        finally:
            self._ctx_timeout.reset(token)
