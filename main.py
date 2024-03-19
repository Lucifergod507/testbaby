from telethon import TelegramClient
from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN
)

from handlers.start    import start_handler
from handlers.cancel   import cancel_handler

from handlers.thumb    import photo_handler
from handlers.text     import doc_handler

from handlers.settings import settings_handler

client = TelegramClient('txt-uploader-v2', API_ID, API_HASH)

client.add_event_handler(start_handler)
client.add_event_handler(cancel_handler)

client.add_event_handler(photo_handler)
client.add_event_handler(doc_handler)

client.add_event_handler(settings_handler)

client.start(bot_token=BOT_TOKEN)
client.run_until_disconnected()
