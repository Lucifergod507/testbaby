from dotenv import load_dotenv
from pathlib import Path
import os

if os.path.exists('.env'):
    load_dotenv(override=True)

API_ID = os.getenv('9407706')
API_HASH = os.getenv('0b75c89e269ad46f30bae2f13fd8c700')
BOT_TOKEN = os.getenv('7117076232:AAEgKgeGdCV3WagWTiZyWeT80aODTVEKZoY')
ALLOWED_CHATS = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHATS').split(' ')]

ASSETS_DIR = os.path.join(os.getcwd(), 'assets')
THUMBS_DIR = os.path.join(ASSETS_DIR, 'thumbs')
VIDEOS_DIR = os.path.join(ASSETS_DIR, 'videos')

Path(ASSETS_DIR).mkdir(exist_ok=True)
Path(THUMBS_DIR).mkdir(exist_ok=True)
Path(VIDEOS_DIR).mkdir(exist_ok=True)

EDIT_INTERVAL = 5
