from telethon.tl.types import DocumentAttributeVideo
from telethon.tl.custom.message import Message
from telethon import events
from logging import Logger
import traceback
import shutil
import os

from helper import (
    get_logger,
    validate_config,
    progress_updater,
    progress_bar,
    get_duration,
    get_thumb,
    sanitize,
    has_any
)

from errors import StopWorkError
from FastTelethonhelper import fast_upload
from downloader import download
from database import db
from user import User

from config import (
    THUMBS_DIR, 
    VIDEOS_DIR
)

logger: Logger = get_logger(__name__)

from config import ALLOWED_CHATS

@events.register(events.MessageEdited(incoming=True))
@events.register(events.NewMessage(chats=ALLOWED_CHATS, incoming=True))
async def settings_handler(event: Message):
    logger.debug('Inside settings_handler')

    if not (not (event.media and event.document) and event.text):
        logger.debug('Event does not meets requirements of this_handler')
        return
    
    logger.debug('Event meets requirements of this handler')
    user: User = await db.get(event.sender_id)

    if not user.waiting_for_config:
        logger.debug('User is not waiting for config ...')
        return
        
    logger.debug('User is waiting for config ...')
    logger.debug('Validating config ...')

    reply: Message = await event.reply('Validating config ...')
    valid_config, fields = await validate_config(event.text, user)
    (start, stop), resolution, batch_name, credit_holder, thumb_id = fields

    if not valid_config:
        logger.debug('Config is invalid')
        await reply.edit(text='Config is invalid. Edit your message.')
        raise events.StopPropagation()
    
    logger.debug('Config is valid')
    user.working = True
    completed = failed = 0
    
    for count, (caption, link) in enumerate(user.links[start - 1: stop if stop else start], 1):
        try:
            count += start - 1
            caption = await sanitize(caption)
            template = f'Completed : {completed}\nFailed : {failed}\n\n{count}. {caption}\n\n{{}}'

            if user.stop_work:
                raise StopWorkError()
            
            logger.debug('Downloading ...')
            await reply.edit(template.format('Downloading ...'))
            file_path = await download(user, link, caption, resolution, reply, template, progress_updater)

            if not file_path:
                raise Exception('Download failed')
            
            logger.debug('Download completed')
            if user.stop_work:
                raise StopWorkError()

            if '.pdf' in file_path:
                logger.debug('Uploading pdf ...')
                await reply.edit(template.format('Uploading ...'))

                logger.debug('Uploading pdf file ...')
                uploaded_file = await fast_upload(
                    event.client, file_path,
                    progress_bar_function=progress_bar,
                    progress_args=(user, reply, template, progress_updater)
                )

            elif has_any(file_path, ('.mp4', '.mkv')):
                if thumb_id:
                    logger.debug('Using specified thumb ...')
                    thumb_path = os.path.join(THUMBS_DIR, f'thumb_{thumb_id}.jpg')
                else:
                    logger.debug('Getting thumb ...')
                    await reply.edit(template.format('Getting thumb ...'))
                    thumb_path = await get_thumb(file_path)                                   

                logger.debug('Uploading video file ...')
                await reply.edit(template.format('Uploading ...'))
                uploaded_file = await fast_upload(
                    event.client, file_path,
                    progress_bar_function=progress_bar,
                    progress_args=(user, reply, template, progress_updater)
                )
            else:
                logger.debug(f'File path : {file_path}')
                raise Exception('Downloaded file type is unknown')

            if not uploaded_file:
                raise Exception('Upload failed')

            logger.debug('Upload completed')
            await reply.edit(template.format('Sending ...'))

            if '.pdf' in file_path:
                await event.client.send_message(
                    await event.get_input_chat(), 
                    message = caption, file = uploaded_file
                )

            if has_any(file_path, ('.mp4', '.mkv')):
                attributes = (
                    DocumentAttributeVideo(
                    get_duration(file_path), 
                    320, 180,
                    supports_streaming=True),
                )
                await event.client.send_message(
                    await event.get_input_chat(), 
                    message = caption, file = uploaded_file,
                    thumb = thumb_path, attributes = attributes,
                    supports_streaming=True
                )
            completed += 1

        except StopWorkError:
            logger.warn('Handling StopWorkError ...')
            await reply.edit(template.format('Deleting file(s) ...'))

        except Exception as err:
            logger.warn(f'Error : {err}')
            traceback.print_exception(err)
            await reply.edit(template.format('Error occured. Skipping ...'))
            failed += 1

        finally:
            logger.debug('Deleting file(s) ...')
            user_dir = os.path.join(VIDEOS_DIR, str(user.id))

            if os.path.exists(user_dir):
                shutil.rmtree(user_dir)
            
            if user.stop_work:
                logger.debug('Discountinuing loop ...')
                break

            logger.debug(f'Completed : {completed} | Failed : {failed}')

    await reply.delete()
    logger.debug('Resetting user ...')

    user.working = False
    await event.reply(f'Completed : {completed}\nFailed : {failed}')
