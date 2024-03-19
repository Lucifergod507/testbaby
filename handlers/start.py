from telethon.tl.custom.message import Message
from telethon import events
from logger import get_logger

logger = get_logger(__name__)

from config import ALLOWED_CHATS

@events.register(events.NewMessage(chats=ALLOWED_CHATS, incoming=True, pattern='^/(start|help)$'))
async def start_handler(event: Message) -> None:
    logger.debug('Inside start_handler')
    await event.reply('Send a text file containing links to download. Each line one link in following format <name>:<link>')
    raise events.StopPropagation()
