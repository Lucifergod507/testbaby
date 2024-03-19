from telethon.tl.custom.message import Message
from telethon import events
from logging import Logger
import re

from helper import get_logger
from database import db
from user import User

logger: Logger = get_logger(__name__)

from config import ALLOWED_CHATS

@events.register(events.NewMessage(chats=ALLOWED_CHATS, incoming=True))
async def doc_handler(event: Message):
    logger.debug('Inside doc_handler')

    if not (hasattr(event.document, 'mime_type') and event.document.mime_type == 'text/plain'):
        logger.debug('Event does not meets requirements of this_handler')
        return
    
    logger.debug('Event meets requirements of this handler')
    user: User = await db.get(event.sender_id)

    if user.working:
        logger.debug('User is working ...')
        await event.reply('There is already an ongoing task. Cancel it first.')
        raise events.StopPropagation()

    logger.debug('User is not working ...')
    logger.debug('Processing document ...')

    reply: Message = await event.reply('Downloading ...')
    file_bytes: bytes = await event.download_media(file=bytes)
    await reply.edit(text='Reading ...')

    links = []
    pattern = '\s*(.*?(?=\s*:))\s*:\s*(?=https?)([^\s]*)'

    for line in file_bytes.decode().strip('\n').split('\n'):
        match = re.search(pattern, line)
        if match:
            links.append(match.groups())

    if not links:
        logger.debug('No link(s) found')
        await reply.edit('No link(s) found')
        raise events.StopPropagation()

    logger.debug(f'Found {len(links)} link(s)')
    user.links = links

    reply_text = ''.join([
        f'Found {len(links)} link(s). Send your config in following format : \n',
        '------------------------------\n'
        'Download range * \n',
        'Video resolution \n',
        'Batch Name       \n',
        'Credit holder    \n',
        'Thumbnail ID     \n',
        '------------------------------\n'
        'Leave the line empty to skip a field. All fields are optional except *'
    ])  

    await reply.edit(text=reply_text)
    user.waiting_for_config = True
    raise events.StopPropagation()
