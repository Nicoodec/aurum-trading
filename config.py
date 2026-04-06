# config.py — AURUM Trading System
import os

OLLAMA_BASE = 'http://localhost:11434'
MODEL_HEAVY = 'qwen3.5:latest'      # razonamiento, debate
MODEL_LIGHT = 'glm-4.7-flash:latest' # JSON, cálculos, estructurado

CAPITAL = 10000        # capital paper trading en USD
MAX_RISK_PCT = 0.02    # 2% máximo por operación
MIN_RR = 2.0           # R:R mínimo 1:2
MAX_POSITIONS = 3      # máximo posiciones simultáneas
MACRO_EVENT_BUFFER_H = 2  # horas buffer antes de evento macro

GOLDAPI_KEY = os.getenv('GOLDAPI_KEY', '')  # goldapi.io tier gratuito
FRED_KEY    = os.getenv('FRED_KEY', '')     # FRED API gratuita

STATE_DIR   = 'state'
LOG_DIR     = 'logs'
DASH_DIR    = 'dashboard'

DEBATE_ROUNDS = 3
