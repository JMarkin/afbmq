import asyncio
import logging

import config
from afbmq import FB
from afbmq.dispatcher import Dispatcher
from afbmq.types import Event, RecipientRequest, MessageRequest
from afbmq.types.message import Message

logging.basicConfig(level=logging.INFO)

loop = asyncio.get_event_loop()
fb = FB(confirmation_code=config.FB_CONFIRMATION_CODE,
        access_token=config.FB_ACCESS_TOKEN,
        loop=loop)
dp = Dispatcher(fb, loop=loop)


@dp.message_handler()
async def echo_handler(event: Event, message: Message):
    await message.send_message(RecipientRequest(id=event.sender.id), message=MessageRequest(text=message.text))


async def shutdown(_):
    await fb.close()
    await asyncio.sleep(0.250)


if __name__ == '__main__':
    from afbmq.utils.executor import start_webhook

    start_webhook(dispatcher=dp, webhook_path=config.WEBHOOK_PATH,
                  host=config.WEBAPP_HOST, port=config.WEBAPP_PORT,
                  on_shutdown=shutdown)
