import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
MONGO_URL = os.getenv("MONGO_URL")
LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", 0))
CHANNEL_1 = os.getenv("CHANNEL_1")
CHANNEL_2 = os.getenv("CHANNEL_2")
WELCOME_IMG = os.getenv("WELCOME_IMG")
OWNER_ID = int(os.getenv("OWNER_ID", 8241087790))
