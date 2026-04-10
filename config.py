import os
from dotenv import load_dotenv
load_dotenv()


CAPITAL       = 25000
MAX_RISK_PCT  = 0.02
MIN_RR        = 2.0
MAX_POSITIONS = 3
MACRO_EVENT_BUFFER_H = 2
TIE_THRESHOLD = 5

GOLDAPI_KEY      = os.getenv("GOLDAPI_KEY", "")
FRED_KEY         = os.getenv("FRED_KEY", "")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
OPENAI_KEY       = os.getenv("OPENAI_API_KEY", "")
NEWSAPI_KEY      = os.getenv("NEWSAPI_KEY", "")
ALPHAVANTAGE_KEY = os.getenv("ALPHAVANTAGE_KEY", "")

STATE_DIR     = "state"
LOG_DIR       = "logs"
DASH_DIR      = "dashboard"
