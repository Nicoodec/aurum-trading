# config.py — AURUM Trading System
import os
from dotenv import load_dotenv
load_dotenv()

OLLAMA_BASE = 'http://localhost:11434'
MODEL_HEAVY = 'qwen3:latest'
MODEL_LIGHT = 'glm4:9b'

CAPITAL = 10000
MAX_RISK_PCT = 0.02
MIN_RR = 2.0
MAX_POSITIONS = 3
MACRO_EVENT_BUFFER_H = 2

GOLDAPI_KEY = os.getenv('GOLDAPI_KEY', '')
FRED_KEY    = os.getenv('FRED_KEY', '')

STATE_DIR   = 'state'
LOG_DIR     = 'logs'
DASH_DIR    = 'dashboard'

DEBATE_ROUNDS = 3
