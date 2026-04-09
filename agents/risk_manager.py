import os
from utils.price_history import get_full_technical_context

CAPITAL     = 25000.0
MAX_RISK_PCT = 0.02
MIN_RR       = 2.0

def _get_atr_from_mt5():
    try:
        import MetaTrader5 as mt5
        from datetime import datetime
        if mt5.initialize():
            rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_D1, 0, 20)
            if rates is not None and len(rates) >= 2:
                trs = []
                for i in range(1, len(rates)):
                    h  = float(rates[i]["high"])
                    l  = float(rates[i]["low"])
                    pc = float(rates[i-1]["close"])
                    trs.append(max(h - l, abs(h - pc), abs(l - pc)))
                mt5.shutdown()
                return round(sum(trs[-14:]) / min(14, len(trs)), 2)
        mt5.shutdown()
    except Exception as e:
        print("[risk] MT5 ATR error:", e)
    return None

def calculate(tech_signal, price_data, account_balance=None):
    """
    Calcula risk plan basado en señal tecnica del signal_engine.

    tech_signal: dict de signal_engine con signal, sl_dist, tp_dist, rr, atr
    price_data:  dict con price, high, low
    account_balance: balance de MT5

    Returns: dict con valid, direction, entry, stop_loss, take_profit,
             contracts, risk_usd, risk_reward, atr_used
    """
    balance = account_balance or CAPITAL
    price   = price_data.get("price", 0)

    if not tech_signal:
        return {"valid": False, "reason": "No technical signal"}

    if not price or price <= 0:
        return {"valid": False, "reason": "Invalid price: " + str(price)}

    direction = tech_signal["signal"]

    # ATR: usar el del signal_engine primero, luego MT5 directo
    atr = tech_signal.get("atr")
    if not atr:
        atr = _get_atr_from_mt5()
    if not atr:
        atr = price * 0.008
        print("[risk] ATR fallback: " + str(round(atr, 2)))
    else:
        print("[risk] ATR real: " + str(round(atr, 2)))

    # SL y TP desde signal_engine (ya calculados con ATR * multiplier)
    sl_dist = tech_signal.get("sl_dist", round(atr * 1.5, 2))
    tp_dist = tech_signal.get("tp_dist", round(atr * 3.0, 2))
    rr      = round(tp_dist / sl_dist, 1)

    if rr < MIN_RR:
        return {"valid": False, "reason": "RR=" + str(rr) + " below minimum " + str(MIN_RR)}

    # Precio de entrada (precio actual)
    entry = round(price, 2)

    if direction == "LONG":
        stop_loss   = round(entry - sl_dist, 2)
        take_profit = round(entry + tp_dist, 2)
    else:
        stop_loss   = round(entry + sl_dist, 2)
        take_profit = round(entry - tp_dist, 2)

    # Sizing: 2% del balance en riesgo
    risk_usd = round(balance * MAX_RISK_PCT, 2)

    # XAU/USD: 1 lote = 100 oz
    # pip value = $1 por 0.01 lote por $1 de movimiento
    # lots = risk_usd / (sl_dist * 100)
    lots = risk_usd / (sl_dist * 100)
    lots = round(max(0.01, min(lots, 5.0)), 2)

    # Recalcular risk_usd real con lots redondeados
    risk_usd_real = round(lots * sl_dist * 100, 2)

    # Margen check (leverage 30x)
    margin_required = round(entry * lots * 100 / 30, 2)
    free_margin     = balance * 0.8  # asume 80% libre
    if margin_required > free_margin:
        lots      = round(lots * 0.5, 2)
        risk_usd_real = round(lots * sl_dist * 100, 2)
        print("[risk] Margin reduced — lots=" + str(lots))

    return {
        "valid":        True,
        "direction":    direction,
        "signal_type":  tech_signal.get("sig_type", ""),
        "entry":        entry,
        "stop_loss":    stop_loss,
        "take_profit":  take_profit,
        "sl_dist":      sl_dist,
        "tp_dist":      tp_dist,
        "risk_reward":  rr,
        "contracts":    lots,
        "risk_usd":     risk_usd_real,
        "atr_used":     round(atr, 2),
        "balance_used": balance,
        "confidence":   tech_signal.get("confidence", 60),
    }
