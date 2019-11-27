import asyncio
import ipaddress
import logging

from aiohttp import web
from aiohttp.web_exceptions import HTTPGone

from afbmq import FB
from afbmq.dispatcher import Dispatcher
from afbmq.types import WebhookEvent
from afbmq.utils import context

logger = logging.getLogger(__name__)

DEFAULT_WEB_PATH = '/webhook'
DEFAULT_ROUTE_NAME = 'webhook_handler'
FB_DISPATCHER_KEY = 'FB_DISPATCHER'

RESPONSE_TIMEOUT = 55

WEBHOOK = 'webhook'
WEBHOOK_CONNECTION = 'WEBHOOK_CONNECTION'
WEBHOOK_REQUEST = 'WEBHOOK_REQUEST'

# IP filter
allowed_ips = set()


def _check_ip(ip: str) -> bool:
    """ Check IP in range. """
    # address = ipaddress.IPv4Address(ip)
    # return address in allowed_ips
    # todo add fb ip
    return True


def allow_ip(*ips: str):
    """ Allow ip address. """
    allowed_ips.update(ipaddress.IPv4Address(ip) for ip in ips)


class WebhookRequestHandler(web.View):
    """
    Simple Webhook request handler for aiohttp web server.

    You need to register that in app:

    .. code-block:: python3

        app.router.add_route('*', '/your/webhook/path', WebhookRequestHadler, name='webhook_handler')

    But first you need to configure application for getting Dispatcher instance from request handler!
    It must always be with key 'VK_DISPATCHER'

    .. code-block:: python3

        fb = FB(TOKEN, loop)
        dp = Dispatcher(fb)
        app['VK_DISPATCHER'] = dp

    """

    def get_dispatcher(self):
        """
        Get Dispatcher instance from environment

        :return: :class:`afbmq.Dispatcher`
        """
        dp = self.request.app[FB_DISPATCHER_KEY]
        try:
            Dispatcher.set_current(dp)
            FB.set_current(dp.fb)

        except RuntimeError:
            pass

        return dp

    async def parse_event(self, fb):
        """
        Read update from stream and deserialize it.

        :param fb: FB instance. You an get it from Dispatcher
        :return: :class:`afbmq.types.Update`
        """
        data = await self.request.json()
        logger.debug(f'Received request: {self.request} {data}')

        event = WebhookEvent(**data)
        logger.debug(f'New event: {event}')
        return event.entry

    async def post(self):
        """ Process POST request """
        self.validate_ip()

        context.update_state({'CALLER': WEBHOOK,
                              WEBHOOK_CONNECTION: True,
                              WEBHOOK_REQUEST: self.request})

        dispatcher = self.get_dispatcher()
        entries = await self.parse_event(dispatcher.fb)

        asyncio.ensure_future(dispatcher.process_entries(entries))
        return web.Response(text='ok')

    async def get(self):
        self.validate_ip()

        dispatcher = self.get_dispatcher()

        mode = self.request.query.get('hub.mode')
        token = self.request.query.get('hub.verify_token')
        challenge = self.request.query.get('hub.challenge')
        if mode == 'subscribe' and token == dispatcher.fb.confirmation_code:
            return web.Response(text=challenge, status=200)

        return web.Response(status=403)

    async def head(self):
        self.validate_ip()
        return web.Response(text='')

    def check_ip(self):
        """
        Check client IP. Accept requests only from FB servers.

        :return:
        """
        # For reverse proxy (nginx)
        forwarded_for = self.request.headers.get('X-Forwarded-For', None)
        if forwarded_for:
            return forwarded_for, _check_ip(forwarded_for)

        # For default method
        peer_name = self.request.transport.get_extra_info('peername')
        if peer_name is not None:
            host, _ = peer_name
            return host, _check_ip(host)

        # Not allowed and can't get client IP
        return None, False

    def validate_ip(self):
        """
        Check ip if that is needed. Raise web.HTTPUnauthorized for not allowed hosts.
        """
        if self.request.app.get('_check_ip', False):
            ip_address, accept = self.check_ip()
            if not accept:
                raise web.HTTPUnauthorized()


class GoneRequestHandler(web.View):
    """
    If a webhook returns the HTTP error 410 Gone for all requests for more than 23 hours successively,
    it can be automatically removed.
    """

    async def get(self):
        raise HTTPGone()

    async def post(self):
        raise HTTPGone()


def get_new_configured_app(dispatcher, path=DEFAULT_WEB_PATH):
    """
    Create new :class:`aiohttp.web.Application` and configure it.

    :param dispatcher: Dispatcher instance
    :param path: Path to your webhook.
    :return:
    """
    app = web.Application()
    configure_app(dispatcher, app, path)
    return app


def configure_app(dispatcher, app: web.Application, path=DEFAULT_WEB_PATH):
    """
    You can prepare web.Application for working with webhook handler.

    :param dispatcher: Dispatcher instance
    :param app: :class:`aiohttp.web.Application`
    :param path: Path to your webhook.
    :return:
    """
    app.router.add_route('*', path, WebhookRequestHandler, name='webhook_handler')
    app[FB_DISPATCHER_KEY] = dispatcher
