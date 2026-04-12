"""
AURUM Telegram Alerts -- Mensajes personalizados generados por GPT
===================================================================
GPT-4o redacta cada mensaje en lenguaje natural explicando:
- Qué ha detectado el sistema
- Por qué ha tomado esa decision
- Qué significa para la cuenta FTMO
- Qué hay que vigilar
"""

import os
import requests
from datetime import datetime, timezone

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN",   "8745728388:AAFkfd5-zJcbNDC3lewR4mRwyOb8g8k3rig")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "967115673")
OPENAI_KEY       = os.getenv("OPENAI_API_KEY",   "")


# ──────────────────────────────────────────────
# SEND RAW MESSAGE
# ──────────────────────────────────────────────

def send(msg: str):
    """Envía un mensaje raw a Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[telegram] No credentials")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       msg,
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception as e:
        print("[telegram] send error:", e)


# ──────────────────────────────────────────────
# GPT MESSAGE WRITER
# ──────────────────────────────────────────────

def _gpt_write(system: str, user: str, max_tokens=300) -> str:
    """Llama a GPT-4o para redactar un mensaje en lenguaje natural."""
    if not OPENAI_KEY:
        return ""
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                "temperature": 0.7,
                "max_tokens":  max_tokens,
            },
            timeout=20,
        )
        data = r.json()
        if "error" in data:
            return ""
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("[telegram] GPT write error:", e)
        return ""


def _now_utc() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%H:%M UTC")


# ──────────────────────────────────────────────
# ALERT: ORDEN EJECUTADA
# ──────────────────────────────────────────────

def alert_order_placed(signal, gpt_result, lots, entry, sl, tp, risk_usd, account):
    """Alerta cuando se abre una orden en MT5."""
    direction  = signal.get("signal", "--")
    price      = signal.get("price", 0)
    adx        = signal.get("adx", "--")
    rsi        = signal.get("rsi", "--")
    atr        = signal.get("atr", "--")
    sl_dist    = signal.get("sl_dist", "--")
    tp_dist    = signal.get("tp_dist", "--")
    rr         = signal.get("rr", "--")
    e50        = signal.get("e50", "--")
    trend_ema  = signal.get("trend_ema", "--")
    gpt_reason = gpt_result.get("reason", "--")
    gpt_conf   = gpt_result.get("confidence", 0)
    balance    = account.get("balance", 25000) if account else 25000
    equity     = account.get("equity",  25000) if account else 25000
    dd         = round(25000 - equity, 2)

    system = """Eres el sistema de trading AURUM. Acabas de abrir una orden en US30 (Dow Jones) en una cuenta FTMO de $25,000.
Escribe un mensaje de Telegram en español, breve (máximo 200 palabras), directo y profesional.
Explica en lenguaje humano: qué señal detectaste, por qué decidiste entrar, qué esperas que pase, y cuál es el riesgo.
Usa emojis con moderación. NO uses markdown complejo. Sé conciso pero informativo.
El tono es el de un trader profesional explicando su posición a un colega."""

    user = f"""Se acaba de abrir esta orden:
Instrumento: US30.cash (Dow Jones)
Dirección: {direction}
Entrada: {entry:.0f} pts
SL: {sl:.0f} pts ({sl_dist} pts de distancia)
TP: {tp:.0f} pts ({tp_dist} pts de distancia)
RR: {rr}:1
Lots: {lots} | Riesgo: ${risk_usd:.0f} (1% cuenta)

Análisis técnico:
- H4 EMA200 (tendencia): {trend_ema:.0f} pts → precio {"por encima" if direction=="LONG" else "por debajo"}
- H1 EMA50 (entrada): {e50:.0f} pts → pullback confirmado
- ADX H1: {adx} (momentum {"fuerte" if float(str(adx)) > 25 else "moderado"})
- RSI H1: {rsi}
- ATR H1: {atr:.0f} pts

Decisión GPT-4o: {direction} con {gpt_conf}% confianza
Razonamiento: {gpt_reason}

Estado cuenta FTMO:
Balance: ${balance:.2f} | Equity: ${equity:.2f} | DD actual: ${dd:.2f} / $2,500

Redacta el mensaje de Telegram explicando esta operación."""

    msg = _gpt_write(system, user, max_tokens=250)

    if not msg:
        # Fallback si GPT falla
        emoji = "📈" if direction == "LONG" else "📉"
        msg = (f"{emoji} <b>AURUM — ORDEN ABIERTA</b>\n\n"
               f"<b>{direction}</b> US30.cash @ {entry:.0f}\n"
               f"SL: {sl:.0f} | TP: {tp:.0f} | RR: {rr}:1\n"
               f"Lots: {lots} | Riesgo: ${risk_usd:.0f}\n\n"
               f"ADX: {adx} | RSI: {rsi}\n"
               f"GPT ({gpt_conf}%): {gpt_reason[:100]}")
    else:
        emoji = "📈" if direction == "LONG" else "📉"
        header = f"{emoji} <b>AURUM — ORDEN ABIERTA // {_now_utc()}</b>\n\n"
        footer = f"\n\n<i>SL: {sl:.0f} | TP: {tp:.0f} | RR: {rr}:1 | Lots: {lots} | Riesgo: ${risk_usd:.0f}</i>"
        msg = header + msg + footer

    send(msg)


# ──────────────────────────────────────────────
# ALERT: ORDEN CERRADA
# ──────────────────────────────────────────────

def alert_order_closed(direction, entry, exit_price, pnl, result, reason, account, stats):
    """Alerta cuando se cierra una posición (SL, TP o time exit)."""
    balance   = account.get("balance", 25000) if account else 25000
    equity    = account.get("equity",  25000) if account else 25000
    total_pnl = stats.get("total_pnl", 0)
    wins      = stats.get("wins", 0)
    losses    = stats.get("losses", 0)
    wr        = round(wins/(wins+losses)*100, 1) if (wins+losses) > 0 else 0

    system = """Eres el sistema de trading AURUM. Acaba de cerrarse una posición en US30.
Escribe un mensaje de Telegram en español, breve y honesto.
Si fue WIN: celebra con moderación, explica qué salió bien.
Si fue LOSS: sé directo, no dramatices, explica qué pasó y qué sigue.
Tono: trader profesional, sin emociones excesivas. Máximo 180 palabras."""

    user = f"""Se acaba de cerrar esta posición:
Instrumento: US30.cash
Dirección: {direction}
Entrada: {entry:.0f} | Salida: {exit_price:.0f}
Resultado: {result} | P&L: ${pnl:.2f}
Motivo de cierre: {reason}

Estado cuenta tras el trade:
Balance: ${balance:.2f} | Equity: ${equity:.2f}
P&L total acumulado: ${total_pnl:.2f}
Win rate: {wr}% ({wins}W / {losses}L)
Progreso FTMO Phase 1: {round((balance-25000)/2500*100,1)}% del objetivo +10%

Redacta el mensaje explicando este resultado."""

    msg = _gpt_write(system, user, max_tokens=220)

    if not msg:
        emoji = "✅" if result == "WIN" else "❌"
        msg = (f"{emoji} <b>AURUM — TRADE CERRADO</b>\n\n"
               f"{direction} US30 | {reason}\n"
               f"Entrada: {entry:.0f} → Salida: {exit_price:.0f}\n"
               f"P&L: <b>${pnl:.2f}</b> ({result})\n\n"
               f"Balance: ${balance:.2f} | WR: {wr}%")
    else:
        emoji = "✅" if result == "WIN" else "❌"
        header = f"{emoji} <b>AURUM — TRADE CERRADO // {_now_utc()}</b>\n\n"
        footer = f"\n\n<i>{direction} {entry:.0f}→{exit_price:.0f} | P&L: ${pnl:.2f} | Balance: ${balance:.2f}</i>"
        msg = header + msg + footer

    send(msg)


# ──────────────────────────────────────────────
# ALERT: STAY OUT (con setup detectado)
# ──────────────────────────────────────────────

def alert_stay_out(signal, gpt_result, news_summary=""):
    """Alerta cuando hay setup técnico pero GPT decide no operar."""
    direction  = signal.get("signal", "--")
    price      = signal.get("price", 0)
    adx        = signal.get("adx", "--")
    rsi        = signal.get("rsi", "--")
    gpt_reason = gpt_result.get("reason", "--")
    gpt_conf   = gpt_result.get("confidence", 0)

    system = """Eres el sistema AURUM. Detectaste un setup técnico en US30 pero decidiste NO operar.
Explica en 2-3 frases por qué. Tono: breve, profesional, en español. Máximo 100 palabras."""

    user = f"""Setup detectado: {direction} en US30 @ {price:.0f} (ADX: {adx}, RSI: {rsi})
GPT decidió STAY OUT con {gpt_conf}% confianza.
Razón GPT: {gpt_reason}
Noticias relevantes: {news_summary[:200] if news_summary else "sin contexto especial"}

Redacta el mensaje explicando por qué no se operó."""

    msg = _gpt_write(system, user, max_tokens=120)

    if not msg:
        msg = (f"⚠️ <b>AURUM — SETUP VETADO</b>\n\n"
               f"Setup {direction} detectado @ {price:.0f}\n"
               f"GPT STAY OUT ({gpt_conf}%): {gpt_reason[:100]}")
    else:
        header = f"⚠️ <b>AURUM — SETUP VETADO // {_now_utc()}</b>\n\n"
        footer = f"\n\n<i>Setup {direction} @ {price:.0f} | GPT: {gpt_conf}% confianza</i>"
        msg = header + msg + footer

    send(msg)


# ──────────────────────────────────────────────
# ALERT: BREAKEVEN
# ──────────────────────────────────────────────

def alert_breakeven(direction, entry, new_sl, current_price):
    """Alerta cuando se mueve el SL a breakeven."""
    pts = abs(current_price - entry)
    msg = (f"🔒 <b>AURUM — BREAKEVEN ACTIVADO // {_now_utc()}</b>\n\n"
           f"La posición {direction} US30 ha alcanzado +1R.\n"
           f"SL movido a breakeven: {new_sl:.0f} pts\n"
           f"Precio actual: {current_price:.0f} | Ganancia asegurada: ~${pts:.0f}\n\n"
           f"<i>El trade ya no puede cerrar en pérdida.</i>")
    send(msg)


# ──────────────────────────────────────────────
# ALERT: DAILY STOP
# ──────────────────────────────────────────────

def alert_daily_stop(reason, daily_pnl, consec_losses):
    """Alerta cuando el sistema para de operar por el día."""
    system = """Eres AURUM. El sistema ha parado de operar por hoy por seguridad.
Explica brevemente en español el motivo y qué significa. Máximo 80 palabras. Tono calmado y profesional."""

    user = f"""Motivo del stop: {reason}
P&L del día: ${daily_pnl:.2f}
Pérdidas consecutivas: {consec_losses}
El sistema no operará más hoy. Reinicia mañana automáticamente."""

    msg = _gpt_write(system, user, max_tokens=100)

    if not msg:
        msg = (f"🛑 <b>AURUM — STOP DEL DÍA // {_now_utc()}</b>\n\n"
               f"Motivo: {reason}\n"
               f"P&L hoy: ${daily_pnl:.2f} | Pérdidas consecutivas: {consec_losses}\n\n"
               f"<i>El sistema reinicia automáticamente mañana.</i>")
    else:
        msg = f"🛑 <b>AURUM — STOP DEL DÍA // {_now_utc()}</b>\n\n" + msg

    send(msg)


# ──────────────────────────────────────────────
# ALERT: RESUMEN DIARIO (22:00 UTC)
# ──────────────────────────────────────────────

def alert_daily_summary(daemon_state, account, trades_today):
    """Resumen diario generado por GPT a las 22:00 UTC."""
    balance   = account.get("balance", 25000) if account else 25000
    equity    = account.get("equity",  25000) if account else 25000
    total_w   = daemon_state.get("total_wins", 0)
    total_t   = daemon_state.get("total_trades", 0)
    daily_pnl = daemon_state.get("daily_pnl", 0)
    progress  = round((balance - 25000) / 2500 * 100, 1)

    system = """Eres AURUM, un sistema de trading automatizado para FTMO.
Escribe el resumen diario en español, estilo trading journal.
Incluye: qué pasó hoy, estado de la cuenta, progreso FTMO, perspectivas para mañana.
Tono: profesional, conciso, informativo. Máximo 220 palabras."""

    trades_str = ""
    if trades_today:
        for t in trades_today:
            trades_str += f"- {t.get('direction','?')} @ {t.get('entry',0):.0f} → {t.get('result','?')} (${t.get('pnl',0):.2f})\n"
    else:
        trades_str = "Sin trades ejecutados hoy."

    user = f"""RESUMEN DEL DÍA — {datetime.now(timezone.utc).strftime('%A %d %B %Y')}

Trades de hoy:
{trades_str}

Estado cuenta:
Balance: ${balance:.2f} | Equity: ${equity:.2f}
P&L hoy: ${daily_pnl:.2f}
Total trades: {total_t} | Wins: {total_w} | WR: {round(total_w/max(total_t,1)*100,1)}%

Progreso FTMO Phase 1: {progress}% completado
Objetivo: +10% ($27,500) | Actual: ${balance:.2f}
Restante: ${max(0, 27500-balance):.2f}

Redacta el resumen diario."""

    msg = _gpt_write(system, user, max_tokens=260)

    if not msg:
        msg = (f"📊 <b>AURUM — RESUMEN DIARIO // {datetime.now(timezone.utc).strftime('%d/%m/%Y')}</b>\n\n"
               f"P&L hoy: ${daily_pnl:.2f}\n"
               f"Balance: ${balance:.2f}\n"
               f"Progreso FTMO: {progress}%\n"
               f"WR total: {round(total_w/max(total_t,1)*100,1)}%")
    else:
        msg = (f"📊 <b>AURUM — RESUMEN DIARIO // "
               f"{datetime.now(timezone.utc).strftime('%d/%m/%Y')} 22:00 UTC</b>\n\n"
               + msg)

    send(msg)


# ──────────────────────────────────────────────
# ALERT: DAEMON START/STOP
# ──────────────────────────────────────────────

def alert_daemon_start(account):
    """Alerta de arranque del daemon."""
    balance  = account.get("balance", 25000) if account else 25000
    progress = round((balance - 25000) / 2500 * 100, 1)
    msg = (f"🤖 <b>AURUM DAEMON INICIADO // {_now_utc()}</b>\n\n"
           f"Sistema activo — US30.cash (Dow Jones)\n"
           f"Estrategia: H4 EMA200 + H1 EMA50 pullback\n"
           f"Árbitro: GPT-4o con contexto de noticias y macro\n"
           f"Sesión: 14:00–20:00 UTC | Riesgo: 1%/trade\n\n"
           f"Balance: <b>${balance:.2f}</b> | FTMO P1: <b>{progress}%</b>\n"
           f"<i>Esperando señal en apertura NY...</i>")
    send(msg)


def alert_daemon_stop(reason="user"):
    """Alerta de parada del daemon."""
    msg = (f"🛑 <b>AURUM DAEMON PARADO // {_now_utc()}</b>\n\n"
           f"Motivo: {reason}\n"
           f"<i>El sistema se reiniciará automáticamente al próximo arranque.</i>")
    send(msg)


# ──────────────────────────────────────────────
# ALERT: DECISION (para main.py)
# ──────────────────────────────────────────────

def alert_decision(cycle_data):
    """
    Alerta genérica llamada desde main.py al final de cada ciclo.
    Solo envía mensaje si hubo señal técnica detectada.
    """
    decision = cycle_data.get("decision", "STAY OUT")
    signal   = cycle_data.get("signal")
    gpt_res  = cycle_data.get("gpt_result", {})
    conf     = cycle_data.get("confidence", 0)
    reason   = cycle_data.get("reason", "")

    # Solo alertar si hay algo interesante
    if not signal:
        return  # Sin setup técnico → silencio

    if decision in ("LONG", "SHORT"):
        # Alerta de orden — construir datos necesarios
        account = cycle_data.get("portfolio", {})
        lots    = cycle_data.get("lots", 0.01)
        price   = signal.get("price", 0)
        sl_d    = signal.get("sl_dist", 0)
        tp_d    = signal.get("tp_dist", 0)
        entry   = price
        sl      = round(entry - sl_d, 0) if decision == "LONG" else round(entry + sl_d, 0)
        tp      = round(entry + tp_d, 0) if decision == "LONG" else round(entry - tp_d, 0)
        risk    = round(account.get("equity", 25000) * 0.01, 2)
        alert_order_placed(signal, gpt_res, lots, entry, sl, tp, risk, account)
    else:
        # STAY OUT con señal técnica → explicar por qué
        alert_stay_out(signal, gpt_res)


# ──────────────────────────────────────────────
# TEST
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing Telegram alerts...")

    # Test send simple
    send("🧪 <b>AURUM TEST</b>\n\nSistema de mensajes personalizados activo.\nGPT-4o redactará todos los mensajes.")
    print("Simple message sent OK")

    # Test GPT message
    print("Testing GPT message writer...")
    test_signal = {
        "signal": "LONG", "price": 47957.0,
        "adx": 21.9, "rsi": 37.7, "atr": 109.8,
        "sl_dist": 164.7, "tp_dist": 329.4, "rr": 2.0,
        "e50": 47901.0, "trend_ema": 47512.0,
        "confidence": 78,
    }
    test_gpt = {
        "decision": "LONG",
        "confidence": 78,
        "reason": "Strong uptrend H4, clean pullback to EMA50, news neutral, macro supportive"
    }
    test_account = {"balance": 26312.41, "equity": 26312.41}

    alert_order_placed(test_signal, test_gpt, 0.02, 47957.0, 47792.3, 48286.4, 263.0, test_account)
    print("GPT order alert sent OK")
