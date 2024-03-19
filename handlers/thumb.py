from telethon.tl.custom.message import Message
from telethon import events
from logging import Logger
import os

from helper import get_logger
from helper import datetime_stamp
from config import THUMBS_DIR

logger: Logger = get_logger(__name__)

from config import ALLOWED_CHATS

@events.register(events.NewMessage(chats=ALLOWED_CHATS, incoming=True))
async def photo_handler(event: Message) -> None:
    logger.debug('Inside photo_handler')

    if not hasattr(event.media, 'photo'):
        logger.debug('Event does not meets requirements of this_handler')
        return
    
    logger.debug('Event meets requirements of this handler')
    reply: Message = await event.reply('Downloading ...')

    thumb_id = datetime_stamp()
    logger.debug(f'Thumb ID : {thumb_id}')

    file_path = os.path.join(THUMBS_DIR, f'thumb_{thumb_id}.jpg')
    await event.download_media(file=file_path)
    await reply.edit(f'Your thumbnail ID : `{thumb_id}`')

    raise events.StopPropagation()