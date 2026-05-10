import os


DS_API_KEY = os.getenv("DS_API_KEY", "")
DS_BASE_URL = os.getenv("DS_BASE_URL", "https://api.deepseek.com/v1")
DS_MODEL = os.getenv("DS_MODEL", "deepseek-chat")

LLM_ENABLED = bool(DS_API_KEY)