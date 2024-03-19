from telethon.tl.custom.message import Message
from telethon import events
import asyncio

from helper import get_logger
from database import db
from user import User

logger = get_logger(__name__)

from config import ALLOWED_CHATS

@events.register(events.NewMessage(chats=ALLOWED_CHATS, incoming=True, pattern='^/cancel$'))
async def cancel_handler(event: Message) -> None:
    logger.debug('Inside cancel_hanlder')
    user: User = await db.get(event.sender_id)

    if not user.working:
        logger.debug('User is not working ...')
        await event.reply('No active task to cancel')
        user.waiting_for_config = False
        raise events.StopPropagation()

    logger.debug('User is working ...')
    logger.debug('Sending stop signal ...')

    reply: Message = await event.reply('Cancelling ...')
    user.stop_work = True

    sec = 0
    while user.working:
        logger.debug(f'Waiting for working status to change ... ({sec}s)')
        await asyncio.sleep(1)
        sec += 1

    logger.debug('Work stopped successfully')
    await reply.edit('Task cancelled successfully')
    
    user.stop_work = False
    user.waiting_for_config = False
    raise events.StopPropagation()
