import os

from dotenv import load_dotenv

load_dotenv()

DS_API_KEY = os.getenv("DS_API_KEY", "")
DS_BASE_URL = os.getenv("DS_BASE_URL", "https://api.deepseek.com/v1")
DS_MODEL = os.getenv("DS_MODEL", "deepseek-chat")

AMAP_API_KEY = os.getenv("AMAP_API_KEY", "be616a117317f7fbaa40f8109a311488")

LLM_ENABLED = bool(DS_API_KEY)
AMAP_ENABLED = bool(AMAP_API_KEY)
