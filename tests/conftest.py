"""Test configuration: provide dummy credentials before importing the bot."""

import os

os.environ.setdefault("API_ID", "12345")
os.environ.setdefault("API_HASH", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("BOT_TOKEN", "123456:dummy-token")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("OWNER_ID", "111")
os.environ.setdefault("ADMIN_IDS", "222,333")
